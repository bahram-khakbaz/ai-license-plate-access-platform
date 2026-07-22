import base64
import json
import os
import secrets
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from flask import jsonify, redirect, render_template, request, session

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

from security_utils import safe_redirect_target


_DISCOVERY_CACHE = None
_JWKS_CACHE = None


def _truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def sso_enabled(auth_mode_func=None):
    mode = ""
    try:
        mode = (auth_mode_func() or "").strip().lower() if auth_mode_func else ""
    except Exception:
        mode = ""
    return mode == "sso_local_roles" or _truthy(os.getenv("SSO_ENABLED"))


def _required_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def _fetch_json(url, method="GET", data=None, headers=None):
    headers = headers or {}
    if data is not None:
        data = data.encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not connect to {url}: {exc}") from exc


def _discovery():
    global _DISCOVERY_CACHE
    if _DISCOVERY_CACHE is None:
        url = _required_env("DSSO_DISCOVERY_URL")
        _DISCOVERY_CACHE = _fetch_json(url)
    return _DISCOVERY_CACHE


def _authorize_endpoint():
    return (
        os.getenv("DSSO_AUTHORIZE_URL", "").strip()
        or _discovery().get("authorization_endpoint")
    )


def _token_endpoint():
    return (
        os.getenv("DSSO_TOKEN_URL", "").strip()
        or _discovery().get("token_endpoint")
    )


def _jwks():
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        jwks_uri = os.getenv("DSSO_JWKS_URI", "").strip() or _discovery().get("jwks_uri")
        if not jwks_uri:
            raise RuntimeError("jwks_uri was not found in DSSO discovery document")
        _JWKS_CACHE = _fetch_json(jwks_uri)
    return _JWKS_CACHE


def _b64url_decode(value):
    value = value.encode("utf-8") if isinstance(value, str) else value
    value += b"=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value)


def _jwt_parts(token):
    parts = token.split(".")
    if len(parts) != 3:
        raise RuntimeError("Invalid JWT format")

    header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    signing_input = (parts[0] + "." + parts[1]).encode("utf-8")
    signature = _b64url_decode(parts[2])
    return header, claims, signing_input, signature


def _rsa_public_key_from_jwk(jwk):
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def _find_jwk(header):
    keys = _jwks().get("keys", [])
    kid = header.get("kid")

    if kid:
        for key in keys:
            if key.get("kid") == kid:
                return key

    for key in keys:
        if key.get("kty") == "RSA":
            return key

    raise RuntimeError("Matching DSSO signing key was not found")


def _verify_id_token(id_token):
    header, claims, signing_input, signature = _jwt_parts(id_token)

    if header.get("alg") != "RS256":
        raise RuntimeError(f"Unsupported id_token alg: {header.get('alg')}")

    public_key = _rsa_public_key_from_jwk(_find_jwk(header))
    public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())

    now = int(time.time())
    leeway = int(os.getenv("DSSO_CLOCK_SKEW_SECONDS", "300"))

    exp = int(claims.get("exp", 0))
    if exp and now > exp + leeway:
        raise RuntimeError("id_token is expired")

    nbf = claims.get("nbf")
    if nbf is not None and now + leeway < int(nbf):
        raise RuntimeError("id_token is not valid yet")

    client_id = _required_env("DSSO_CLIENT_ID")
    aud = claims.get("aud")

    if isinstance(aud, list):
        if client_id not in aud:
            raise RuntimeError("id_token audience mismatch")
    elif aud != client_id:
        raise RuntimeError("id_token audience mismatch")

    expected_issuer = os.getenv("DSSO_ISSUER", "").strip() or _discovery().get("issuer", "")
    if expected_issuer and claims.get("iss") != expected_issuer:
        raise RuntimeError(f"id_token issuer mismatch. got={claims.get('iss')} expected={expected_issuer}")

    expected_nonce = session.get("sso_nonce")
    token_nonce = claims.get("nonce")
    if token_nonce and expected_nonce and token_nonce != expected_nonce:
        raise RuntimeError("id_token nonce mismatch")

    return claims


def _exchange_code_for_token(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _required_env("DSSO_REDIRECT_URI"),
        "client_id": _required_env("DSSO_CLIENT_ID"),
    }

    auth_method = os.getenv("DSSO_TOKEN_ENDPOINT_AUTH_METHOD", "client_secret_post").strip()

    if auth_method == "client_secret_post":
        data["client_secret"] = _required_env("DSSO_CLIENT_SECRET")
    else:
        raise RuntimeError(f"Unsupported token endpoint auth method: {auth_method}")

    return _fetch_json(_token_endpoint(), method="POST", data=urlencode(data))


def _claim_get(claims, *keys):
    for key in keys:
        value = claims.get(key)
        if value:
            return str(value).strip()
    return ""


def _candidate_usernames(claims):
    raw_values = [
        _claim_get(claims, "upn"),
        _claim_get(claims, "email"),
        _claim_get(claims, "preferred_username"),
        _claim_get(claims, "unique_name"),
        _claim_get(claims, "nameid"),
        _claim_get(claims, "sub"),
    ]

    candidates = []

    for value in raw_values:
        value = (value or "").strip().lower()
        if not value:
            continue

        if value not in candidates:
            candidates.append(value)

        if "@" in value:
            short = value.split("@", 1)[0]
            if short and short not in candidates:
                candidates.append(short)

    return candidates


def _is_active_user(user):
    if not user:
        return False
    return str(user.get("active", 1)).lower() not in ("0", "false", "none")


def _find_local_user(db, claims):
    for username in _candidate_usernames(claims):
        try:
            user = db.user_public(username)
        except Exception:
            user = None

        if _is_active_user(user):
            return user

    return None


def _display_name(claims, local_user):
    return (
        local_user.get("full_name")
        or _claim_get(claims, "name")
        or _claim_get(claims, "display_name")
        or _claim_get(claims, "given_name")
        or local_user.get("username")
        or ""
    )


def _email_from_claims(claims):
    return _claim_get(claims, "email", "upn", "preferred_username", "unique_name").lower()
def register_dsso_routes(app, db, auth_mode_func=None):
    @app.before_request
    def dsso_login_page_override():
        if not sso_enabled(auth_mode_func):
            return None

        if request.path == "/login":
            if request.method in ("GET", "HEAD"):
                if request.args.get("sso") == "1":
                    state = secrets.token_urlsafe(32)
                    nonce = secrets.token_urlsafe(32)

                    session["sso_state"] = state
                    session["sso_nonce"] = nonce
                    session["sso_next"] = safe_redirect_target(request.args.get("next"), "/")

                    params = {
                        "client_id": _required_env("DSSO_CLIENT_ID"),
                        "response_type": "code",
                        "redirect_uri": _required_env("DSSO_REDIRECT_URI"),
                        "scope": os.getenv("DSSO_SCOPE", "openid profile email").strip(),
                        "state": state,
                        "nonce": nonce,
                    }

                    return redirect(_authorize_endpoint() + "?" + urlencode(params))

                return render_template("login.html")

            return jsonify({
                "error": "Password login is disabled. Use DigiKala SSO."
            }), 403

        return None

    @app.route("/sso/start")
    def sso_start():
        if not sso_enabled(auth_mode_func):
            return redirect("/login")

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        session["sso_state"] = state
        session["sso_nonce"] = nonce
        session["sso_next"] = safe_redirect_target(request.args.get("next"), "/")

        params = {
            "client_id": _required_env("DSSO_CLIENT_ID"),
            "response_type": "code",
            "redirect_uri": _required_env("DSSO_REDIRECT_URI"),
            "scope": os.getenv("DSSO_SCOPE", "openid profile email").strip(),
            "state": state,
            "nonce": nonce,
        }

        return redirect(_authorize_endpoint() + "?" + urlencode(params))

    @app.route("/sso/callback")
    def sso_callback():
        if not sso_enabled(auth_mode_func):
            return redirect("/login")

        if request.args.get("error"):
            return (
                "DSSO error: "
                + request.args.get("error", "")
                + " "
                + request.args.get("error_description", ""),
                401,
            )

        code = request.args.get("code", "").strip()
        state = request.args.get("state", "").strip()

        if not code:
            return "DSSO callback missing code", 400

        if not state or state != session.get("sso_state"):
            return "DSSO callback state mismatch", 400

        token = _exchange_code_for_token(code)
        id_token = token.get("id_token")

        if not id_token:
            return "DSSO token response did not contain id_token", 401

        try:
            claims = _verify_id_token(id_token)
        except Exception as exc:
            return f"DSSO id_token validation failed: {exc}", 401

        local_user = _find_local_user(db, claims)

        if not local_user:
            candidates = ", ".join(_candidate_usernames(claims))
            return (
                "DSSO authentication succeeded, but this user is not allowed in Plate Reader local users panel. "
                f"Please add one of these usernames to local users: {candidates}",
                403,
            )

        next_url = session.get("sso_next", "/")

        session.clear()
        session["username"] = local_user["username"]
        session["role"] = local_user.get("role") or "viewer"
        session["full_name"] = _display_name(claims, local_user)
        session["auth_provider"] = "dsso"
        session["sso_email"] = _email_from_claims(claims)

        return redirect(safe_redirect_target(next_url, "/"))

    @app.route("/sso/me")
    def sso_me():
        if not session.get("username"):
            return jsonify({"user": None}), 401

        return jsonify({
            "username": session.get("username"),
            "role": session.get("role"),
            "full_name": session.get("full_name"),
            "auth_provider": session.get("auth_provider"),
            "sso_email": session.get("sso_email"),
        })

    @app.before_request
    def dsso_public_route_dispatcher():
        if not sso_enabled(auth_mode_func):
            return None

        public_sso_routes = {
            "/sso/start": "sso_start",
            "/sso/callback": "sso_callback",
            "/sso/me": "sso_me",
        }

        endpoint = public_sso_routes.get(request.path)
        if not endpoint:
            return None

        view = app.view_functions.get(endpoint)
        if view is None:
            return None

        return view()

    try:
        funcs = app.before_request_funcs.setdefault(None, [])
        if funcs and getattr(funcs[-1], "__name__", "") == "dsso_public_route_dispatcher":
            funcs.insert(0, funcs.pop())
    except Exception:
        pass

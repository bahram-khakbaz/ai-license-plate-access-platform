from urllib.parse import quote

from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

import storage
from config import APP_HOST, APP_PORT, SECRET_KEY
from import_tools import (
    build_vehicle_csv_template,
    build_vehicle_template,
    import_vehicles_csv,
    import_vehicles_excel,
)
from plate_engine import recognize, status as model_status


app = Flask(__name__)
app.secret_key = SECRET_KEY


def normalize_role(value):
    raw = str(value or "").strip().lower()
    mapping = {
        "admin": "admin",
        "administrator": "admin",
        "مدیر": "admin",
        "ادمین": "admin",
        "security": "security",
        "guard": "security",
        "harasat": "security",
        "حراست": "security",
        "نگهبان": "security",
        "سکیوریتی": "security",
        "viewer": "viewer",
        "view": "viewer",
        "read": "viewer",
        "readonly": "viewer",
        "ویو": "viewer",
        "مشاهده": "viewer",
        "مشاهده‌گر": "viewer",
        "مشاهده گر": "viewer",
    }
    return mapping.get(raw, raw or "viewer")


def session_username():
    return session.get("username")


def current_user():
    username = session_username()
    if not username:
        return None
    return storage.get_user(username)


def current_role():
    user = current_user()
    if not user:
        return "viewer"
    return normalize_role(user.get("role"))


def is_logged_in():
    return current_user() is not None


def path_allowed_for_role(role, path, method="GET"):
    role = normalize_role(role)
    path = path or "/"
    method = (method or "GET").upper()

    if path.startswith("/static/") or path.startswith("/captures/") or path.startswith("/uploads/"):
        return True

    if path in ["/login", "/logout", "/dx/logout", "/force-logout", "/status"]:
        return True

    if role == "admin":
        return True

    if role == "viewer":
        if path in ["/", "/logs", "/dx/whoami"]:
            return True
        allowed_prefixes = [
            "/api/dashboard-stats",
            "/api/sites",
            "/dx/api/live-data",
            "/dx/api/logs",
            "/dx/api/sites",
        ]
        return any(path.startswith(prefix) for prefix in allowed_prefixes)

    if role == "security":
        blocked_exact = [
            "/users",
            "/settings",
            "/mobile-entry",
            "/vehicles/import",
            "/api/log",
            "/api/log.csv",
        ]
        blocked_prefixes = [
            "/users/",
            "/settings/",
            "/api/users",
            "/api/settings",
            "/mobile-entry/",
            "/dx/vehicle-import-preview",
            "/dx/vehicle-import-template.csv",
            "/dx/api/vehicle-import-preview",
            "/dx/api/vehicle-import-commit",
        ]
        if path in blocked_exact:
            return False
        if any(path.startswith(prefix) for prefix in blocked_prefixes):
            return False

        allowed_exact = [
            "/",
            "/scan",
            "/vehicles",
            "/manual-entry",
            "/logs",
            "/cameras",
            "/settings/sites",
            "/dx/sites",
            "/site-admin",
            "/dx/whoami",
        ]
        allowed_prefixes = [
            "/vehicle/",
            "/log-edit/",
            "/cameras/",
            "/settings/sites/",
            "/dx/sites/",
            "/api/vehicles",
            "/api/vehicle-profile/",
            "/api/cameras",
            "/api/camera",
            "/api/dashboard-stats",
            "/api/sites",
            "/dx/api/live-data",
            "/dx/api/logs",
            "/dx/api/sites",
            "/dx/api/camera-sites",
        ]
        if path in allowed_exact:
            return True
        if any(path.startswith(prefix) for prefix in allowed_prefixes):
            return True
        return False

    return path_allowed_for_role("viewer", path, method)


@app.before_request
def bootstrap_and_guard():
    storage.setup()
    path = request.path or "/"

    if path in ["/logout", "/dx/logout", "/force-logout"]:
        session.clear()
        response = make_response(redirect("/login"))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    if path.startswith("/static/") or path in ["/login", "/status"]:
        return None

    if not is_logged_in():
        if path.startswith("/api/") or path.startswith("/dx/api/"):
            return jsonify({"error": "auth required"}), 401
        return redirect("/login?next=" + quote(path))

    role = current_role()
    if not path_allowed_for_role(role, path, request.method):
        if path.startswith("/api/") or path.startswith("/dx/api/"):
            return jsonify({"error": "access denied", "role": role, "path": path}), 403
        return render_template("access_denied.html", role=role, path=path), 403

    return None


@app.context_processor
def inject_auth_context():
    user = current_user()
    return {
        "auth_user": user,
        "auth_username": user.get("username") if user else "",
        "auth_role": current_role() if user else "guest",
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = storage.verify_user(username, password)
        if user:
            session.clear()
            session["username"] = user["username"]
            return redirect(request.args.get("next") or url_for("index"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)


@app.route("/")
def index():
    sites = storage.sites(active_only=True)
    return render_template("index.html", sites=sites)


@app.route("/scan", methods=["GET", "POST"])
def scan():
    result = None
    sites = storage.sites(active_only=True)
    if request.method == "POST":
        result = recognize(
            request.files.get("image"),
            request.form.get("plate"),
            request.form.get("plate_color"),
        )
        if result.get("plate"):
            storage.save_event({
                "site_id": request.form.get("site_id"),
                "plate": result["plate"],
                "gate_role": request.form.get("gate_role") or "entry",
                "source": "scan",
                "plate_color": result.get("plate_color"),
                "score": result.get("confidence"),
                "image_path": result.get("image_path"),
                "crop_path": result.get("crop_path"),
                "operator_name": request.form.get("operator_name"),
                "note": request.form.get("note"),
            })
    return render_template("scan.html", result=result, sites=sites)


@app.route("/manual-entry", methods=["GET", "POST"])
def manual_entry():
    sites = storage.sites(active_only=True)
    if request.method == "POST":
        data = dict(request.form)
        data["source"] = "manual"
        storage.save_event(data)
        return redirect(url_for("logs", site_id=request.form.get("site_id") or ""))
    return render_template("manual_entry.html", sites=sites)


@app.route("/mobile-entry", methods=["GET", "POST"])
def mobile_entry():
    sites = storage.sites(active_only=True)
    if request.method == "POST":
        data = dict(request.form)
        data["source"] = "mobile"
        storage.save_event(data)
        return redirect(url_for("logs", site_id=request.form.get("site_id") or ""))
    return render_template("mobile_entry.html", sites=sites)


@app.route("/vehicles", methods=["GET", "POST"])
def vehicles():
    sites = storage.sites(active_only=True)
    selected_site_id = request.values.get("site_id") or ""
    if request.method == "POST":
        storage.save_vehicle(request.form)
        return redirect(url_for("vehicles", site_id=request.form.get("site_id") or ""))
    return render_template(
        "vehicles.html",
        vehicles=storage.vehicles(selected_site_id or None),
        sites=sites,
        selected_site_id=selected_site_id,
    )


@app.route("/vehicles/template.xlsx")
def vehicle_template():
    output = build_vehicle_template()
    return send_file(
        output,
        as_attachment=True,
        download_name="vehicle-import-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/dx/vehicle-import-template.csv")
def vehicle_template_csv():
    output = build_vehicle_csv_template()
    return send_file(
        output,
        as_attachment=True,
        download_name="vehicle-import-template.csv",
        mimetype="text/csv; charset=utf-8",
    )


@app.route("/vehicles/import", methods=["GET", "POST"])
def vehicle_import():
    result = None
    sites = storage.sites(active_only=True)
    selected_site_id = request.values.get("site_id") or ""
    if request.method == "POST":
        uploaded = request.files.get("file")
        filename = (uploaded.filename or "").lower() if uploaded else ""
        if filename.endswith(".csv"):
            result = import_vehicles_csv(uploaded, request.form.get("site_id"))
        else:
            result = import_vehicles_excel(uploaded, request.form.get("site_id"))
        selected_site_id = request.form.get("site_id") or ""
    return render_template(
        "vehicle_import.html",
        sites=sites,
        selected_site_id=selected_site_id,
        result=result,
    )


@app.route("/cameras", methods=["GET", "POST"])
def cameras():
    sites = storage.sites(active_only=True)
    selected_site_id = request.values.get("site_id") or ""
    if request.method == "POST":
        storage.save_camera(request.form)
        return redirect(url_for("cameras", site_id=request.form.get("site_id") or ""))
    return render_template(
        "cameras.html",
        cameras=storage.cameras(selected_site_id or None),
        sites=sites,
        selected_site_id=selected_site_id,
    )


@app.route("/logs")
def logs():
    sites = storage.sites(active_only=True)
    selected_site_id = request.args.get("site_id") or ""
    return render_template(
        "logs.html",
        rows=storage.events(100, selected_site_id or None),
        sites=sites,
        selected_site_id=selected_site_id,
    )


@app.route("/settings/sites", methods=["GET", "POST"])
@app.route("/dx/sites", methods=["GET", "POST"])
def site_settings():
    if request.method == "POST":
        action = request.form.get("action") or "save_site"
        if action == "toggle_site":
            storage.toggle_site(request.form.get("site_id"))
        elif action == "assign_camera":
            storage.assign_camera_to_site(request.form.get("camera_id"), request.form.get("site_id"))
        else:
            storage.save_site(request.form)
        return redirect(url_for("site_settings"))

    return render_template(
        "settings_sites.html",
        sites=storage.site_summary(),
        cameras=storage.cameras(all_sites=True),
    )


@app.route("/site-admin")
def site_admin_alias():
    return redirect(url_for("site_settings"))


@app.route("/settings/sites/<int:site_id>/toggle", methods=["POST"])
def site_toggle(site_id):
    storage.toggle_site(site_id)
    return redirect(url_for("site_settings"))


@app.route("/status")
def status():
    return jsonify(model_status())


@app.route("/dx/whoami")
def whoami():
    user = current_user()
    if not user:
        return jsonify({"logged_in": False}), 401

    return jsonify({
        "logged_in": True,
        "username": user["username"],
        "db_role": user["role"],
        "normalized_role": current_role(),
    })


@app.route("/api/dashboard-stats")
def api_dashboard_stats():
    return jsonify(storage.stats(request.args.get("site_id") or None))


@app.route("/api/sites")
@app.route("/dx/api/sites")
def api_sites():
    return jsonify(storage.sites(active_only=True))


@app.route("/dx/api/live-data")
def api_live_data():
    site_id = request.args.get("site_id") or None
    return jsonify(storage.stats(site_id))


@app.route("/dx/api/logs")
def api_logs():
    site_id = request.args.get("site_id") or None
    limit = int(request.args.get("limit") or 100)
    return jsonify({"rows": storage.events(limit, site_id)})


@app.route("/api/log")
def api_log_admin():
    site_id = request.args.get("site_id") or None
    limit = int(request.args.get("limit") or 200)
    return jsonify(storage.events(limit, site_id))


@app.route("/api/vehicles")
def api_vehicles():
    site_id = request.args.get("site_id") or None
    return jsonify(storage.vehicles(site_id))


if __name__ == "__main__":
    storage.setup()
    app.run(host=APP_HOST, port=APP_PORT)

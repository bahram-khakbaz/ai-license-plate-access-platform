from urllib.parse import urlsplit


def safe_redirect_target(target, default="/"):
    target = (target or "").strip()
    default = default or "/"

    if not target:
        return default

    parsed = urlsplit(target)

    if parsed.scheme or parsed.netloc:
        return default

    if not target.startswith("/"):
        return default

    if target.startswith("//"):
        return default

    if "\\" in target:
        return default

    path_only = target.split("?", 1)[0].split("#", 1)[0]
    blocked_paths = {
        "/login",
        "/logout",
        "/dx/logout",
        "/force-logout",
    }

    if path_only in blocked_paths:
        return default

    return target

"""Compatibility extension for production multi-site routes.

The production server historically used a separate ``dx_multi_site.py`` module for
multi-site, camera assignment, live dashboard and report helpers.  The public-safe
GitHub version now keeps the active routes in ``app.py`` and the persistence layer in
``storage.py``; this module is kept so deployments that still import
``dx_multi_site`` do not fail.

No secrets, camera URLs, runtime data, database files or model binaries belong in
this file.
"""


def register(app):
    """Compatibility no-op.

    Existing deployments may call ``dx_multi_site.register(app)``.  Routes are
    already registered in ``app.py`` in this public-safe template, so this function
    intentionally does nothing.
    """
    return app

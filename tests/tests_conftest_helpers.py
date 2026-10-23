"""Service probes shared by the conftest files."""
_SERVICES = None


def services_up() -> bool:
    global _SERVICES
    if _SERVICES is None:
        try:
            from musicengine import db
            from musicengine.storage import Storage

            with db.conn_ctx() as c:
                db.ping(c)
            Storage().client.list_buckets()
            _SERVICES = True
        except Exception:
            _SERVICES = False
    return _SERVICES

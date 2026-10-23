"""Command line: init-bucket, export-openapi, qa, batch."""
import argparse
import sys


def cmd_init_bucket(_args) -> int:
    from .storage import get_storage

    get_storage().ensure_bucket()
    print("bucket ready")
    return 0


def openapi_yaml() -> str:
    import yaml

    from .api.main import app

    return yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True, width=120)


def cmd_export_openapi(args) -> int:
    with open(args.path, "w") as fh:
        fh.write(openapi_yaml())
    print(f"wrote {args.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="musicengine")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-bucket").set_defaults(fn=cmd_init_bucket)
    e = sub.add_parser("export-openapi")
    e.add_argument("path", nargs="?", default="openapi.yaml")
    e.set_defaults(fn=cmd_export_openapi)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

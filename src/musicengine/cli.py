"""Command line: init-bucket, export-openapi, qa, batch."""
import argparse
import sys


def cmd_init_bucket(_args) -> int:
    from .storage import get_storage

    get_storage().ensure_bucket()
    print("bucket ready")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="musicengine")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-bucket").set_defaults(fn=cmd_init_bucket)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

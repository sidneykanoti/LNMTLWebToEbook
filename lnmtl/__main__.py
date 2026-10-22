import argparse

from .export import export_book
from .library import Library
from .source import Client


def main():
    parser = argparse.ArgumentParser(description="Archive available LNMTL chapters for offline reading.")
    parser.add_argument("--library", help="Alternate library directory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalogue")
    index = sub.add_parser("index")
    index.add_argument("novel")
    download = sub.add_parser("download")
    download.add_argument("slug")
    download.add_argument("--limit", type=int)
    export = sub.add_parser("export")
    export.add_argument("slug")
    export.add_argument("--format", nargs="+", choices=["epub", "pdf", "html"], default=["epub"])
    sub.add_parser("status")
    args = parser.parse_args()
    lib = Library(args.library)
    try:
        if args.command == "catalogue":
            items = Client().catalogue(print)
            lib.catalogue(items)
            print(f"Saved {len(items)} novels.")
        elif args.command == "index":
            n = Client().discover(args.novel, print)
            lib.save_index(n)
            print(f'Indexed {len(n["chapters"])} available chapters.')
        elif args.command == "download":
            if args.limit is not None and args.limit < 1:
                parser.error("--limit must be positive")
            print(lib.download(args.slug, report=print, limit=args.limit))
        elif args.command == "export":
            for p in export_book(lib, args.slug, args.format):
                print(p)
        elif args.command == "status":
            for n in lib.novels():
                print(n["slug"], lib.summary(n["slug"]))
    finally:
        lib.close()


if __name__ == "__main__":
    main()

import argparse
from cli.search import run as search_run
from cli.download import run as download_run
from cli.list import run as list_run


def main():
    parser = argparse.ArgumentParser(
        prog="papers",
        description="Academic paper search and download tool",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = sub.add_parser("search", help="Search for papers by topic")
    p_search.add_argument("--topic", "-t", required=True, help="Search topic")
    p_search.add_argument("--max", "-n", type=int, default=20, help="Max results (default: 20)")
    p_search.add_argument("--sources", "-s", default="semantic,arxiv,scholar",
                          help="Comma-separated sources (default: semantic,arxiv,scholar)")
    p_search.add_argument("--new-topic", action="store_true",
                          help="Force a new topic directory even if a similar one exists")
    p_search.add_argument("--merge-into", type=str, default=None,
                          help="Merge results into an existing topic slug (bypasses auto-detection)")

    # download
    p_dl = sub.add_parser("download", help="Download papers from saved results")
    p_dl.add_argument("--topic", "-t", required=True, help="Topic of saved results")
    p_dl.add_argument("--all", "-a", action="store_true", help="Download all pending papers")

    # list
    sub.add_parser("list", help="List saved topics")

    args = parser.parse_args()

    if args.command == "search":
        search_run(args)
    elif args.command == "download":
        download_run(args)
    elif args.command == "list":
        list_run(args)


if __name__ == "__main__":
    main()

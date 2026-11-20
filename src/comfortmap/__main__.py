"""Command line: python -m comfortmap table|zones|svg FILE.csv"""

from __future__ import annotations

import argparse
import sys

from .analysis import balance, load, select, svg_heatmap, text_table


def main(argv: list[str] | None = None) -> int:
    """Return 0 on success, 1 when rows were skipped with --strict, 2 for a missing or unreadable file."""
    parser = argparse.ArgumentParser(prog="comfortmap", description="Hot and cold call heatmap by zone")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("table", "text heatmap of complaints by zone"), ("zones", "hot versus cold balance per zone"),
                       ("svg", "write the heatmap as an SVG image")):
        p = sub.add_parser(name, help=text)
        p.add_argument("file")
        p.add_argument("--kind", choices=("all", "hot", "cold"), default="all")
        p.add_argument("--by", choices=("weekday", "hour"), default="weekday")
        p.add_argument("--strict", action="store_true", help="exit 1 when any row was skipped")
        if name == "svg":
            p.add_argument("-o", "--output", required=True)
    args = parser.parse_args(argv)
    try:
        items, problems = load(args.file)
    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"skipped {p}", file=sys.stderr)
    chosen = select(items, args.kind)
    if args.command == "table":
        print(text_table(chosen, args.by))
    elif args.command == "zones":
        print(f"{'zone':<12} {'hot':>4} {'cold':>5} {'net':>5}")
        for zone, hot, cold, net in balance(items):
            print(f"{zone:<12} {hot:>4} {cold:>5} {net:>+5}")
    else:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(svg_heatmap(chosen, args.by, f"Comfort complaints ({args.kind}, by {args.by})"))
        print(f"{len(chosen)} complaints drawn to {args.output}")
    return 1 if (args.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())

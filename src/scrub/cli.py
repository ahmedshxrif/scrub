"""Command line: `scrub notes.txt`, or pipe text in."""

from __future__ import annotations

import argparse
import json
import sys

from .core import KINDS, redact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scrub", description="Remove personal details from text.")
    parser.add_argument("file", nargs="?", help="text file to clean (reads standard input when left out)")
    parser.add_argument("--only", help=f"comma-separated kinds to remove (default: all of {', '.join(KINDS)})")
    parser.add_argument("--names", help="file with one known name per line, removed wherever it appears")
    parser.add_argument("--mask", action="store_true", help="keep the last few characters (**** **** **** 1111) instead of a label")
    parser.add_argument("--json", action="store_true", help="print the cleaned text and what was found as JSON")
    parser.add_argument("--check", action="store_true", help="print nothing; exit 1 if anything personal was found")
    args = parser.parse_args(argv)

    try:
        text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
        names = [line.strip() for line in open(args.names, encoding="utf-8")] if args.names else None
        kinds = [kind.strip() for kind in args.only.split(",")] if args.only else None
        result = redact(text, kinds, names, mask=args.mask)
    except (OSError, ValueError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2

    if args.check:
        for kind, count in sorted(result.counts().items()):
            print(f"{count} {kind}", file=sys.stderr)
        return 1 if result.findings else 0
    if args.json:
        # The JSON never repeats what was removed: only where it was and what kind it was.
        found = [{"kind": f.kind, "start": f.start, "end": f.end} for f in result.findings]
        print(json.dumps({"text": result.text, "found": found, "counts": result.counts()}, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(result.text)
        summary = ", ".join(f"{count} {kind}" for kind, count in sorted(result.counts().items()))
        print(f"removed: {summary or 'nothing'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI bridge for the Archify Python engine."""

from __future__ import annotations

import argparse
import json
import sys

from .config import normalize_config
from .engine import analyze, generate, write_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archify-engine")
    parser.add_argument("command", choices=["analyze", "generate", "write"])
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--target-path", required=True)
    parser.add_argument("--config-json", required=True)
    parser.add_argument("--doc-type", default="archify")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = normalize_config(
        repo_root=args.repo_root,
        target_path=args.target_path,
        config=json.loads(args.config_json),
    )

    if args.command == "analyze":
        result = analyze(args.target_path, config)
    elif args.command == "generate":
        result = generate(args.target_path, config, doc_type=args.doc_type)
    else:
        result = write_document(args.target_path, config, doc_type=args.doc_type)

    sys.stdout.write(f"{json.dumps(result)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

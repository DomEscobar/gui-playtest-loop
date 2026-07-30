#!/usr/bin/env python3
"""Serve a single benchmark fixture as static files."""

from __future__ import annotations

import argparse
import http.server
import socketserver
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        required=True,
        help="Fixture id under benchmark/fixtures/<id>/",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path to gui-playtest-loop repo root",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fixture_dir = args.repo_root / "benchmark" / "fixtures" / args.fixture
    if not fixture_dir.is_dir():
        raise SystemExit(f"Fixture not found: {fixture_dir}")

    handler = lambda *h_args, **h_kwargs: http.server.SimpleHTTPRequestHandler(
        *h_args, directory=str(fixture_dir), **h_kwargs
    )
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"Serving {fixture_dir} at http://{args.host}:{args.port}/")
        httpd.serve_forever()


if __name__ == "__main__":
    main()

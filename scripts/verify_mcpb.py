#!/usr/bin/env python3
"""Verify that an MCPB bundle contains only expected runtime files."""

from __future__ import annotations

import argparse
import fnmatch
import sys
import zipfile
from pathlib import Path


FORBIDDEN_PATTERNS = (
    ".claude/*",
    ".claude-plugin/*",
    ".env",
    ".env.*",
    ".mcpregistry_*",
    "codealive-context-engine/*",
    "plugins/*",
    "smoke_test.py",
    "src/tests/*",
    "uv.lock",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an MCPB bundle")
    parser.add_argument("archive", type=Path, help="Path to the .mcpb archive")
    args = parser.parse_args()

    if not args.archive.exists():
        print(f"Archive not found: {args.archive}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(args.archive) as zf:
        members = zf.namelist()

    forbidden = sorted(
        member
        for member in members
        for pattern in FORBIDDEN_PATTERNS
        if fnmatch.fnmatch(member, pattern)
    )

    if forbidden:
        print("Forbidden files detected in MCPB bundle:", file=sys.stderr)
        for member in forbidden:
            print(f"  - {member}", file=sys.stderr)
        return 1

    print(f"MCPB bundle verified: {args.archive}")
    print(f"Checked {len(members)} archive entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Run release smoke tests with one command.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "unittest",
        "-v",
        "tests.test_backup_workflows",
        "tests.test_edit_workflows",
        "tests.test_lang",
    ]

    print("Running release smoke tests:")
    print(" ".join(command))
    result = subprocess.run(command, cwd=repo_root)
    if result.returncode == 0:
        print("Release smoke tests passed.")
    else:
        print("Release smoke tests failed.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

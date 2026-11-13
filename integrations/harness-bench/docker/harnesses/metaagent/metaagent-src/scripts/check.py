"""Run the same development checks locally and in CI."""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="also build sdist and wheel")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "mypy", "src"],
        [sys.executable, "-m", "pytest"],
    ]
    if args.build:
        commands.append(["uv", "build"])
    for command in commands:
        print("Running:", " ".join(command), flush=True)
        subprocess.run(command, cwd=root, check=True)


if __name__ == "__main__":
    main()

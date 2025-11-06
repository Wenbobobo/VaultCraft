import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parent.parent
PNPM = shutil.which("pnpm") or "pnpm"

DEFAULT_STEPS = [
    {
        "name": "hardhat",
        "cmd": [PNPM, "hardhat", "test"],
        "cwd": ROOT / "hardhat",
    },
    {
        "name": "backend",
        "cmd": ["uv", "run", "pytest", "-q"],
        "cwd": ROOT / "apps" / "backend",
    },
    {
        "name": "frontend",
        "cmd": [PNPM, "test"],
        "cwd": ROOT / "apps" / "vaultcraft-frontend",
    },
]


def run_step(name: str, cmd: List[str], cwd: Path, verbose: bool = False) -> bool:
    print(f"\n==> {name}: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=cwd, check=True, shell=False)
        print(f"<== {name}: ok")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"<== {name}: failed with exit code {exc.returncode}", file=sys.stderr)
        if verbose:
            print(f"command: {' '.join(cmd)}", file=sys.stderr)
        return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run VaultCraft test suites sequentially")
    parser.add_argument("--skip", action="append", default=[], help="Suite name(s) to skip (can repeat)")
    parser.add_argument("--only", action="append", default=[], help="If set, run only the named suite(s)")
    parser.add_argument("--verbose", action="store_true", help="Print extra diagnostics on failure")
    args = parser.parse_args(argv)

    requested = set(args.only or [])
    skipped = set(args.skip or [])

    steps = []
    for step in DEFAULT_STEPS:
        name = step["name"]
        if requested and name not in requested:
            continue
        if name in skipped:
            continue
        steps.append(step)

    if not steps:
        print("No suites selected (check --only/--skip filters).")
        return 1

    failures = []
    for step in steps:
        ok = run_step(step["name"], step["cmd"], step["cwd"], verbose=args.verbose)
        if not ok:
            failures.append(step["name"])

    if failures:
        print("\nSummary: failures ->", ", ".join(failures), file=sys.stderr)
        return 1

    print("\nSummary: all suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

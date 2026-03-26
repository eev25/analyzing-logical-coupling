# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Query a precomputed file coupling map.

Given a file path, prints associated files sorted by descending coupling
weight.  Results can be narrowed with an optional weight threshold and/or
a limit on the number of results returned.

Usage:
    uv run lookup_coupling.py <file> [--threshold FLOAT] [--top N] [--show-weights]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _find_coupling_file(start: Path) -> Path:
    """Locate the ``.logical-coupling`` file in the current git repository root.

    Uses ``git rev-parse --show-toplevel`` to find the repo root, then
    checks for a ``.logical-coupling`` file there.

    Args:
        start: Directory to run git from (typically cwd).

    Returns:
        Path to ``<git_root>/.logical-coupling``.

    Raises:
        SystemExit: If not inside a git repository, or if
            ``.logical-coupling`` does not exist in the repo root.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("error: not inside a git repository", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(result.stdout.strip())
    coupling_file = repo_root / ".logical-coupling"

    if not coupling_file.exists():
        print(
            "error: coupling data not found. "
            f"Please run 'uv run index.py {repo_root}' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    return coupling_file


def load_coupling(path: Path) -> dict[str, dict[str, float]]:
    """Load and return the coupling map from a JSON file.

    Args:
        path: Path to the JSON file produced by index.py.

    Returns:
        The parsed coupling map.

    Raises:
        SystemExit: On missing file or invalid JSON, with a descriptive
            message printed to stderr.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: coupling file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def query(
    coupling: dict[str, dict[str, float]],
    file: str,
    threshold: float | None,
    top: int | None,
) -> list[tuple[str, float]]:
    """Return associated (file, weight) pairs for *file*, filtered and sorted.

    Results are sorted by descending weight.  Threshold filtering and top-N
    slicing are applied in that order.

    Args:
        coupling: Coupling map as returned by :func:`load_coupling`.
        file: The file path to look up.
        threshold: If given, exclude pairs where weight < threshold.
        top: If given, return at most this many results.

    Returns:
        A list of ``(associated_file, weight)`` tuples.

    Raises:
        KeyError: If *file* is not present in the coupling map.
    """
    associations = coupling[file]  # raises KeyError if absent

    if threshold is not None:
        associations = {f: w for f, w in associations.items() if w >= threshold}

    results = sorted(associations.items(), key=lambda x: x[1], reverse=True)

    if top is not None:
        results = results[:top]

    return results


def _non_negative_float(value: str) -> float:
    """argparse type converter: float that must be >= 0."""
    f = float(value)
    if f < 0:
        raise argparse.ArgumentTypeError(f"threshold must be >= 0, got {f}")
    return f


def _positive_int(value: str) -> int:
    """argparse type converter: int that must be >= 1."""
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError(f"--top must be >= 1, got {n}")
    return n


def main() -> None:
    """CLI entry point: parse args, load coupling map, query, print results."""
    parser = argparse.ArgumentParser(
        prog="lookup_coupling.py",
        description=(
            "Query a precomputed file coupling map.\n\n"
            "Prints files that are historically coupled to the given file, "
            "sorted by descending coupling weight."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        help="File path to look up in the coupling map.",
    )
    parser.add_argument(
        "--threshold",
        type=_non_negative_float,
        default=None,
        metavar="FLOAT",
        help="Exclude results with weight below this value.",
    )
    parser.add_argument(
        "--top",
        type=_positive_int,
        default=None,
        metavar="N",
        help="Return only the top N results (applied after --threshold).",
    )
    parser.add_argument(
        "--show-weights",
        action="store_true",
        help="Print coupling weights alongside file paths.",
    )

    args = parser.parse_args()

    coupling_path = _find_coupling_file(Path.cwd())
    coupling = load_coupling(coupling_path)

    try:
        results = query(coupling, args.file, args.threshold, args.top)
    except KeyError:
        print(
            f"error: '{args.file}' not found in coupling map {coupling_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.show_weights:
        for associated_file, weight in results:
            print(f"{associated_file} {weight:.4f}")
    else:
        for associated_file, _ in results:
            print(associated_file)


if __name__ == "__main__":
    main()

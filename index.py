# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compute logical coupling between files in a Git repository.

Logical coupling measures how frequently pairs of files are modified
together in the same commits — a proxy for hidden architectural dependencies.

For every commit that touches N files (1 < N < 50), each unordered pair
(A, B) receives an increment of 1 / (N - 1). Large commits contribute less
per pair, keeping noisy "change everything" commits from dominating the
results.

Usage:
    uv run index.py /path/to/repository
"""

import argparse
import itertools
import json
import subprocess
from collections import defaultdict
from pathlib import Path

# File suffixes treated as binary/non-source — excluded from all coupling.
BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".tiff",
        ".webp",
        ".svg",
        # Python bytecode / compiled
        ".pyc",
        ".pyo",
        ".pyd",
        # Native objects and shared libraries
        ".o",
        ".a",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".lib",
        ".elf",
        ".bin",
        # Archives and packages
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".zst",
        ".7z",
        ".rar",
        ".whl",
        ".egg",
        # Documents and media
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".mp3",
        ".mp4",
        ".wav",
        ".ogg",
        ".flac",
        # Fonts
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
    }
)


def _filter_binary(files: list[str]) -> set[str]:
    """Return *files* with binary entries removed.

    A file is considered binary when its suffix (lowercased) appears in
    BINARY_EXTENSIONS.  Files with no suffix (e.g. ``Makefile``) are kept.
    """
    return {f for f in files if Path(f).suffix.lower() not in BINARY_EXTENSIONS}


def extract_commit_file_sets(repo_path: Path) -> list[set[str]]:
    """Run a single git-log call and return one file-set per commit.

    Executes::

        git log --name-only --pretty=format:COMMIT:%h

    in *repo_path* and parses the output into a list of sets.  Each set
    contains the source filenames (relative to the repo root) touched by
    one commit, with binary files already removed.

    Commits that produce an empty set (e.g. merge commits with no file
    changes) are included; callers are responsible for filtering by
    cardinality.

    Args:
        repo_path: Path to the root of the git repository.

    Returns:
        A list of sets, one per commit, newest-first (git log order).

    Raises:
        subprocess.CalledProcessError: If git exits non-zero.
        FileNotFoundError: If git is not on PATH.
    """
    result = subprocess.run(
        ["git", "log", "--name-only", "--pretty=format:COMMIT:%h"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )

    commit_file_sets: list[set[str]] = []
    current_files: list[str] = []
    in_commit = False

    for line in result.stdout.splitlines():
        if line.startswith("COMMIT:"):
            if in_commit:
                commit_file_sets.append(_filter_binary(current_files))
            current_files = []
            in_commit = True
        elif line:
            # Non-empty, non-COMMIT line is a filename.
            current_files.append(line)
        # Blank lines are separators — silently ignored.

    if in_commit:
        # Flush the final commit (no trailing COMMIT: line follows it).
        commit_file_sets.append(_filter_binary(current_files))

    return commit_file_sets


def compute_coupling(
    commit_file_sets: list[set[str]],
) -> dict[str, dict[str, float]]:
    """Compute pairwise logical-coupling weights from commit file sets.

    For every unordered pair (A, B) that co-appear in a commit of size N,
    both ``W[A][B]`` and ``W[B][A]`` are incremented by ``1 / (N - 1)``.

    Commits where ``N <= 1`` or ``N >= 50`` are skipped entirely.

    The weight formula ``1 / (N - 1)`` penalises mega-commits: a 2-file
    commit contributes weight 1.0 to that pair, while a 10-file commit
    contributes only ~0.111 per pair.

    Args:
        commit_file_sets: As returned by :func:`extract_commit_file_sets`.

    Returns:
        A two-level dict ``result[file_a][file_b] = cumulative_weight``.
        The structure is symmetric: ``result[a][b] == result[b][a]``.
        Files that never co-appear in a qualifying commit are absent.
    """
    coupling: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for file_set in commit_file_sets:
        n = len(file_set)
        if n <= 1 or n >= 50:
            continue

        weight = 1.0 / (n - 1)
        # sorted() makes iteration order deterministic across Python runs.
        for file_a, file_b in itertools.combinations(sorted(file_set), 2):
            coupling[file_a][file_b] += weight
            coupling[file_b][file_a] += weight

    # Convert defaultdicts to plain dicts for clean JSON serialisation.
    return {k: dict(v) for k, v in coupling.items()}


def normalize_coupling(
    coupling: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Row-normalize coupling weights so each file's weights sum to 1.

    For each file A:
        total = sum(W(A, B) for all B)
        W_norm(A, B) = W(A, B) / total

    This converts raw accumulated weights into relative coupling strengths,
    interpretable as: "given file A changes, how likely is file B to also
    change?"

    Files with a total weight of zero are excluded from the output
    (defensive; should not occur given :func:`compute_coupling`'s output).

    Args:
        coupling: Raw weights as returned by :func:`compute_coupling`.

    Returns:
        A new two-level dict with the same structure, values in [0, 1],
        where each row sums to 1.0.
    """
    return {
        file_a: {
            file_b: w / total
            for file_b, w in neighbors.items()
        }
        for file_a, neighbors in coupling.items()
        if (total := sum(neighbors.values())) > 0
    }


def main() -> None:
    """CLI entry point: parse args, orchestrate, emit JSON to stdout."""
    parser = argparse.ArgumentParser(
        prog="index.py",
        description=(
            "Compute logical coupling between files in a Git repository.\n\n"
            "For every pair of files (A, B), outputs a coupling weight "
            "representing how frequently both files are modified in the same "
            "commits. Higher weight = stronger coupling."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Path to the root of the git repository to analyse.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write JSON output to FILE instead of stdout.",
    )

    args = parser.parse_args()
    repo_path: Path = args.repo_path.resolve()

    if not repo_path.is_dir():
        parser.error(f"repo_path does not exist or is not a directory: {repo_path}")

    try:
        commit_file_sets = extract_commit_file_sets(repo_path)
    except FileNotFoundError:
        parser.error("git executable not found on PATH.")
    except subprocess.CalledProcessError as exc:
        parser.error(
            f"git log failed (exit code {exc.returncode}).\n"
            f"Is '{repo_path}' a valid git repository?\n"
            f"stderr: {exc.stderr.strip()}"
        )

    coupling = normalize_coupling(compute_coupling(commit_file_sets))

    # Sort outer keys alphabetically; sort each file's neighbours by weight
    # descending so the strongest couplings appear first.
    sorted_coupling = {
        file_a: dict(
            sorted(neighbors.items(), key=lambda kv: kv[1], reverse=True)
        )
        for file_a, neighbors in sorted(coupling.items())
    }

    output_path: Path = args.output if args.output is not None else Path(f"{repo_path.name}.json")
    output_path.write_text(json.dumps(sorted_coupling, indent=2), encoding="utf-8")
    print(f"Wrote coupling data to {output_path}")


if __name__ == "__main__":
    main()

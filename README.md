# Logical Coupling

Discover hidden dependencies in a Git repository by analyzing which files are most frequently modified together.

## What is logical coupling?

Logical coupling measures co-change frequency across commits. When two files are repeatedly edited in the same commit, they are likely coupled — even if no import or call-site connects them in the code. This makes it a useful signal for identifying implicit dependencies, test gaps, and refactoring risk.

## How it works

For every non-merge commit touching N files (2 ≤ N < 50), each unordered pair (A, B) receives a weight increment of `1 / (N - 1)`. Large commits contribute less per pair, reducing noise from "change everything" commits. Weights are then max-normalized per file so the strongest relationship is always `1.0` and all others fall in `[0, 1]`.

File renames are tracked across history using `git log --name-status -M`, so coupling accumulated under an old name is merged into the current canonical path.

## Usage

Run from inside any Git repository:

```bash
uv run src/coupling.py <file>
```

Coupling data is indexed automatically on first use and cached in `.logical-coupling` at the repo root.

### Options

| Flag | Description |
|------|-------------|
| `--top N` | Return only the top N strongest couplings |
| `--threshold FLOAT` | Exclude results below this weight (0–1) |
| `--show-weights` | Print weights alongside file paths |

### Examples

```bash
# Find all files coupled to src/auth.py
uv run src/coupling.py src/auth.py

# Top 5 with weights
uv run src/coupling.py src/auth.py --top 5 --show-weights

# Strong couplings only
uv run src/coupling.py src/auth.py --threshold 0.5
```

## Data file

Coupling data is stored as JSON in `.logical-coupling` at the repository root. To regenerate it manually:

```bash
uv run src/index.py
```

## Claude Skill

This tool ships with a Claude Skill (`SKILL.md`). When installed, Claude can invoke `src/coupling.py` automatically in response to questions about file dependencies and co-change patterns.

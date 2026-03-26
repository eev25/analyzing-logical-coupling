---
name: analyzing-logical-coupling
description: Identifies files that frequently change together in a Git repository by analyzing commit history. Use when the user wants to find related files, understand hidden dependencies, discover what else might need updating when modifying a file, or explore logical coupling in a codebase.
---

## Quick start

Run from inside the target git repository:

```bash
uv run src/coupling.py <file>
```

Coupling data is generated automatically on first use.

## CLI reference

```
uv run src/coupling.py <file> [--threshold FLOAT] [--top N] [--show-weights]
```

## Examples

All files coupled to `src/auth.py`:
```bash
uv run src/coupling.py src/auth.py
```

Top 5 most strongly coupled files with weights:
```bash
uv run src/coupling.py src/auth.py --top 5 --show-weights
```

Only files with coupling strength ≥ 0.5:
```bash
uv run src/coupling.py src/auth.py --threshold 0.5
```

## Interpreting results

Weights are max-normalized: the strongest coupling for any given file is `1.0`, all others fall in `[0, 1]`. Higher weight means the two files change together more consistently across the repository's history.

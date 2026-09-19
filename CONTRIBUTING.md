# Contributing to repohealth

## Setup

```bash
python -m pip install -e .
```

Requires Python 3.10+.

## Running tests

```bash
python -m pytest tests/ -v
```

## Release process

1. Bump `version` in `pyproject.toml`.
2. Commit the change.
3. Tag the release: `git tag v0.1.0 && git push --tags`

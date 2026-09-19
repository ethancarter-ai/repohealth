# repohealth

Repository health checker that scores local git repos across docs, metadata, git hygiene, and freshness signals.

## About

`repohealth` inspects a local repository and produces a concise health report. It evaluates documentation, project metadata, git hygiene, repository freshness, and test/CI coverage. Use it to quickly assess how well a project is maintained, or to enforce minimum health standards in CI/local checks.

## Features

- Text or JSON output for human review or automation.
- Five health categories with weighted scores.
- Fast local-only checks; no network access required.
- Single-module CLI with editable-install entrypoint.

## Installation

```bash
python -m pip install -e .
```

Requires Python 3.10+.

## Usage

```bash
repohealth /path/to/repo
repohealth /path/to/repo --json
repohealth /path/to/repo --fail-below 10
```

Exit codes:
- `0` when score is at or above `--fail-below`.
- `1` when the target path is invalid.
- `2` when score is below `--fail-below`.

## Project structure

```
repohealth/
  README.md
  pyproject.toml
  repohealth.py
  tests/
    test_repohealth.py
```

## Tags / keywords

cli, python, repo-health, git, ci

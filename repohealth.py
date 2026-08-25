"""repohealth - Repository health checker CLI.

Scores local repos across docs, metadata, git hygiene, and freshness signals.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CategoryResult:
    name: str
    score: int = 0
    max_score: int = 0
    checks: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class RepoReport:
    repo: str
    categories: list[CategoryResult] = field(default_factory=list)
    score: int = 0


def _run(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        out = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        return out.returncode == 0, out.stdout + "\n" + out.stderr
    except (subprocess.SubprocessError, OSError) as exc:
        return False, str(exc)


def _has_file(repo: Path, *names: str) -> bool:
    return any((repo / name).exists() for name in names)


def _read_first(repo: Path, *names: str) -> str | None:
    for name in names:
        candidate = repo / name
        if candidate.exists():
            try:
                return candidate.read_text(errors="replace")[:5000]
            except OSError:
                return None
    return None


def score_docs(repo: Path) -> CategoryResult:
    result = CategoryResult(name="Docs", max_score=5)
    checks: list[str] = []
    issues: list[str] = []
    score = 0

    readme = _read_first(repo, "README.md", "readme.md")
    if readme:
        score += 2
        checks.append("README present")
        heading = readme.splitlines()[0].strip()
        if heading.startswith("#") and len(heading) > 2:
            score += 1
            checks.append("README has title")
        else:
            issues.append("README title missing or empty")
    else:
        issues.append("README missing")

    if _has_file(repo, "docs", "doc", "docs/README.md"):
        score += 1
        checks.append("docs directory present")
    else:
        issues.append("No docs directory")

    if _has_file(repo, "CONTRIBUTING.md", "contributing.md"):
        score += 1
        checks.append("CONTRIBUTING present")
    else:
        issues.append("CONTRIBUTING missing")

    result.score = min(score, result.max_score)
    result.checks = checks
    result.issues = issues
    return result


def score_metadata(repo: Path) -> CategoryResult:
    result = CategoryResult(name="Metadata", max_score=5)
    checks: list[str] = []
    issues: list[str] = []
    score = 0

    metadata_file = None
    metadata_format = None
    if (repo / "pyproject.toml").exists():
        metadata_file = repo / "pyproject.toml"
        metadata_format = "pyproject"
    elif (repo / "package.json").exists():
        metadata_file = repo / "package.json"
        metadata_format = "package"
    elif (repo / "setup.py").exists():
        metadata_file = repo / "setup.py"
        metadata_format = "setuptools"

    if metadata_file:
        score += 2
        checks.append(f"Project metadata present ({metadata_format})")
        try:
            text = metadata_file.read_text(errors="replace")
        except OSError:
            text = ""
        if metadata_format == "pyproject":
            if all(part in text for part in ["name", "version", "description"]):
                score += 1
                checks.append("pyproject name/version/description present")
            else:
                issues.append("Incomplete pyproject metadata")
        elif metadata_format == "package":
            if '"name"' in text and '"version"' in text:
                score += 1
                checks.append("package.json name+version present")
            else:
                issues.append("Incomplete package metadata")
        else:
            checks.append("setup.py present")
    else:
        issues.append("No project metadata file")

    if _has_file(repo, "LICENSE", "LICENCE", "license.txt"):
        score += 1
        checks.append("License file present")
    else:
        issues.append("License file missing")

    if _has_file(repo, ".gitignore"):
        score += 1
        checks.append(".gitignore present")
    else:
        issues.append(".gitignore missing")

    result.score = min(score, result.max_score)
    result.checks = checks
    result.issues = issues
    return result


def score_git_hygiene(repo: Path) -> CategoryResult:
    result = CategoryResult(name="Git hygiene", max_score=5)
    checks: list[str] = []
    issues: list[str] = []
    score = 0

    ok, out = _run(["git", "rev-parse", "--is-inside-work-tree"], repo)
    if not ok:
        result.issues = ["Not a git repository"]
        return result
    checks.append("Git repository detected")

    ok, out = _run(["git", "status", "--porcelain=v1"], repo)
    if ok and out.strip():
        issues.append(f"Dirty working tree: {len([line for line in out.splitlines() if line.strip()])} entries")
    else:
        score += 2
        checks.append("Working tree clean")

    ok, out = _run(["git", "tag"], repo)
    if ok and out.strip():
        score += 1
        checks.append("Tags present")
    else:
        issues.append("No tags")

    ok, out = _run(["git", "branch", "--show-current"], repo)
    if ok and out.strip() in {"main", "master"}:
        score += 1
        checks.append(f"Default branch ({out.strip()})")
    else:
        issues.append("Default branch is not main/master")

    ok, out = _run(["git", "log", "-1", "--format=%h %s"], repo)
    if ok and out.strip():
        score += 1
        checks.append("At least one commit")
    else:
        issues.append("No commits")

    result.score = min(score, result.max_score)
    result.checks = checks
    result.issues = issues
    return result


def score_freshness(repo: Path) -> CategoryResult:
    result = CategoryResult(name="Freshness", max_score=5)
    checks: list[str] = []
    issues: list[str] = []
    score = 0

    ok, out = _run(["git", "log", "-1", "--format=%ct"], repo)
    if ok:
        latest = out.strip()
        if latest.isdigit():
            timestamp = datetime.datetime.fromtimestamp(int(latest))
            now = datetime.datetime.now()
            days = (now - timestamp).days
            if days <= 7:
                score += 2
                checks.append(f"Last commit within 7 days ({days}d)")
            elif days <= 30:
                score += 1
                checks.append(f"Last commit within 30 days ({days}d)")
            else:
                issues.append(f"Last commit is stale: {days}d ago")
        else:
            issues.append("Could not parse commit timestamp")
    else:
        issues.append("Could not read latest commit")

    ok, out = _run(["git", "log", "--oneline"], repo)
    if ok:
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        if lines:
            score += 1
            checks.append("Has commit history")

    contributors: set[str] = set()
    ok, out = _run(["git", "log", "--format=%ae"], repo)
    if ok:
        for line in out.splitlines():
            line = line.strip()
            if line:
                contributors.add(line)
    if contributors:
        score += 1
        checks.append(f"Contributors detected: {len(contributors)}")
    else:
        issues.append("No contributor emails found")

    result.score = min(score, result.max_score)
    result.checks = checks
    result.issues = issues
    return result


def score_test_coverage(repo: Path) -> CategoryResult:
    result = CategoryResult(name="Tests", max_score=5)
    checks: list[str] = []
    issues: list[str] = []
    score = 0

    has_tests = _has_file(repo, "tests") or any(repo.glob("test_*.py")) or any(repo.glob("*_test.py"))
    if has_tests:
        score += 2
        checks.append("Tests directory or files detected")
    else:
        issues.append("No tests detected")

    if _has_file(repo, "pytest.ini", "pyproject.toml", "tox.ini"):
        score += 1
        checks.append("Test configuration present")
    else:
        issues.append("No test configuration")

    if (repo / ".github" / "workflows").exists():
        score += 1
        checks.append("CI configuration present")
    else:
        issues.append("No CI workflows")

    if _has_file(repo, "Makefile", "justfile", "Taskfile.yml"):
        score += 1
        checks.append("Task runner configuration present")
    else:
        issues.append("No task runner configuration")

    result.score = min(score, result.max_score)
    result.checks = checks
    result.issues = issues
    return result


def evaluate(repo: Path) -> RepoReport:
    repo = repo.expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo}")
    if not repo.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo}")

    categories = [
        score_docs(repo),
        score_metadata(repo),
        score_git_hygiene(repo),
        score_freshness(repo),
        score_test_coverage(repo),
    ]
    total = sum(category.score for category in categories)
    return RepoReport(repo=str(repo), categories=categories, score=total)


def render_text(report: RepoReport) -> str:
    lines = [
        f"repohealth: {report.repo}",
        f"Health score: {report.score}/{sum(c.max_score for c in report.categories)}",
        "",
    ]
    for category in report.categories:
        lines.append(f"## {category.name}: {category.score}/{category.max_score}")
        for check in category.checks:
            lines.append(f"- [x] {check}")
        for issue in category.issues:
            lines.append(f"- [ ] {issue}")
        lines.append("")
    return "\n".join(lines)


def render_json(report: RepoReport) -> str:
    payload = {
        "repo": report.repo,
        "score": report.score,
        "max_score": sum(category.max_score for category in report.categories),
        "categories": [
            {
                "name": category.name,
                "score": category.score,
                "max_score": category.max_score,
                "checks": list(category.checks),
                "issues": list(category.issues),
            }
            for category in report.categories
        ],
    }
    return json.dumps(payload, indent=2)


class _HelpArgs:
    help_requested = True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace | None | _HelpArgs:
    parser = argparse.ArgumentParser(description="Evaluate repository health from the local filesystem.")
    parser.add_argument("repo", type=Path, help="Path to a local git repository")
    parser.add_argument("--json", action="store_true", help="Emit JSON output instead of text")
    parser.add_argument("--fail-below", type=int, default=0, help="Exit with nonzero status when score is below this threshold")
    try:
        return parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            return _HelpArgs()
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if isinstance(args, _HelpArgs) or args is None:
        return 0

    try:
        report = evaluate(args.repo)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(render_json(report))
    else:
        print(render_text(report))

    if report.score < args.fail_below:
        return 2
    return 0

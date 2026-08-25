from pathlib import Path

import pytest

from repohealth import CategoryResult, evaluate, main, render_json, render_text


def test_evaluate_missing_path():
    with pytest.raises(FileNotFoundError):
        evaluate(Path("/tmp/missing-repohealth-xyz"))


def test_evaluate_not_a_directory(tmp_path: Path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")
    with pytest.raises(NotADirectoryError):
        evaluate(file_path)


def test_text_report(tmp_path: Path):
    report = evaluate(tmp_path)
    output = render_text(report)
    assert output.startswith("repohealth:")
    assert "Health score:" in output


def test_json_report(tmp_path: Path):
    report = evaluate(tmp_path)
    output = render_json(report)
    assert output.startswith("{")
    assert "categories" in output


def test_main_invalid_path():
    assert main(["/tmp/missing-repohealth-xyz"]) == 1


def test_main_help_exit_zero():
    assert main(["--help"]) == 0


def test_main_json_output(tmp_path: Path):
    assert main([str(tmp_path), "--json"]) == 0


def test_fail_below(tmp_path: Path):
    assert main([str(tmp_path), "--fail-below", "100"]) == 2


def test_category_result_defaults():
    result = CategoryResult(name="Test")
    assert result.checks == []
    assert result.issues == []
    assert result.score == 0
    assert result.max_score == 0

"""CLI tests for `--check`: exit codes and the TOML baseline fallback."""

import pytest

from eval.check import THRESHOLDS_PATH
from eval.results import write_results
from eval.test_check import OVERALL, _files, _rows
from scripts.run_eval import main


def _argv(tmp_path, baseline, *extra: str) -> list[str]:
    return [
        "run_eval.py",
        "--check",
        "--results",
        str(tmp_path),
        "--baseline",
        str(baseline),
        "--thresholds",
        str(THRESHOLDS_PATH),
        *extra,
    ]


def test_cli_returns_zero_on_pass(tmp_path, monkeypatch):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    monkeypatch.setattr("sys.argv", _argv(results, baseline))
    assert main() == 0


def test_cli_returns_one_on_fail(tmp_path, monkeypatch):
    results, baseline = _files(tmp_path, OVERALL, dict(OVERALL, hit_at_k=0.60))
    monkeypatch.setattr("sys.argv", _argv(results, baseline))
    assert main() == 1


def test_cli_uses_the_toml_baseline_when_omitted(tmp_path, monkeypatch):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    text = THRESHOLDS_PATH.read_text(encoding="utf-8").replace(
        'baseline = "eval/results/baseline.csv"', f'baseline = "{baseline}"'
    )
    thresholds = tmp_path / "thresholds.toml"
    thresholds.write_text(text, encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_eval.py",
            "--check",
            "--results",
            str(results),
            "--thresholds",
            str(thresholds),
        ],
    )
    assert main() == 0


def test_cli_latest_pins_a_specific_run(tmp_path, monkeypatch):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    passing = results / "20260101T000000Z.csv"
    failing = results / "20260102T000000Z.csv"
    write_results(failing, _rows("failing", dict(OVERALL, hit_at_k=0.60)))

    monkeypatch.setattr("sys.argv", _argv(results, baseline, "--latest", str(passing)))
    assert main() == 0

    monkeypatch.setattr("sys.argv", _argv(results, baseline, "--latest", str(failing)))
    assert main() == 1


def test_cli_rejects_check_and_write_baseline_together(monkeypatch):
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--check", "--write-baseline"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_cli_rejects_latest_without_check(monkeypatch):
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--latest", "run.csv"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2

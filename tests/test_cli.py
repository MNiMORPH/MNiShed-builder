"""End-to-end CLI test against a bundled example config."""

from pathlib import Path

from mnished_builder import cli
from mnished_builder.cli import main

REPO = Path(__file__).resolve().parents[1]
CROW_WING = REPO / "watershed_configs" / "crow_wing_river.yml"


class _FakeReport:
    """Stand-in for mnished.io.ValidationReport (avoids needing MNiShed here)."""

    def __init__(self, errors=(), warnings=()):
        self.errors = list(errors)
        self.warnings = list(warnings)

    @property
    def ok(self):
        return not self.errors

    def __str__(self):
        return "fake validation report"


def test_new_builds_full_study(tmp_path, capsys):
    rc = main(["new", "--config", str(CROW_WING), "--out", str(tmp_path)])
    assert rc == 0

    study = tmp_path / "crow_wing_river"
    # 12 decades, 1911-1920 .. 2021-2030 (first_year 1911, last_year 2021)
    decades = sorted(p.name for p in (study / "decades").iterdir())
    assert decades[0] == "1911-1920" and decades[-1] == "2021-2030"
    assert len(decades) == 12

    # pipeline scripts + slurm + root helpers all present
    fdir = tmp_path / "forcing" / "crow_wing_river"
    assert (fdir / "crow_wing_river_pipeline.sh").is_file()
    assert (tmp_path / "slurm" / "pipeline_job.sh").is_file()
    assert (tmp_path / "status.py").is_file()

    out = capsys.readouterr().out
    assert "Built MNiShed study for Crow Wing River at Nimrod" in out


def test_bad_config_returns_nonzero(tmp_path, capsys):
    bad = tmp_path / "bad.yml"
    bad.write_text("name: x\n")          # missing required fields
    rc = main(["new", "--config", str(bad), "--out", str(tmp_path)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


# --------------------------------------------------------------------------
# `validate` subcommand (MNiShed is an optional dependency; monkeypatched here)
# --------------------------------------------------------------------------

def _patch_validator(monkeypatch, report):
    monkeypatch.setattr(cli, "_resolve_validate_inputs",
                        lambda: (lambda config: report))


def test_validate_clean_exits_zero(monkeypatch, capsys):
    _patch_validator(monkeypatch, _FakeReport())
    assert cli.main(["validate", "--config", "x.yml"]) == 0
    assert "fake validation report" in capsys.readouterr().out


def test_validate_errors_exit_one(monkeypatch):
    _patch_validator(monkeypatch, _FakeReport(errors=["missing column"]))
    assert cli.main(["validate", "--config", "x.yml"]) == 1


def test_validate_strict_promotes_warnings(monkeypatch):
    _patch_validator(monkeypatch, _FakeReport(warnings=["snowpack disabled"]))
    assert cli.main(["validate", "--config", "x.yml"]) == 0           # lenient
    assert cli.main(["validate", "--config", "x.yml", "--strict"]) == 1


def test_validate_without_mnished_exits_two(monkeypatch, capsys):
    def _missing():
        raise RuntimeError("install it with `pip install mnished`")
    monkeypatch.setattr(cli, "_resolve_validate_inputs", _missing)
    assert cli.main(["validate", "--config", "x.yml"]) == 2
    assert "pip install mnished" in capsys.readouterr().err


def test_generated_run_sh_has_contract_preflight(tmp_path):
    cli.main(["new", "--config", str(CROW_WING), "--out", str(tmp_path)])
    run_sh = (tmp_path / "crow_wing_river" / "run.sh").read_text()
    assert "validate_inputs" in run_sh

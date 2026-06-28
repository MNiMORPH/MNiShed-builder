"""End-to-end CLI test against a bundled example config."""

from pathlib import Path

from mnished_builder.cli import main

REPO = Path(__file__).resolve().parents[1]
CROW_WING = REPO / "watershed_configs" / "crow_wing_river.yml"


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

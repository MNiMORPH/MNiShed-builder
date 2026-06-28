"""Tests for the generated GRASS forcing-data pipeline scripts."""

import os
import textwrap

from mnished_builder.config import load_config
from mnished_builder.grass_pipeline import write_pipeline_scripts

CONFIG = """\
    name: demo_river
    gauge: "05244000"
    title: "Demo River"
    grass:
      location: DemoLoc
      epsg: 26915
    forcing:
      start: '1905-01-01'
      end:   '2024-12-31'
      csv_name: demo_forcing.csv
      config_name: demo_config.yml
    decades: {first_year: 1991, last_year: 2001}
    scaffold:
      conda_env: my-grass-env
    initial_params: {}
"""


def _cfg(tmp_path):
    p = tmp_path / "ws.yml"
    p.write_text(textwrap.dedent(CONFIG))
    return load_config(p)


def test_three_pipeline_scripts_written_and_executable(tmp_path):
    cfg = _cfg(tmp_path)
    out = tmp_path / "out"
    ed = write_pipeline_scripts(cfg, out)
    assert ed == out / "forcing" / "demo_river"
    for f in ("demo_river_pipeline_download.sh", "demo_river_pipeline_compute.sh",
              "demo_river_pipeline.sh"):
        path = ed / f
        assert path.is_file() and os.access(path, os.X_OK)


def test_download_script_calls_addons_with_config_values(tmp_path):
    cfg = _cfg(tmp_path)
    out = tmp_path / "out"
    write_pipeline_scripts(cfg, out)
    text = (out / "forcing" / "demo_river" / "demo_river_pipeline_download.sh").read_text()
    assert "v.in.waterdata" in text and "v.in.ghcn" in text
    assert "GAUGE=05244000" in text
    assert "START=1905-01-01" in text and "END=2024-12-31" in text
    assert "EPSG:26915" in text
    assert "grassdata/DemoLoc/PERMANENT" in text
    assert "basins=demo_river_basin" in text


def test_compute_script_calls_interp_and_export(tmp_path):
    cfg = _cfg(tmp_path)
    out = tmp_path / "out"
    write_pipeline_scripts(cfg, out)
    text = (out / "forcing" / "demo_river" / "demo_river_pipeline_compute.sh").read_text()
    assert "v.interp.timeseries" in text and "db.out.hydroravens" in text
    assert "demo_forcing.csv" in text
    assert "demo_config.yml" in text                  # copied to study dir


def test_slurm_job_written_with_conda_env_and_subdir(tmp_path):
    cfg = _cfg(tmp_path)
    out = tmp_path / "out"
    write_pipeline_scripts(cfg, out)
    slurm = (out / "slurm" / "pipeline_job.sh").read_text()
    assert "conda activate my-grass-env" in slurm
    assert "MNISHED_BUILDER_" not in slurm
    # the compute-script path uses the configured output subdir, not the stale one
    assert "/forcing/${WATERSHED}/" in slurm
    assert "db.out.hydroravens/examples" not in slurm


def test_no_unsubstituted_placeholders(tmp_path):
    cfg = _cfg(tmp_path)
    out = tmp_path / "out"
    write_pipeline_scripts(cfg, out)
    for path in (out / "forcing" / "demo_river").glob("*.sh"):
        assert "MNISHED_BUILDER_" not in path.read_text()

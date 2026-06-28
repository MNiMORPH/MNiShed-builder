"""Tests for study-directory scaffolding."""

import os
import textwrap

import pytest

from mnished_builder.config import load_config
from mnished_builder.scaffold import render_params, scaffold_study

CONFIG = """\
    name: demo_river
    gauge: "05244000"
    title: "Demo River at Somewhere"
    forcing:
      start: '1905-01-01'
      end:   '2024-12-31'
      config_name: demo_config.yml
    decades:
      first_year: 1991
      last_year:  2011
    scaffold:
      driver_python: /opt/conda/envs/dakota/bin/python
    initial_params:
      log__t_recession_soil:         4.0
      log__t_recession_intermediate: 1.0
      log__t_recession_deep:         3.5
      f_exfiltration_soil:           0.5
      f_exfiltration_intermediate:   0.1
      PDD_melt_factor:               5.0
      recession_b_soil:              3.0
      log__fdd_threshold:            2.0
"""


def _cfg(tmp_path, text=CONFIG, name="ws.yml"):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text))
    return load_config(p)


def test_scaffold_creates_decade_tree(tmp_path):
    cfg = _cfg(tmp_path)
    study = scaffold_study(cfg, tmp_path / "out")
    assert study == tmp_path / "out" / "demo_river"
    decades = sorted(p.name for p in (study / "decades").iterdir())
    assert decades == ["1991-2000", "2001-2010", "2011-2020"]
    for d in decades:
        assert (study / "decades" / d / "params.yml").is_file()


def test_params_substitution_and_window(tmp_path):
    cfg = _cfg(tmp_path)
    study = scaffold_study(cfg, tmp_path / "out")
    text = (study / "decades" / "2001-2010" / "params.yml").read_text()
    assert "decade_start:          '2001-01-01'" in text
    assert "decade_end:            '2010-12-31'" in text
    assert "config_template:       'demo_config.yml'" in text
    assert "initial: 4.0" in text                    # warm-start value substituted
    assert "{" not in text and "}" not in text       # no leftover placeholders


def test_title_and_name_substituted_in_scripts(tmp_path):
    cfg = _cfg(tmp_path)
    study = scaffold_study(cfg, tmp_path / "out")
    for script in ("plot_best.py", "generate_dakota_in.py", "summarize.py"):
        text = (study / script).read_text()
        assert "WATERSHED_TITLE" not in text and "WATERSHED_NAME" not in text


def test_driver_python_substituted_and_executable(tmp_path):
    cfg = _cfg(tmp_path)
    study = scaffold_study(cfg, tmp_path / "out")
    rd = study / "run_driver.sh"
    assert "/opt/conda/envs/dakota/bin/python driver.py" in rd.read_text()
    assert "MNISHED_BUILDER_" not in rd.read_text()
    assert os.access(rd, os.X_OK)                     # executable bit set


def test_root_helpers_written_once(tmp_path):
    cfg = _cfg(tmp_path)
    out = tmp_path / "out"
    scaffold_study(cfg, out)
    assert (out / "status.py").is_file()
    assert (out / "summarize_backbone.py").is_file()


def test_missing_initial_param_raises_helpful_error(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.initial_params.pop("recession_b_soil")        # template still references it
    with pytest.raises(KeyError, match="recession_b_soil"):
        render_params(cfg, "2001-01-01", "2010-12-31", "2001-2010")


def test_custom_span(tmp_path):
    cfg = _cfg(tmp_path, CONFIG.replace("first_year: 1991\n      last_year:  2011",
                                        "first_year: 2000\n      last_year:  2009\n      span: 5"))
    study = scaffold_study(cfg, tmp_path / "out")
    decades = sorted(p.name for p in (study / "decades").iterdir())
    assert decades == ["2000-2004", "2005-2009"]

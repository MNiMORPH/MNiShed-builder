"""Tests for watershed-config loading and validation."""

import textwrap

import pytest

from mnished_builder.config import ConfigError, load_config


def _write(tmp_path, text, name="ws.yml"):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text))
    return p


MINIMAL = """\
    name: test_river
    gauge: "01234567"
    title: "Test River"
    forcing:
      start: '1990-01-01'
      end:   '2000-12-31'
    decades:
      first_year: 1991
      last_year:  2011
    initial_params: {}
"""


def test_minimal_config_loads_with_defaults(tmp_path):
    cfg = load_config(_write(tmp_path, MINIMAL))
    assert cfg.name == "test_river"
    assert cfg.gauge == "01234567"          # coerced to str even if YAML-numeric
    assert cfg.grass_epsg == 32615           # default
    assert cfg.grass_location == "TestRiver"  # derived from name
    assert cfg.forcing_csv == "test_river_forcing.csv"
    assert cfg.config_name == "test_river_config.yml"
    assert cfg.decade_span == 10
    assert cfg.driver_python == "python"
    assert list(cfg.decade_starts()) == [1991, 2001, 2011]


def test_grass_block_overrides(tmp_path):
    cfg = load_config(_write(tmp_path, """\
        name: r
        gauge: "1"
        title: "R"
        grass: {location: MyLoc, epsg: 26915}
        forcing: {start: '2000-01-01', end: '2010-12-31'}
        decades: {first_year: 2000, last_year: 2009}
        initial_params: {}
    """))
    assert cfg.grass_location == "MyLoc" and cfg.grass_epsg == 26915


def test_legacy_flat_grass_keys(tmp_path):
    cfg = load_config(_write(tmp_path, """\
        name: r
        gauge: "1"
        title: "R"
        grass_location: LegacyLoc
        grass_epsg: 32614
        forcing: {start: '2000-01-01', end: '2010-12-31'}
        decades: {first_year: 2000, last_year: 2009}
        initial_params: {}
    """))
    assert cfg.grass_location == "LegacyLoc" and cfg.grass_epsg == 32614


def test_custom_decade_span(tmp_path):
    cfg = load_config(_write(tmp_path, """\
        name: r
        gauge: "1"
        title: "R"
        forcing: {start: '2000-01-01', end: '2010-12-31'}
        decades: {first_year: 2000, last_year: 2009, span: 5}
        initial_params: {}
    """, name="span5.yml"))
    assert cfg.decade_span == 5
    assert list(cfg.decade_starts()) == [2000, 2005]


@pytest.mark.parametrize("bad,match", [
    ("name: r\ngauge: '1'\ntitle: T\ndecades: {first_year: 1, last_year: 2}\ninitial_params: {}",
     "forcing"),
    ("name: r\ngauge: '1'\ntitle: T\nforcing: {start: x, end: '2000-12-31'}\n"
     "decades: {first_year: 1, last_year: 2}\ninitial_params: {}", "YYYY-MM-DD"),
    ("name: r\ngauge: '1'\ntitle: T\nforcing: {start: '2001-01-01', end: '2000-12-31'}\n"
     "decades: {first_year: 1, last_year: 2}\ninitial_params: {}", "precedes"),
    ("name: r\ngauge: '1'\ntitle: T\nforcing: {start: '2000-01-01', end: '2010-12-31'}\n"
     "decades: {first_year: 2010, last_year: 2000}\ninitial_params: {}", "last_year"),
])
def test_invalid_configs_raise(tmp_path, bad, match):
    with pytest.raises(ConfigError, match=match):
        load_config(_write(tmp_path, bad, name="bad.yml"))


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yml")

"""
Watershed-config loading and validation.

A watershed config is a small YAML file naming a USGS gauge, a projection, a
forcing period, and warm-start parameter values. :func:`load_config` reads it
into a validated :class:`WatershedConfig`, normalising the couple of legacy key
spellings that accumulated in the study repo (top-level ``grass_location`` /
``grass_epsg`` vs a ``grass:`` block) so both forms work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


class ConfigError(ValueError):
    """A watershed config is missing a required field or has a bad value."""


@dataclass
class WatershedConfig:
    """Validated watershed configuration (see :func:`load_config`)."""

    name: str
    gauge: str
    title: str
    grass_location: str
    grass_epsg: int
    forcing_start: str
    forcing_end: str
    forcing_csv: str
    config_name: str
    first_year: int
    last_year: int
    decade_span: int
    params_template: str | None
    driver_python: str
    conda_env: str
    output_subdir: str
    initial_params: dict = field(default_factory=dict)

    def decade_starts(self):
        """Yield the start year of each calibration window."""
        return range(self.first_year, self.last_year + 1, self.decade_span)


def _require(d, key, where):
    if key not in d or d[key] is None:
        raise ConfigError(f"watershed config: missing required '{where}{key}'")
    return d[key]


def _check_date(value, where):
    try:
        datetime.strptime(str(value), "%Y-%m-%d")
    except (ValueError, TypeError):
        raise ConfigError(
            f"watershed config: '{where}' must be a YYYY-MM-DD date; got {value!r}")
    return str(value)


def load_config(path):
    """
    Load and validate a watershed config YAML.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the watershed config file.

    Returns
    -------
    WatershedConfig

    Raises
    ------
    ConfigError
        If a required field is missing or a value is invalid.
    """
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"watershed config not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"watershed config {path} did not parse to a mapping")

    name  = _require(raw, "name", "")
    gauge = str(_require(raw, "gauge", ""))
    title = _require(raw, "title", "")

    # GRASS settings: accept a `grass:` block or the legacy top-level keys.
    grass = raw.get("grass", {}) or {}
    location = (grass.get("location")
                or raw.get("grass_location")
                or "".join(w.title() for w in str(name).split("_")))
    epsg = grass.get("epsg", raw.get("grass_epsg", 32615))
    try:
        epsg = int(epsg)
    except (ValueError, TypeError):
        raise ConfigError(f"watershed config: grass epsg must be an integer; got {epsg!r}")

    forcing = _require(raw, "forcing", "")
    if not isinstance(forcing, dict):
        raise ConfigError("watershed config: 'forcing' must be a mapping")
    start = _check_date(_require(forcing, "start", "forcing."), "forcing.start")
    end   = _check_date(_require(forcing, "end", "forcing."), "forcing.end")
    if end < start:
        raise ConfigError(f"watershed config: forcing.end ({end}) precedes start ({start})")
    csv_name    = forcing.get("csv_name", f"{name}_forcing.csv")
    config_name = forcing.get("config_name", f"{name}_config.yml")

    decades = _require(raw, "decades", "")
    if not isinstance(decades, dict):
        raise ConfigError("watershed config: 'decades' must be a mapping")
    first_year = int(_require(decades, "first_year", "decades."))
    last_year  = int(_require(decades, "last_year", "decades."))
    span       = int(decades.get("span", 10))
    if last_year < first_year:
        raise ConfigError(
            f"watershed config: decades.last_year ({last_year}) < first_year ({first_year})")
    if span < 1:
        raise ConfigError(f"watershed config: decades.span must be >= 1; got {span}")

    scaffold = raw.get("scaffold", {}) or {}
    params_template = scaffold.get("params_template")  # None -> bundled default
    driver_python   = scaffold.get("driver_python", "python")
    conda_env       = scaffold.get("conda_env", "dakota-env")
    output_subdir   = scaffold.get("output_subdir", "forcing")

    initial_params = raw.get("initial_params", {}) or {}
    if not isinstance(initial_params, dict):
        raise ConfigError("watershed config: 'initial_params' must be a mapping")

    return WatershedConfig(
        name            = name,
        gauge           = gauge,
        title           = title,
        grass_location  = location,
        grass_epsg      = epsg,
        forcing_start   = start,
        forcing_end     = end,
        forcing_csv     = csv_name,
        config_name     = config_name,
        first_year      = first_year,
        last_year       = last_year,
        decade_span     = span,
        params_template = params_template,
        driver_python   = driver_python,
        conda_env       = conda_env,
        output_subdir   = output_subdir,
        initial_params  = initial_params,
    )

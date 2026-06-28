"""
Generate a per-watershed MNiShed calibration study directory.

This is the packaged, generalized form of the study repo's ``setup_watershed.py``
study-dir step: it lays down the calibration driver scripts and one ``params.yml``
per decade window, plus the shared study-root helpers. The GRASS forcing-data
pipeline scripts are written separately by :mod:`mnished_builder.grass_pipeline`.
"""

from __future__ import annotations

import stat
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Driver scripts copied verbatim into the study directory.
GENERIC_SCRIPTS = [
    "run.sh", "run_all_decades.sh", "archive_run.sh",
    "driver.py", "warm_start.py",
]
# Scripts carrying the basin name/title as literal WATERSHED_NAME / WATERSHED_TITLE
# placeholders (the study repo's own convention).
TITLE_SCRIPTS = [
    "plot_best.py", "plot_trends.py", "generate_dakota_in.py", "summarize.py",
]
# Shared helpers written once at the study root (operate across all watersheds).
ROOT_SCRIPTS = ["status.py", "summarize_backbone.py"]


def _make_executable(path):
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


def _write(dst, text, executable=False):
    dst.write_text(text)
    if executable:
        _make_executable(dst)


def render_params(cfg, decade_start, decade_end, label, template_text=None):
    """
    Render one decade's ``params.yml`` from the parameter template.

    Substitutes the decade window, the model config name, and the warm-start
    ``initial_params`` values. Raises a helpful error if the template references
    an ``initial_params`` key the config does not provide.
    """
    if template_text is None:
        path = (Path(cfg.params_template) if cfg.params_template
                else TEMPLATE_DIR / "params_template.yml")
        template_text = path.read_text()
    fields = dict(cfg.initial_params)
    fields.update(label=label, decade_start=decade_start, decade_end=decade_end,
                  config_name=cfg.config_name)
    try:
        return template_text.format(**fields)
    except KeyError as exc:
        raise KeyError(
            f"params template needs a value for {exc} that is not in the "
            f"watershed config's initial_params (or as a substitution field). "
            f"Provided initial_params keys: {sorted(cfg.initial_params)}.") from exc


def scaffold_study(cfg, out_root):
    """
    Generate the study directory tree for one watershed.

    Parameters
    ----------
    cfg : WatershedConfig
        Validated config (see :func:`mnished_builder.config.load_config`).
    out_root : str or pathlib.Path
        Study-root directory; ``<out_root>/<name>/`` is the watershed study dir.

    Returns
    -------
    pathlib.Path
        The created study directory (``<out_root>/<name>``).
    """
    out_root = Path(out_root)
    study_dir = out_root / cfg.name
    study_dir.mkdir(parents=True, exist_ok=True)

    # Shared study-root helpers (idempotent; written once per study root).
    for fname in ROOT_SCRIPTS:
        src = TEMPLATE_DIR / fname
        if src.is_file():
            _write(out_root / fname, src.read_text(), executable=True)

    # Driver scripts copied verbatim.
    for fname in GENERIC_SCRIPTS:
        _write(study_dir / fname, (TEMPLATE_DIR / fname).read_text(), executable=True)

    # Name/title-substituted scripts.
    for fname in TITLE_SCRIPTS:
        text = (TEMPLATE_DIR / fname).read_text()
        text = text.replace("WATERSHED_TITLE", cfg.title)
        text = text.replace("WATERSHED_NAME", cfg.name)
        _write(study_dir / fname, text, executable=True)

    # run_driver.sh: substitute the calibration Python interpreter.
    rd = (TEMPLATE_DIR / "run_driver.sh").read_text()
    rd = rd.replace("MNISHED_BUILDER_DRIVER_PYTHON", cfg.driver_python)
    _write(study_dir / "run_driver.sh", rd, executable=True)

    # One params.yml per decade window.
    template_text = (Path(cfg.params_template).read_text() if cfg.params_template
                     else (TEMPLATE_DIR / "params_template.yml").read_text())
    for y in cfg.decade_starts():
        y_end = y + cfg.decade_span - 1
        label = f"{y}-{y_end}"
        decade_dir = study_dir / "decades" / label
        decade_dir.mkdir(parents=True, exist_ok=True)
        content = render_params(
            cfg, f"{y}-01-01", f"{y_end}-12-31", label, template_text=template_text)
        (decade_dir / "params.yml").write_text(content)

    return study_dir

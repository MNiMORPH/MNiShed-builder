"""
Generate the GRASS forcing-data pipeline scripts for a watershed.

Three shell scripts are written, mirroring the study repo's
``setup_watershed.py``:

* ``<name>_pipeline_download.sh`` -- internet-required (``v.in.waterdata`` pulls
  the USGS discharge + basin polygon; ``v.in.ghcn`` pulls climate stations);
* ``<name>_pipeline_compute.sh``  -- no internet (IDW via ``v.interp.timeseries``
  + export via ``db.out.hydroravens``), HPC-submittable;
* ``<name>_pipeline.sh``          -- convenience wrapper (download then compute).

The split lets the compute phase run on HPC nodes without outbound internet. The
SLURM submission script is also written to ``<out_root>/slurm/pipeline_job.sh``.

This module *emits scripts that call* the GRASS addons; it does not import GRASS.
"""

from __future__ import annotations

import stat
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _make_executable(path):
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


def _header_vars(cfg, examples_dir_abs, study_dir_abs):
    return (
        "set -e\n"
        "export GRASS_OVERWRITE=1\n\n"
        f"GAUGE={cfg.gauge}\n"
        f"START={cfg.forcing_start}\n"
        f"END={cfg.forcing_end}\n"
        f'OUTDIR="{examples_dir_abs}"\n'
        f'STUDY_DIR="{study_dir_abs}"\n'
    )


def _download_script(cfg, examples_dir_abs, header):
    return f"""\
#!/bin/bash
# {cfg.title} — forcing-data download (internet-required)
#
# Downloads USGS discharge + basin polygon and GHCN station data into the
# GRASS mapset.  Run this on any machine with outbound internet access
# BEFORE running {cfg.name}_pipeline_compute.sh.
#
# Gauge  : USGS {cfg.gauge}
# Period : {cfg.forcing_start} to {cfg.forcing_end}
#
# One-time GRASS location setup (EPSG:{cfg.grass_epsg}):
#   grass -c EPSG:{cfg.grass_epsg} ~/grassdata/{cfg.grass_location}/PERMANENT
#
# Run:
#   grass ~/grassdata/{cfg.grass_location}/PERMANENT \\
#       --exec bash {examples_dir_abs}/{cfg.name}_pipeline_download.sh
#
# Required GRASS addons: v.in.waterdata  v.in.ghcn

{header}
# ── 1. Discharge time series + upstream basin polygon ─────────────────────────
v.in.waterdata \\
    sites=$GAUGE \\
    output=discharge_${{GAUGE}} \\
    basins={cfg.name}_basin \\
    start_date=$START \\
    end_date=$END \\
    -t

# ── 2. Region = basin extent (with padding for station search) ─────────────────
g.region vector={cfg.name}_basin res=1000 -a

# ── 3. GHCN station import ────────────────────────────────────────────────────
# sample= ensures the bbox expands until the basin centroid falls inside the
# convex hull of stations for each element, guaranteeing true spatial enclosure.
v.in.ghcn \\
    output=ghcn_stations \\
    elements=PRCP,TMAX,TMIN \\
    start_date=$START \\
    end_date=$END \\
    min_coverage=0.1 \\
    domain={cfg.name}_basin

echo "Download complete. Transfer the GRASS mapset to MSI, then run:"
echo "  {cfg.name}_pipeline_compute.sh"
"""


def _compute_script(cfg, header):
    return f"""\
#!/bin/bash
# {cfg.title} — forcing-data compute (no internet required)
#
# Interpolates GHCN station data to basin-mean time series and exports to
# MNiShed CSV + config YML.  Requires the GRASS mapset to already
# contain discharge_$GAUGE, {cfg.name}_basin, and ghcn_stations (run the
# download script first).
#
# On MSI, submit via: sbatch slurm/pipeline_job.sh {cfg.name}
#
# Required GRASS addons: v.interp.timeseries  db.out.hydroravens
#
# PROJ_DATA: conda environments may shadow the system PROJ data directory.
# The line below resolves it from the active conda env, falling back to the
# system path so GRASS commands work correctly on both laptops and HPC nodes.
PROJ_DATA="${{PROJ_DATA:-${{CONDA_PREFIX:+$CONDA_PREFIX/share/proj}}}}"; \\
    PROJ_DATA="${{PROJ_DATA:-/usr/share/proj}}"
export PROJ_DATA PROJ_LIB="$PROJ_DATA"

{header}
# ── 2. Region = basin extent (ensure it is set after mapset transfer) ──────────
g.region vector={cfg.name}_basin res=1000 -a

# ── 4. Basin-mean interpolation (IDW, area-weighted, min 2 stations) ──────────
for ELEM in PRCP TMAX TMIN; do
    v.interp.timeseries \\
        input=ghcn_stations \\
        element=$ELEM \\
        method=idw \\
        min_stations=2 \\
        domain={cfg.name}_basin \\
        start_date=$START \\
        end_date=$END \\
        -f
done

# ── 5. Export to MNiShed format ──────────────────────────────────────────
db.out.hydroravens \\
    basin={cfg.name}_basin \\
    discharge_table=discharge_${{GAUGE}}_timeseries \\
    output="${{OUTDIR}}/{cfg.forcing_csv}" \\
    config="${{OUTDIR}}/{cfg.name}_config.yml"

# ── 6. Copy config to study directory ─────────────────────────────────────────
cp "${{OUTDIR}}/{cfg.name}_config.yml" "${{STUDY_DIR}}/{cfg.config_name}"
echo "Config copied → ${{STUDY_DIR}}/{cfg.config_name}"

echo ""
echo "Done. Files written:"
echo "  ${{OUTDIR}}/{cfg.forcing_csv}"
echo "  ${{OUTDIR}}/{cfg.name}_config.yml"
echo "  ${{STUDY_DIR}}/{cfg.config_name}"
echo ""
echo "Next: cd ${{STUDY_DIR}} && nohup bash run_all_decades.sh >run_all.log 2>&1 &"
"""


def _combined_script(cfg, examples_dir_abs):
    return f"""\
#!/bin/bash
# {cfg.title} — full forcing-data pipeline (download + compute)
#
# Convenience wrapper: runs the download script then the compute script
# in sequence.  For HPC use, run the two scripts separately.
#
# Gauge  : USGS {cfg.gauge}
# Period : {cfg.forcing_start} to {cfg.forcing_end}
#
# One-time GRASS location setup (EPSG:{cfg.grass_epsg}):
#   grass -c EPSG:{cfg.grass_epsg} ~/grassdata/{cfg.grass_location}/PERMANENT
#
# Run:
#   grass ~/grassdata/{cfg.grass_location}/PERMANENT \\
#       --exec bash {examples_dir_abs}/{cfg.name}_pipeline.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$SCRIPT_DIR/{cfg.name}_pipeline_download.sh"
bash "$SCRIPT_DIR/{cfg.name}_pipeline_compute.sh"
"""


def write_pipeline_scripts(cfg, out_root):
    """
    Write the GRASS forcing-data pipeline scripts (and the SLURM job).

    Parameters
    ----------
    cfg : WatershedConfig
    out_root : str or pathlib.Path
        Study-root directory. Pipeline scripts go in
        ``<out_root>/<output_subdir>/<name>/``; the SLURM job in
        ``<out_root>/slurm/``.

    Returns
    -------
    pathlib.Path
        The directory the pipeline scripts were written to.
    """
    out_root = Path(out_root)
    examples_dir = out_root / cfg.output_subdir / cfg.name
    examples_dir.mkdir(parents=True, exist_ok=True)
    study_dir = out_root / cfg.name

    examples_dir_abs = examples_dir.resolve()
    study_dir_abs = study_dir.resolve()
    header = _header_vars(cfg, examples_dir_abs, study_dir_abs)

    scripts = {
        f"{cfg.name}_pipeline_download.sh":
            _download_script(cfg, examples_dir_abs, header),
        f"{cfg.name}_pipeline_compute.sh":
            _compute_script(cfg, header),
        f"{cfg.name}_pipeline.sh":
            _combined_script(cfg, examples_dir_abs),
    }
    for fname, text in scripts.items():
        dst = examples_dir / fname
        dst.write_text(text)
        _make_executable(dst)

    # SLURM submission script (study-root scope; substitute conda env + subdir).
    slurm_src = TEMPLATE_DIR / "pipeline_job.sh"
    if slurm_src.is_file():
        slurm_dir = out_root / "slurm"
        slurm_dir.mkdir(parents=True, exist_ok=True)
        text = slurm_src.read_text()
        text = text.replace("MNISHED_BUILDER_CONDA_ENV", cfg.conda_env)
        text = text.replace("MNISHED_BUILDER_OUTPUT_SUBDIR", cfg.output_subdir)
        dst = slurm_dir / "pipeline_job.sh"
        dst.write_text(text)
        _make_executable(dst)

    return examples_dir

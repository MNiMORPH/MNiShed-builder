"""
Command-line interface for mnished-builder.

Usage::

    mnished-builder new --config watershed_configs/crow_wing_river.yml [--out DIR]

Generates, under the study root ``--out`` (default: current directory):

* ``<name>/``                       the per-watershed calibration study directory
* ``<output_subdir>/<name>/``       the GRASS forcing-data pipeline scripts
* ``slurm/pipeline_job.sh``         the HPC submission script
* shared study-root helpers (``status.py``, ``summarize_backbone.py``)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .grass_pipeline import write_pipeline_scripts
from .scaffold import scaffold_study


def _cmd_new(args):
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_root = Path(args.out)
    study_dir = scaffold_study(cfg, out_root)
    examples_dir = write_pipeline_scripts(cfg, out_root)

    n_decades = len(list(cfg.decade_starts()))
    print(f"""\
Built MNiShed study for {cfg.title}.

  study dir       : {study_dir}/   ({n_decades} decade(s) in decades/)
  pipeline scripts: {examples_dir}/
  SLURM job       : {out_root / 'slurm' / 'pipeline_job.sh'}

Next steps:
  1. Create the GRASS location (once):
       grass -c EPSG:{cfg.grass_epsg} ~/grassdata/{cfg.grass_location}/PERMANENT

  2. Build the forcing data (download needs internet):
       grass ~/grassdata/{cfg.grass_location}/PERMANENT \\
           --exec bash {examples_dir}/{cfg.name}_pipeline.sh

  3. Start the decade calibrations:
       cd {study_dir} && nohup bash run_all_decades.sh >run_all.log 2>&1 &
""")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mnished-builder",
        description="Build a MNiShed calibration study from a watershed config.")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="generate a study from a watershed config")
    new.add_argument("--config", required=True, help="watershed config YAML")
    new.add_argument("--out", default=".",
                     help="study-root output directory (default: current dir)")
    new.set_defaults(func=_cmd_new)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

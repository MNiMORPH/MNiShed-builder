# mnished-builder

Build a complete [MNiShed](https://github.com/MNiMORPH/MNiShed) calibration
study for a gauged watershed from a one-screen config — a USGS gauge ID, a
projection, a forcing period, and warm-start parameter values.

`mnished-builder` is the **orchestrator** of MNiShed's producer/consumer input
pipeline. A set of GRASS GIS addons are the *producers* (they fetch and process
the geospatial data); MNiShed is the *consumer* (it reads a forcing CSV + config
YAML and knows nothing about where they came from). `mnished-builder` sits
between them: from the watershed config it generates (1) the per-decade
calibration scaffolding and (2) the GRASS forcing-data pipeline scripts that
drive the producers.

It **does not import GRASS** — it emits shell scripts that call the GRASS addons —
so the package is pure-Python (`pyyaml` only) and its generation logic is fully
testable without a GRASS install.

## Install

```bash
pip install -e .            # from a clone
```

## Usage

```bash
mnished-builder new --config watershed_configs/crow_wing_river.yml --out STUDY_ROOT
```

This writes, under `STUDY_ROOT`:

```
STUDY_ROOT/
  <name>/                            per-watershed calibration study directory
    decades/<start>-<end>/params.yml  one calibration window per decade
    run.sh  run_all_decades.sh  driver.py  ...   calibration driver scripts
  forcing/<name>/                    GRASS forcing-data pipeline scripts
    <name>_pipeline_download.sh        v.in.waterdata + v.in.ghcn (needs internet)
    <name>_pipeline_compute.sh         v.interp.timeseries + db.out.hydroravens
    <name>_pipeline.sh                 download then compute
  slurm/pipeline_job.sh              HPC submission script for the compute phase
  status.py  summarize_backbone.py   shared study-root helpers
```

Then build the forcing data and run the calibrations (see the printed next-steps).

### Validate the built inputs (pre-flight)

Once the GRASS pipeline has produced the forcing CSV + config, check them against
MNiShed's input contract before launching a calibration:

```bash
mnished-builder validate --config STUDY_ROOT/<name>/<name>_config.yml [--strict]
```

This runs `mnished.io.validate_inputs` and reports every contract problem at
once — a missing required column, an unknown ET method, a config that has fallen
behind a MNiShed schema change — distinguishing errors (exit 1) from warnings
(silent degradation; promote to failures with `--strict`). It needs MNiShed
installed (`pip install 'mnished-builder[validate]'`). The generated `run.sh`
also runs this check automatically as a pre-flight before each Dakota run.

## The watershed config

```yaml
name:  crow_wing_river
gauge: "05244000"
title: "Crow Wing River at Nimrod"

grass:                       # or legacy flat keys grass_location / grass_epsg
  location: CrowWingRiver
  epsg: 32615

forcing:
  start: '1905-01-01'
  end:   '2024-12-31'
  csv_name:    crow_wing_forcing.csv     # optional; defaults from name
  config_name: crow_wing_config.yml

decades:
  first_year: 1911
  last_year:  2021
  span: 10                   # optional; calibration-window length in years (default 10)

scaffold:                    # all optional
  params_template: path/to/params_template.yml   # default: bundled template
  driver_python:   python                         # interpreter for run_driver.sh
  conda_env:       dakota-env                      # conda env for the SLURM job
  output_subdir:   forcing                         # where pipeline scripts go

initial_params:             # warm-start values substituted into the params template
  log__t_recession_soil:         4.493
  log__t_recession_intermediate: 1.021
  ...
```

See `watershed_configs/` for complete examples (`cannon_river.yml`,
`crow_wing_river.yml`).

## Required GRASS addons (the producers)

The generated pipeline scripts call these GRASS addons — install them where the
scripts run, not where `mnished-builder` runs:

| Addon | Role |
|---|---|
| `v.in.waterdata` | USGS discharge time series + upstream basin polygon from the gauge |
| `v.in.ghcn` | GHCN climate-station data (PRCP, TMAX, TMIN) |
| `v.interp.timeseries` | IDW interpolation of stations to basin-mean series |
| `db.out.hydroravens` | export to MNiShed forcing CSV + config YAML |

## Status & roadmap

**v0.1** extracts and generalizes the proven forcing + config + calibration
scaffolding pipeline (formerly `setup_watershed.py` in a study repo) into a
reusable, tested package.

Planned: a **recession-priors-from-geometry** stage that drives `r.stream.distance`
(→ hillslope length and slope) + `r.in.polaris` (→ soil K, drainable porosity,
depth) and folds derived recession-timescale priors into the generated MNiShed
config. The geometry/soil math lives in the GRASS producers and
[`rivernetworkx`](https://github.com/MNiMORPH/GRASS-fluvial-profiler); MNiShed
stays GIS-free.

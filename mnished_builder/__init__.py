"""
mnished-builder
~~~~~~~~~~~~~~~

Build a complete MNiShed calibration study for a gauged watershed from a
one-screen config (gauge ID, projection, period, warm-start parameters).

``mnished-builder`` is the *orchestrator* of MNiShed's producer/consumer input
pipeline: it generates (1) the per-decade calibration scaffolding and (2) the
GRASS forcing-data pipeline scripts that drive the GRASS-addon producers
(``v.in.waterdata``, ``v.in.ghcn``, ``v.interp.timeseries``,
``db.out.hydroravens``) to build MNiShed's forcing CSV + config YAML. MNiShed
itself stays GIS-free and simply consumes those inputs.

It does not import GRASS — it *emits scripts that call* the GRASS addons — so the
package is pure-Python and its scaffolding/script generation is testable without
a GRASS install.
"""

from .config import WatershedConfig, load_config
from .scaffold import scaffold_study
from .grass_pipeline import write_pipeline_scripts

__version__ = "0.1.0"

__all__ = [
    "WatershedConfig",
    "load_config",
    "scaffold_study",
    "write_pipeline_scripts",
    "__version__",
]

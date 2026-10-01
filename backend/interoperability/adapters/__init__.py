"""Built-in format adapters for MachineryPro AI (Stage 4C).

Stage 4C ships three adapters, all pure-Python (no external dependencies):

* :class:`StepTokenAdapter` — STEP AP203 / AP214 / AP242 token-level parser.
  Reaches Level 1 (parsed) on all conforming STEP files. Level 2 (geometry)
  when ``pythonocc-core`` is available. Degrades gracefully.

* :class:`IgesTokenAdapter` — IGES 5.x token-level parser.
  Reaches Level 1 on all conforming IGES files.

* :class:`DxfTokenAdapter` — DXF R12–R2024 header + entity reader.
  Reaches Level 1 on all text DXF files.  Level 2 (drawing geometry)
  via ``ezdxf`` when available.

All adapters honour the FormatAdapter contract (Stage 4A) and produce
``CanonicalDocument`` envelopes with ``ConversionFidelityReport``.

No adapter performs manufacturing-feature recognition (Stage 4D).
No adapter contacts external services or reads the filesystem directly;
bytes are supplied by the caller.
"""

from backend.interoperability.adapters.dxf import DxfTokenAdapter
from backend.interoperability.adapters.iges import IgesTokenAdapter
from backend.interoperability.adapters.registry_helpers import (
    build_default_adapter_registry,
)
from backend.interoperability.adapters.step import StepTokenAdapter

__all__ = [
    "DxfTokenAdapter",
    "IgesTokenAdapter",
    "StepTokenAdapter",
    "build_default_adapter_registry",
]

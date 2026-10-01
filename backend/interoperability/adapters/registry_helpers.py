"""Registry factory helpers for Stage 4C built-in adapters.

Provides a single function that registers all built-in adapters into a
new :class:`~backend.interoperability.registry.AdapterRegistry`.

Usage::

    from backend.interoperability.adapters import build_default_adapter_registry

    registry = build_default_adapter_registry()
    adapters = registry.find_by_format("STEP-AP242")
"""

from __future__ import annotations

from backend.interoperability.adapters.dxf import DxfTokenAdapter
from backend.interoperability.adapters.iges import IgesTokenAdapter
from backend.interoperability.adapters.step import StepTokenAdapter
from backend.interoperability.registry import AdapterRegistry

__all__ = ["build_default_adapter_registry"]


def build_default_adapter_registry() -> AdapterRegistry:
    """Create an AdapterRegistry with all Stage 4C built-in adapters registered.

    The registry is NOT a singleton; callers own and manage their instance.
    Commercial/native adapters are NOT included here; they are registered
    as optional plugins.

    Returns:
        A new :class:`AdapterRegistry` with StepTokenAdapter,
        IgesTokenAdapter, and DxfTokenAdapter registered.
    """
    registry = AdapterRegistry()
    registry.register(StepTokenAdapter())
    registry.register(IgesTokenAdapter())
    registry.register(DxfTokenAdapter())
    return registry

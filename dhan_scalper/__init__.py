"""DhanHQ Nifty scalping engine.

The package is deliberately paper-first. Live execution requires both valid
DhanHQ environment secrets and an explicit confirmation flag.
"""

from .config import EngineConfig, ExecutionMode

__all__ = ["EngineConfig", "ExecutionMode"]
"""Agentic SDLC — an agentic system that takes a software requirement and drives
it through understand -> decompose -> orchestrate -> generate -> validate, under
controlled autonomy with human approval gates.
"""

from .config import Settings, get_settings
from .orchestration import Orchestrator

__version__ = "1.0.0"
__all__ = ["Orchestrator", "Settings", "get_settings", "__version__"]

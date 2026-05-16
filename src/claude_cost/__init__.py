"""claude-cost: environmental footprint of your Claude Code usage."""

__version__ = "0.1.0"

from claude_cost.parser import iter_records, load_dataframe, default_claude_dir  # noqa: E402

try:
    from claude_cost.model import Factors, load_default_factors, apply_impact  # noqa: F401
except ImportError:
    pass

__all__ = [
    "iter_records",
    "load_dataframe",
    "default_claude_dir",
    "Factors",
    "load_default_factors",
    "apply_impact",
]

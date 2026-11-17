"""scrub: remove personal details from text before it is stored or sent anywhere."""

from .core import KINDS, Finding, Result, redact

__all__ = ["KINDS", "Finding", "Result", "redact"]
__version__ = "0.1.0"

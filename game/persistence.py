"""Compatibility exports for the shared append-only event store."""
from ._shared import load_log, save_log

__all__ = ['load_log', 'save_log']

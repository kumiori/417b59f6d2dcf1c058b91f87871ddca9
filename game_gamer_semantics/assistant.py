"""An optional advisory boundary. Providers select identifiers from a supplied set."""
from collections.abc import Callable, Sequence
from copy import deepcopy


SemanticAssistant = Callable[[str, dict], Sequence[str]]


def suggested_keys(assistant: SemanticAssistant | None, topic, context, allowed, *, limit=None):
    if assistant is None:
        return []
    try:
        suggestions = assistant(topic, deepcopy(context))
        if isinstance(suggestions, (str, bytes)) or not isinstance(suggestions, Sequence):
            return []
        accepted = dict.fromkeys(key for key in suggestions if isinstance(key, str) and key in allowed)
        return list(accepted)[:limit]
    except Exception:
        return []

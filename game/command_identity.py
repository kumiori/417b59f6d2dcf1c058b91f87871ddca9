"""Compare typed command values before recognising an exact retry."""


def same_command(left: object, right: object) -> bool:
    """Compare mappings without key order and arrays in order."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            same_command(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(same_command, left, right))
    return left == right

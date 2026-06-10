"""Code-convention validation (M1 slice, #244 — spec §6.2, §8.4).

A paint line may declare a `code_pattern` regex (e.g. ^MPA-\\d{3}$) that every
paint code in the line must satisfy. The pattern is applied with re.search as
written — the spec's examples carry their own anchors, so the pattern author
controls strictness.

M3 extends this into the full guide validator (paint-exists, owned, JSON-block
references); only the code-pattern check lives here for now.
"""
import re


def validate_pattern(pattern: str | None) -> str | None:
    """Return an error message if `pattern` is not a valid regex, else None."""
    if not pattern:
        return None
    try:
        re.compile(pattern)
    except re.error as e:
        return f"Invalid code pattern '{pattern}': {e}"
    return None


def validate_code(code: str, pattern: str | None) -> str | None:
    """Return an error message if `code` does not satisfy the line's
    `code_pattern`, else None. Lines without a pattern accept any code."""
    if not pattern:
        return None
    try:
        compiled = re.compile(pattern)
    except re.error:
        # Patterns are validated on line create/update, so this only guards
        # against hand-edited DBs — skip rather than block all writes.
        return None
    # No !r here — repr doubles backslashes in patterns like ^MPA-\d{3}$.
    if compiled.search(code) is None:
        return f"Code '{code}' does not match the line's code pattern '{pattern}'"
    return None

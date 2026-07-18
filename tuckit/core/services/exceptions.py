class NotFound(Exception):
    """Raised when an id does not exist or is not visible to the given org."""


class InvalidValue(Exception):
    """Raised when a caller supplies a value outside the allowed set (e.g. a bad status)."""


class LimitReached(Exception):
    """Raised when an org-level plan limit (e.g. a seat cap) would be exceeded."""

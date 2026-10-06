"""Error helper: every API error carries a stable `code` that the frontend translates (id/en/ar)."""
from fastapi import HTTPException


def fail(status: int, code: str, **extra):
    """Raise an HTTP error with a machine-readable code (never a hard-coded language string)."""
    raise HTTPException(status_code=status, detail={"code": code, **extra})

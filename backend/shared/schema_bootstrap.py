"""Deprecated — delegates to ``backend.shared.database.migrations``.

Kept for backward compatibility; new code should import directly from
:mod:`backend.shared.database`.
"""

from backend.shared.database.migrations import bootstrap_schema  # noqa: F401

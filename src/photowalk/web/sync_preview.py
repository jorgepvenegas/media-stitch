"""Preview-side logic: compute shifted timelines without touching disk."""

from photowalk.web.sync_models import OffsetEntry


def compute_net_deltas(offsets: list[OffsetEntry]) -> dict[str, float]:
    """Sum delta_seconds per path across the offset stack.

    Paths with a zero net delta are omitted from the result.
    """
    totals: dict[str, float] = {}
    for entry in offsets:
        for path in entry.target_paths:
            totals[path] = totals.get(path, 0.0) + entry.delta_seconds
    return {p: d for p, d in totals.items() if d != 0.0}

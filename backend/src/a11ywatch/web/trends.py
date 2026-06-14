from dataclasses import dataclass

# Direction labels for an issue-count change between two scans. Fewer issues is better,
# so a drop is "improved" and a rise is "regressed".
IMPROVED = "improved"
REGRESSED = "regressed"
UNCHANGED = "unchanged"
NO_BASELINE = "no_baseline"


@dataclass(frozen=True)
class Trend:
    direction: str
    change: int  # current_total - previous_total (negative = fewer issues now)

    @property
    def magnitude(self) -> int:
        return abs(self.change)


def scan_trend(current_total: int, previous_total: int | None) -> Trend:
    """Compare a scan's issue count against the previous scan's.

    Returns ``NO_BASELINE`` (change 0) when there is no prior scan to compare against.
    """
    if previous_total is None:
        return Trend(direction=NO_BASELINE, change=0)
    change = current_total - previous_total
    if change < 0:
        return Trend(direction=IMPROVED, change=change)
    if change > 0:
        return Trend(direction=REGRESSED, change=change)
    return Trend(direction=UNCHANGED, change=0)

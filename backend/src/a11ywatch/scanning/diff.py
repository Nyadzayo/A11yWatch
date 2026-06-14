from dataclasses import dataclass


@dataclass(frozen=True)
class FingerprintDiff:
    new: set[str]
    resolved: set[str]

    @property
    def new_count(self) -> int:
        return len(self.new)

    @property
    def resolved_count(self) -> int:
        return len(self.resolved)


def diff_fingerprints(current: set[str], previous: set[str]) -> FingerprintDiff:
    """NEW = present now but not before; RESOLVED = present before but not now."""
    current = set(current)
    previous = set(previous)
    return FingerprintDiff(new=current - previous, resolved=previous - current)

from dataclasses import dataclass


@dataclass
class Action:
    """Strict editing action structure for keyboard operations."""

    action: str
    text: str
    find: str
    which: str = "last"

    @property
    def type(self) -> str:
        """Compatibility property mapping action to type."""
        return self.action


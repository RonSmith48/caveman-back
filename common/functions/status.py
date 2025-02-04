from typing import Optional, List


class Status:
    """
    Utility class to manage and step through a sequence of statuses.

    Attributes:
        statuses (List[str]): The list of status names.
        current_index (int): The current position in the statuses list.

    Usage:

        s = Status(initial_status='Charged')
        print(s.current_status)  # Outputs: Charged

        s.step(2)     # Advances two steps forward, bounded by the list limits.
        s.step(-1)    # Moves one step backward.

        s.set_status('Bogging')
    """

    def __init__(self, initial_status: Optional[str] = None, statuses: Optional[List[str]] = None) -> None:
        # Use the provided list of statuses or default to a standard list.
        self.statuses = statuses if statuses is not None else [
            'Designed', 'Drilled', 'Charged', 'Bogging', 'Complete']

        # Set the initial status; if not provided, default to the first element.
        if initial_status is None:
            self.current_index = 0
        else:
            if initial_status in self.statuses:
                self.current_index = self.statuses.index(initial_status)
            else:
                raise ValueError(
                    f"'{initial_status}' is not a valid status. Valid statuses: {self.statuses}")

    def next_status(self) -> str:
        """Advance to the next status (if possible) and return it."""
        if self.current_index < len(self.statuses) - 1:
            self.current_index += 1
        return self.get_current_status()

    def prev_status(self) -> str:
        """Go back to the previous status (if possible) and return it."""
        if self.current_index > 0:
            self.current_index -= 1
        return self.get_current_status()

    def step(self, steps: int = 1) -> str:
        """
        Step a given number of statuses.

        Positive numbers move forward; negative numbers move backward.
        The index is bounded by 0 and the last status index.
        """
        new_index = self.current_index + steps
        new_index = max(0, min(new_index, len(self.statuses) - 1))
        self.current_index = new_index
        return self.get_current_status()

    def get_current_status(self) -> str:
        """Return the current status name."""
        return self.statuses[self.current_index]

    def set_status(self, status_name: str) -> str:
        """
        Set the current status to the given status name, if valid, and return it.

        Raises:
            ValueError: If the provided status name is not in the statuses list.
        """
        index = self.get_position(status_name)
        if index == -1:
            raise ValueError(
                f"'{status_name}' is not a valid status. Valid statuses: {self.statuses}")
        self.current_index = index
        return self.get_current_status()

    def reset_status(self) -> str:
        """Reset to the initial (first) status and return it."""
        self.current_index = 0
        return self.get_current_status()

    def get_position(self, status_name: str) -> int:
        """
        Return the index position of a given status name.

        Returns:
            int: The index if found; otherwise -1.
        """
        try:
            return self.statuses.index(status_name)
        except ValueError:
            return -1

    @property
    def current_status(self) -> str:
        """Property to get the current status name."""
        return self.get_current_status()

    def __repr__(self) -> str:
        return f"Status(current_status='{self.get_current_status()}')"

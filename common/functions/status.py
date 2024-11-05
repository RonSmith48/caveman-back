class Status():
    def __init__(self):
        self.statuses = ['Designed', 'Drilled',
                         'Charged', 'Bogging', 'Complete']
        self.current_index = 0

    def next_status(self):
        """Move to the next status if possible."""
        if self.current_index < len(self.statuses) - 1:
            self.current_index += 1
        return self.get_current_status()

    def prev_status(self):
        """Move to the previous status if possible."""
        if self.current_index > 0:
            self.current_index -= 1
        return self.get_current_status()

    def get_current_status(self):
        """Return the current status."""
        return self.statuses[self.current_index]

    def reset_status(self):
        """Reset to the initial status."""
        self.current_index = 0
        return self.get_current_status()

    def get_position(self, status_name):
        """Return the position (index) of a given status name, or -1 if not found."""
        try:
            return self.statuses.index(status_name)
        except ValueError:
            return -1  # Return -1 if the status is not found

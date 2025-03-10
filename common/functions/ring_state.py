from prod_actual.models import RingState


def ensure_mandatory_ring_states():
    """
    Ensures that all mandatory `RingState` combinations exist in the database.
    Missing combinations will be created.
    """
    # Define the mandatory state combinations
    mandatory_states = [
        {"pri_state": "Designed", "sec_state": None},
        {"pri_state": "Drilled", "sec_state": None},
        {"pri_state": "Drilled", "sec_state": "Redrilled"},
        {"pri_state": "Drilled", "sec_state": "Lost Rods"},
        {"pri_state": "Drilled", "sec_state": "BG Reported"},
        {"pri_state": "Drilled", "sec_state": "Making Water"},
        {"pri_state": "Drilled", "sec_state": "Incomplete"},
        {"pri_state": "Drilled", "sec_state": "Blocked Holes"},
        {"pri_state": "Drilled", "sec_state": "Had Cleanout"},
        {"pri_state": "Charged", "sec_state": None},
        {"pri_state": "Charged", "sec_state": "Incomplete"},
        {"pri_state": "Charged", "sec_state": "Charged Short"},
        {"pri_state": "Charged", "sec_state": "Recharged Holes"},
        {"pri_state": "Bogging", "sec_state": None},
        {"pri_state": "Complete", "sec_state": None},
        {"pri_state": "Abandoned", "sec_state": None},
    ]

    for state in mandatory_states:
        # Use get_or_create to check if the combination exists, and create if missing
        RingState.objects.get_or_create(
            pri_state=state["pri_state"],
            # Use None if sec_state is not provided
            sec_state=state.get("sec_state")
        )

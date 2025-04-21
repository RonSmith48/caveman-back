MANDATORY_RING_STATES = [
    {"pri_state": "Abandoned", "sec_state": None},
    {"pri_state": "Bogging", "sec_state": None},
    {"pri_state": "Charged", "sec_state": None},
    {"pri_state": "Charged", "sec_state": "Incomplete"},
    {"pri_state": "Charged", "sec_state": "Charged Short"},
    {"pri_state": "Charged", "sec_state": "Recharged Holes"},
    {"pri_state": "Complete", "sec_state": None},
    {"pri_state": "Designed", "sec_state": None},
    {"pri_state": "Drilled", "sec_state": None},
    {"pri_state": "Drilled", "sec_state": "Redrilled"},
    {"pri_state": "Drilled", "sec_state": "Lost Rods"},
    {"pri_state": "Drilled", "sec_state": "BG Reported"},
    {"pri_state": "Drilled", "sec_state": "Making Water"},
    {"pri_state": "Drilled", "sec_state": "Incomplete"},
    {"pri_state": "Drilled", "sec_state": "Blocked Holes"},
    {"pri_state": "Drilled", "sec_state": "Had Cleanout"},
    {"pri_state": "Fired", "sec_state": None},
]

COMMENT_VISIBILITY_TARGETS = [
    {"key": "geology", "label": "Geology"},
    {"key": "handover_notes", "label": "Handover Notes"},
    {"key": "level_status_report", "label": "Level Status Report"},
    {"key": "ring_history", "label": "Ring History"},
]

COMMENT_NOTIFICATION_TARGETS = [
    {"key": "geotech", "label": "Geotechnical"},
    {"key": "mobile_maint", "label": "Mobile Maintenance"},
    {"key": "prod_shiftboss", "label": "Production Shiftboss"},
]

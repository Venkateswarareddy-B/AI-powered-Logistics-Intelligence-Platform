"""Shared constants used across all generator modules."""

from __future__ import annotations

# ── Service level SLA parameters ────────────────────────────────────────────
SERVICE_LEVELS = [
    {
        "service_level_id": "STANDARD",
        "name": "Standard",
        "description": "Standard ground delivery within 48 hours",
        "maximum_delivery_hours": 48.0,
        "allowed_delay_hours": 4.0,
        "is_active": True,
    },
    {
        "service_level_id": "EXPRESS",
        "name": "Express",
        "description": "Express delivery within 24 hours",
        "maximum_delivery_hours": 24.0,
        "allowed_delay_hours": 2.0,
        "is_active": True,
    },
    {
        "service_level_id": "SAME_DAY",
        "name": "Same Day",
        "description": "Same-day delivery within 8 hours",
        "maximum_delivery_hours": 8.0,
        "allowed_delay_hours": 1.0,
        "is_active": True,
    },
    {
        "service_level_id": "PRIORITY",
        "name": "Priority",
        "description": "Priority delivery within 12 hours",
        "maximum_delivery_hours": 12.0,
        "allowed_delay_hours": 1.5,
        "is_active": True,
    },
]

# ── Roles ────────────────────────────────────────────────────────────────────
ROLES = [
    {"role_id": "ADMIN",    "role_name": "Administrator", "description": "Full system access"},
    {"role_id": "PLANNER",  "role_name": "Planner",       "description": "Route and shipment planning"},
    {"role_id": "ANALYST",  "role_name": "Analyst",       "description": "Analytics and reporting"},
    {"role_id": "OPERATOR", "role_name": "Operator",      "description": "Warehouse and carrier ops"},
    {"role_id": "MANAGER",  "role_name": "Manager",       "description": "Operations management"},
]

# ── Carrier base delay factors ────────────────────────────────────────────────
CARRIER_BASE_DELAY_FACTORS = [1.00, 1.05, 1.08, 1.12, 1.15, 1.20, 1.03, 1.07]

# ── Facility types and their typical capacity ranges ─────────────────────────
FACILITY_TYPES = [
    "WAREHOUSE", "HUB", "DISTRIBUTION_CENTER", "SORTING_CENTER", "DELIVERY_CENTER"
]
FACILITY_CAPACITY_RANGE = {
    "WAREHOUSE": (200, 500),
    "HUB": (400, 800),
    "DISTRIBUTION_CENTER": (300, 700),
    "SORTING_CENTER": (150, 400),
    "DELIVERY_CENTER": (80, 200),
}

# ── Indian cities for realistic demo data ─────────────────────────────────────
INDIAN_CITIES = [
    ("Mumbai",     "Maharashtra", 19.0760,  72.8777),
    ("Delhi",      "Delhi",       28.7041,  77.1025),
    ("Bangalore",  "Karnataka",   12.9716,  77.5946),
    ("Hyderabad",  "Telangana",   17.3850,  78.4867),
    ("Chennai",    "Tamil Nadu",  13.0827,  80.2707),
    ("Kolkata",    "West Bengal", 22.5726,  88.3639),
    ("Pune",       "Maharashtra", 18.5204,  73.8567),
    ("Ahmedabad",  "Gujarat",     23.0225,  72.5714),
    ("Jaipur",     "Rajasthan",   26.9124,  75.7873),
    ("Surat",      "Gujarat",     21.1702,  72.8311),
    ("Lucknow",    "Uttar Pradesh", 26.8467, 80.9462),
    ("Kanpur",     "Uttar Pradesh", 26.4499, 80.3319),
    ("Nagpur",     "Maharashtra", 21.1458,  79.0882),
    ("Indore",     "Madhya Pradesh", 22.7196, 75.8577),
    ("Bhopal",     "Madhya Pradesh", 23.2599, 77.4126),
    ("Visakhapatnam", "Andhra Pradesh", 17.6868, 83.2185),
    ("Patna",      "Bihar",       25.5941,  85.1376),
    ("Vadodara",   "Gujarat",     22.3072,  73.1812),
    ("Ludhiana",   "Punjab",      30.9010,  75.8573),
    ("Agra",       "Uttar Pradesh", 27.1767, 78.0081),
]

# ── Weather type → delay factor (documented in schema) ───────────────────────
WEATHER_DELAY_FACTORS = {
    "NORMAL":       1.00,
    "RAIN":         1.15,
    "HEAVY_RAIN":   1.35,
    "STORM":        1.60,
    "FLOOD":        2.00,
    "EXTREME_HEAT": 1.10,
    "FOG":          1.25,
}

# ── Tracking event lifecycle order ────────────────────────────────────────────
EVENT_LIFECYCLE = [
    "PICKED_UP",
    "DEPARTED_FACILITY",
    "IN_TRANSIT",
    "ARRIVED_FACILITY",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
]

# ── Delay reason categories ────────────────────────────────────────────────────
DELAY_CATEGORIES = [
    "WEATHER", "FACILITY_CONGESTION", "CARRIER_ISSUE", "ROUTE_CHANGE",
    "CUSTOMS", "MECHANICAL", "TRAFFIC", "DEMAND_SURGE", "MISSING_SCAN", "OTHER",
]

# ── Shipment status weights (probability of each final status) ────────────────
SHIPMENT_STATUS_WEIGHTS = {
    "DELIVERED":        0.60,
    "IN_TRANSIT":       0.20,
    "AT_FACILITY":      0.08,
    "OUT_FOR_DELIVERY": 0.05,
    "PICKED_UP":        0.03,
    "EXCEPTION":        0.03,
    "CANCELLED":        0.01,
}

# Generation year
GENERATION_YEAR = 2026

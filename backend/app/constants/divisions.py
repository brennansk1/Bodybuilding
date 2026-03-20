# Division-specific ideal proportion vectors
# Each division has 11 measurement sites with ideal proportions
# relative to height. Values are circumference-to-height ratios.

DIVISION_VECTORS = {
    "mens_open": {
        "neck": 0.243, "shoulders": 0.618, "chest": 0.550,
        "bicep": 0.230, "forearm": 0.175, "waist": 0.447,
        "hips": 0.520, "thigh": 0.340, "calf": 0.230,
        # back_width: linear axillary breadth / height. Open = maximum lat spread target.
        "back_width": 0.265,
        "shoulder_to_waist": 1.382, "v_taper": 1.618,
    },
    "classic_physique": {
        "neck": 0.238, "shoulders": 0.600, "chest": 0.540,
        "bicep": 0.220, "forearm": 0.170, "waist": 0.432,
        "hips": 0.510, "thigh": 0.325, "calf": 0.225,
        "back_width": 0.258,
        "shoulder_to_waist": 1.389, "v_taper": 1.618,
    },
    "mens_physique": {
        "neck": 0.240, "shoulders": 0.690, "chest": 0.620,
        "bicep": 0.240, "forearm": 0.175, "waist": 0.430,
        "hips": 0.510, "thigh": 0.330, "calf": 0.225,
        # V-taper is a primary criterion — back width heavily weighted
        "back_width": 0.265,
        "shoulder_to_waist": 1.605, "v_taper": 1.618,
    },
    "womens_figure": {
        "neck": 0.195, "shoulders": 0.530, "chest": 0.490,
        "bicep": 0.170, "forearm": 0.145, "waist": 0.395,
        "hips": 0.530, "thigh": 0.320, "calf": 0.210,
        "back_width": 0.210,
        "shoulder_to_waist": 1.342, "v_taper": 1.341,
    },
    "womens_bikini": {
        "neck": 0.190, "shoulders": 0.500, "chest": 0.470,
        "bicep": 0.155, "forearm": 0.138, "waist": 0.385,
        "hips": 0.540, "thigh": 0.330, "calf": 0.205,
        "back_width": 0.198,
        "shoulder_to_waist": 1.299, "v_taper": 1.299,
    },
    "womens_physique": {
        "neck": 0.200, "shoulders": 0.550, "chest": 0.500,
        "bicep": 0.185, "forearm": 0.152, "waist": 0.405,
        "hips": 0.520, "thigh": 0.310, "calf": 0.215,
        "back_width": 0.220,
        "shoulder_to_waist": 1.358, "v_taper": 1.358,
    },
}

# Division ceiling factors: what fraction of Casey Butt genetic maximum
# each division targets per muscle site.  HQI 100 = at personal weight cap
# with ideal division proportions.  Men's Open aims for full genetic ceiling;
# other divisions trade absolute size for shape/aesthetics.
# Waist and hips are excluded — they use ratio × height (stay-small targets).
DIVISION_CEILING_FACTORS = {
    "mens_open": {
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0,
        "bicep": 1.0, "forearm": 1.0, "thigh": 1.0, "calf": 1.0,
        "back_width": 1.0,
    },
    "classic_physique": {
        "neck": 0.96, "shoulders": 0.97, "chest": 0.97,
        "bicep": 0.96, "forearm": 0.95, "thigh": 0.95, "calf": 0.95,
        "back_width": 0.97,
    },
    "mens_physique": {
        "neck": 0.88, "shoulders": 0.95, "chest": 0.90,
        "bicep": 0.92, "forearm": 0.88, "thigh": 0.78, "calf": 0.80,
        "back_width": 0.93,  # V-taper emphasis — near-maximum back width encouraged
    },
    "womens_figure": {
        "neck": 0.80, "shoulders": 0.85, "chest": 0.82,
        "bicep": 0.80, "forearm": 0.78, "thigh": 0.82, "calf": 0.80,
        "back_width": 0.82,
    },
    "womens_bikini": {
        "neck": 0.72, "shoulders": 0.75, "chest": 0.74,
        "bicep": 0.70, "forearm": 0.68, "thigh": 0.75, "calf": 0.72,
        "back_width": 0.75,
    },
    "womens_physique": {
        "neck": 0.85, "shoulders": 0.90, "chest": 0.88,
        "bicep": 0.87, "forearm": 0.85, "thigh": 0.87, "calf": 0.85,
        "back_width": 0.87,
    },
}

# Sites used for LCSA calculation with k-factors
# k_site adjusts tape circumference → lean cross-sectional area
K_SITE_FACTORS = {
    "neck": 0.85,
    "shoulders": 0.70,
    "chest": 0.75,
    "bicep": 0.90,
    "forearm": 0.92,
    "waist": 0.60,
    "hips": 0.65,
    "thigh": 0.80,
    "calf": 0.88,
    # back_width is a linear breadth measurement, not a circumference;
    # k=0.72 accounts for the non-circular cross-section of the back musculature
    "back_width": 0.72,
}

# ---------------------------------------------------------------------------
# Ghost Vectors — extended proportion vectors for the Volumetric Ghost Model
# ---------------------------------------------------------------------------
# These include the additional sites needed for the Hanavan segmental model:
#   chest_relaxed  — torso minor axis (relaxed tape, no lat flare)
#   chest_expanded — competition measurement (flexed/lat-spread)
#   proximal_thigh — upper thigh at glute fold (frustum large end)
#   distal_thigh   — lower thigh above knee (frustum small end)
#
# IMPORTANT: GHOST_VECTORS ≠ DIVISION_VECTORS. These encode the actual
# proportions of competitive athletes near the division weight cap, not the
# aesthetic shape ratios used for PDS scoring. Open/Classic athletes are
# significantly more muscular relative to height than MP/women's divisions.
# The allometric scaling (cube-root) only provides fine correction — the
# vectors themselves must produce a Hanavan mass close to the weight cap.
GHOST_VECTORS = {
    "mens_open": {
        # Open competitors at 180cm stage at 115-130+ kg; vectors calibrated
        # to produce Hanavan mass ~105-115 kg at reference height, minimizing
        # allometric correction. Based on elite natural Open stage measurements.
        "neck": 0.258, "shoulders": 0.760,
        "chest_relaxed": 0.640, "chest_expanded": 0.700,
        "bicep": 0.270, "forearm": 0.195,
        "waist": 0.465, "hips": 0.560,
        "proximal_thigh": 0.410, "distal_thigh": 0.340,
        "calf": 0.255, "back_width": 0.285,
    },
    "classic_physique": {
        # Classic at 180cm stage at ~96 kg. Between Open and MP in absolute
        # size but closer to Open in muscularity. IFBB Classic emphasizes
        # full-body development with slightly tighter waist than Open.
        "neck": 0.248, "shoulders": 0.710,
        "chest_relaxed": 0.580, "chest_expanded": 0.645,
        "bicep": 0.252, "forearm": 0.185,
        "waist": 0.440, "hips": 0.535,
        "proximal_thigh": 0.385, "distal_thigh": 0.315,
        "calf": 0.242, "back_width": 0.272,
    },
    "mens_physique": {
        "neck": 0.240, "shoulders": 0.690,
        "chest_relaxed": 0.560, "chest_expanded": 0.620,
        "bicep": 0.240, "forearm": 0.175,
        "waist": 0.430, "hips": 0.510,
        "proximal_thigh": 0.340, "distal_thigh": 0.280,
        "calf": 0.225, "back_width": 0.265,
    },
    "womens_figure": {
        # Figure at 165cm stages at ~59 kg. Vectors scaled +4% from base
        # to align Hanavan ghost mass with division weight caps.
        "neck": 0.203, "shoulders": 0.551,
        "chest_relaxed": 0.478, "chest_expanded": 0.510,
        "bicep": 0.177, "forearm": 0.151,
        "waist": 0.411, "hips": 0.551,
        "proximal_thigh": 0.359, "distal_thigh": 0.291,
        "calf": 0.218, "back_width": 0.218,
    },
    "womens_bikini": {
        "neck": 0.190, "shoulders": 0.500,
        "chest_relaxed": 0.440, "chest_expanded": 0.470,
        "bicep": 0.155, "forearm": 0.138,
        "waist": 0.385, "hips": 0.540,
        "proximal_thigh": 0.355, "distal_thigh": 0.290,
        "calf": 0.205, "back_width": 0.198,
    },
    "womens_physique": {
        # WP at 165cm stages at ~63 kg. Vectors scaled +7.5% from base
        # to align Hanavan ghost mass with division weight caps.
        "neck": 0.215, "shoulders": 0.591,
        "chest_relaxed": 0.505, "chest_expanded": 0.538,
        "bicep": 0.199, "forearm": 0.163,
        "waist": 0.435, "hips": 0.559,
        "proximal_thigh": 0.360, "distal_thigh": 0.296,
        "calf": 0.231, "back_width": 0.237,
    },
}

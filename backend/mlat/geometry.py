"""Coordinate math for MLAT.

MLAT solves in ECEF (Earth-Centered, Earth-Fixed) meters, then we convert the
answer back to lat/lon/alt. WGS84 ellipsoid.
"""

import math

# WGS84 constants
_A = 6378137.0                  # semi-major axis, meters
_F = 1.0 / 298.257223563        # flattening
_E2 = _F * (2 - _F)             # eccentricity squared


def geodetic_to_ecef(lat_deg, lon_deg, alt_m=0.0):
    """lat/lon (degrees) + altitude (meters) -> (x, y, z) in meters."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    n = _A / math.sqrt(1 - _E2 * sin_lat * sin_lat)

    x = (n + alt_m) * math.cos(lat) * math.cos(lon)
    y = (n + alt_m) * math.cos(lat) * math.sin(lon)
    z = (n * (1 - _E2) + alt_m) * sin_lat
    return x, y, z


def ecef_to_geodetic(x, y, z):
    """(x, y, z) meters -> (lat_deg, lon_deg, alt_m). Bowring's method."""
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    b = _A * (1 - _F)                 # semi-minor axis
    ep2 = (_A * _A - b * b) / (b * b)
    theta = math.atan2(z * _A, p * b)

    lat = math.atan2(
        z + ep2 * b * math.sin(theta) ** 3,
        p - _E2 * _A * math.cos(theta) ** 3,
    )
    n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
    alt = p / math.cos(lat) - n

    return math.degrees(lat), math.degrees(lon), alt


def distance_m(a, b):
    """Straight-line distance between two ECEF points, meters."""
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))

"""Multilateration solver (the real math).

Given the same signal heard by several receivers at known positions, each with a
precise time of arrival, we find where it came from.

Physics: the signal leaves the aircraft at unknown time t0 and travels at the
speed of light c. Receiver i hears it at t_i = t0 + |x - p_i| / c. Subtracting a
reference receiver removes the unknown t0 and leaves TDOA equations:

    |x - p_i| - |x - p_ref| = c * (t_i - t_ref)

Ground receivers all sit at nearly the same height, so vertical position is
almost unobservable. Real MLAT works around this the same way we do here: take
the aircraft's barometric altitude (from its Mode-C/ADS-B message) as known and
solve only latitude/longitude. That leaves 2 unknowns and is well-conditioned,
so >= 3 receivers is enough.

NOTE: this needs true sub-microsecond times of arrival. SBS/port-30003 data does
NOT carry them. Feed this Beast-format timing (see grouping.py) to go live. The
solver itself is complete and testable today with synthetic input.
"""

import numpy as np

from mlat.geometry import geodetic_to_ecef, ecef_to_geodetic

C = 299_792_458.0  # speed of light, m/s


def solve(receivers, altitude_m, max_iter=50, tol=1e-9):
    """Solve for the emitter's latitude/longitude at a known altitude.

    receivers: list of (position_ecef, toa_seconds), position in meters.
    altitude_m: aircraft barometric altitude, meters (from its own message).

    Returns ((lat_deg, lon_deg, altitude_m), rms_residual_m), or None if there
    are too few receivers.
    """
    if len(receivers) < 3:  # 2 unknowns need at least 2 TDOA equations
        return None

    positions = np.array([p for p, _ in receivers], dtype=float)
    toa = np.array([t for _, t in receivers], dtype=float)

    ref_pos = positions[0]
    others = positions[1:]
    range_diff = C * (toa[1:] - toa[0])  # measured |x-p_i| - |x-p_ref|

    def residual(lat, lon):
        x = np.array(geodetic_to_ecef(lat, lon, altitude_m))
        d_ref = np.linalg.norm(x - ref_pos)
        d_others = np.linalg.norm(others - x, axis=1)
        return (d_others - d_ref) - range_diff

    # Start from the geodetic centroid of the receivers.
    lat, lon, _ = ecef_to_geodetic(*positions.mean(axis=0))

    for _ in range(max_iter):
        r = residual(lat, lon)

        # Numerical Jacobian over (lat, lon). h ~ 1e-6 deg ~ 0.1 m.
        h = 1e-6
        jac = np.column_stack([
            (residual(lat + h, lon) - r) / h,
            (residual(lat, lon + h) - r) / h,
        ])

        step, *_ = np.linalg.lstsq(jac, -r, rcond=None)
        lat += step[0]
        lon += step[1]
        if np.linalg.norm(step) < tol:
            break

    r = residual(lat, lon)
    rms = float(np.sqrt(np.mean(r ** 2)))
    return (lat, lon, altitude_m), rms


if __name__ == "__main__":
    # Self-test: put 5 receivers around a known point, generate ideal times of
    # arrival, and check the solver recovers the point within a meter.
    from mlat.geometry import distance_m

    truth_alt = 10000.0
    truth = geodetic_to_ecef(27.70, 85.33, truth_alt)  # over Kathmandu, 10 km up
    rx_geo = [
        (27.67, 85.31, 1300),
        (27.72, 85.36, 1300),
        (27.65, 85.40, 1300),
        (27.74, 85.29, 1300),
        (27.60, 85.33, 1300),
    ]
    rxs = []
    for lat, lon, alt in rx_geo:
        p = geodetic_to_ecef(lat, lon, alt)
        toa = distance_m(truth, p) / C  # ideal arrival time (t0 = 0)
        rxs.append((p, toa))

    (lat, lon, alt), rms = solve(rxs, truth_alt)
    err = distance_m(geodetic_to_ecef(lat, lon, alt), truth)
    print(f"recovered: {lat:.5f}, {lon:.5f}, {alt:.0f} m")
    print(f"error: {err:.3f} m   rms residual: {rms:.3e} m")
    assert err < 1.0, "solver failed to recover the known point"
    print("OK")

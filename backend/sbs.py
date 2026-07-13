"""SBS-1 / BaseStation parser.

dump1090 port 30003 sends comma-separated SBS text lines. This turns one line
into a dict of only the fields that are present. One parser, used everywhere.

Field layout (0-indexed):
  0  message class (MSG, STA, ...)
  1  transmission type (1-8)
  4  ICAO24 hex id
  10 callsign
  11 altitude (feet)
  12 ground speed (knots)
  13 track (degrees)
  14 latitude
  15 longitude
  16 vertical rate (feet/min)
  17 squawk
  18 alert  19 emergency  20 spi  21 on-ground
"""


def _num(value, cast):
    value = value.strip()
    if not value:
        return None
    try:
        return cast(value)
    except ValueError:
        return None


def parse_sbs(line):
    """Parse one SBS line. Return a dict of present fields, or None if unusable."""
    parts = line.strip().split(",")
    if len(parts) < 22 or parts[0] != "MSG" or not parts[4]:
        return None

    icao = parts[4].strip().upper()
    if len(icao) != 6:
        return None

    out = {"icao24": icao, "msg_type": parts[1]}

    callsign = parts[10].strip()
    if callsign:
        out["callsign"] = callsign

    out["altitude"] = _num(parts[11], int)
    out["ground_speed"] = _num(parts[12], float)
    out["track"] = _num(parts[13], float)

    lat = _num(parts[14], float)
    lon = _num(parts[15], float)
    if lat is not None and -90 <= lat <= 90 and lon is not None and -180 <= lon <= 180:
        out["latitude"] = lat
        out["longitude"] = lon

    out["vertical_rate"] = _num(parts[16], int)

    squawk = parts[17].strip()
    if squawk:
        out["squawk"] = squawk

    out["alert"] = parts[18] == "1"
    out["emergency"] = parts[19] == "1"
    out["spi"] = parts[20] == "1"
    out["is_on_ground"] = parts[21].strip() == "1"

    # Drop keys that came back empty so callers can do a clean update.
    return {k: v for k, v in out.items() if v is not None}

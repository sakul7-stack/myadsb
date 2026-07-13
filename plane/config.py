"""Settings for app.py. Edit these to change how the tracker runs."""

# ADS-B source (dump1090 SBS output on port 30003)
SBS_HOST = ""          # receiver IP; 
SBS_PORT = 30003
RECONNECT_DELAY = 5    # seconds to wait before retrying the connection

# Aircraft tracking
AIRCRAFT_TIMEOUT = 120  # drop an aircraft after this many seconds of silence
CLEANUP_INTERVAL = 10   # how often to check for stale aircraft, seconds
MAX_POSITIONS = 700     # trail points kept per aircraft

# Web server
HOST = "0.0.0.0"
PORT = 5000

# Data files
FLAGS_FILE = "flags.json"

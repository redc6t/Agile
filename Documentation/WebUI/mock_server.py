"""Serve the Agile web UI (extracted from the firmware source) against mock data.

Used to produce the screenshots in Documentation/WebUI.md. The HTML and
JavaScript are taken verbatim from the HTML_HEAD / HTML_SCRIPT raw literals
of the sketch; only the JSON endpoints are faked. One small script is
appended so a screenshot can open the Config tab and select a circuit from
the URL hash (#config). The WebSocket is not emulated, so the Live tab runs
on its /data poll fallback.

Usage:
    python mock_server.py <path-to-LapTimer_vX.ino-or-.txt> [port]
    then open http://localhost:8765/  or  http://localhost:8765/#config
"""

import json
import math
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SRC = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765

with open(SRC, encoding="utf-8") as f:
    source = f.read()
parts = re.findall(r'R"rawliteral\((.*?)\)rawliteral"', source, re.S)
HTML_HEAD, HTML_SCRIPT = parts[0], parts[1]

HOOK = """<script>
window.addEventListener('load', function(){
  if (location.hash === '#config') {
    switchTab('config', document.querySelectorAll('.tabbar button')[1]);
    setTimeout(function(){ selectCircuit('Craigie'); }, 1500);
  }
});
</script>"""

# --- synthetic circuit (mock geometry, not a real track) -------------------
C_LAT, C_LON = -31.7790, 115.7700
M_LAT, M_LON = 1 / 111320.0, 1 / (111320.0 * math.cos(math.radians(C_LAT)))


def loop_point(t):
    """Rounded loop roughly 650 m x 300 m with a kink, t in 0..1."""
    a = 2 * math.pi * t
    x = 330 * math.cos(a) + 60 * math.cos(3 * a)
    y = 150 * math.sin(a) + 40 * math.sin(2 * a)
    return C_LAT + y * M_LAT, C_LON + x * M_LON


REF = [loop_point(i / 800.0) for i in range(801)]


def ll(dx, dy):
    return {"lat": C_LAT + dy * M_LAT, "lon": C_LON + dx * M_LON}


SF = [ll(390, -40), ll(390, 60)]          # across the track and the pit lane
ZONES = [
    {"type": 6, "label": "Start / Finish", "colour": "#00E5FF", "vertices": SF},
    {"type": 1, "label": "Pit Entry Line", "colour": "#FFA500",
     "vertices": [ll(300, 95), ll(320, 135)]},
    {"type": 3, "label": "Pits Zone", "colour": "#4fc3f7",
     "vertices": [ll(330, 75), ll(450, 75), ll(450, 115), ll(330, 115)]},
    {"type": 4, "label": "Fuel Zone", "colour": "#CE93D8",
     "vertices": [ll(370, 80), ll(410, 80), ll(410, 110), ll(370, 110)]},
    {"type": 2, "label": "Pit Exit Line", "colour": "#FFD54F",
     "vertices": [ll(470, 70), ll(480, 30)]},
]

state = {"polls": 0}

LAPS = [  # n, ms, delta, promoted, sectors (t, d)
    (1, 168420, 0, True, []),
    (2, 151230, -17190, True, [(17010, -820), (16220, -1440), (15980, -910)]),
    (3, 149870, -1360, True, [(16870, -140), (16050, -170), (16120, 140)]),
    (4, 151120, 1250, False, [(17110, 240), (16300, 250), (15990, -130)]),
    (5, 148960, -910, True, [(16790, -80), (15910, -140), (16010, -110)]),
]


def data():
    state["polls"] += 1
    k = min(state["polls"], len(LAPS)) - 1
    n, ms, delta, promoted, secs = LAPS[k]
    colours = [1, 2, 1, 1, 0, 2, 1, None, None]
    sectors = []
    for i, c in enumerate(colours):
        done = c is not None
        sectors.append({"completed": done, "delta_ms": [-120, 85, -40, -210, 0, 160, -30, 0, 0][i],
                        "cur_time_ms": 16000 if done else 0, "colour": c or 0})
    lat, lon = REF[610]
    return {
        "lap_number": 6, "lap_elapsed_ms": 112480, "live_delta_ms": -640,
        "sector_live_delta_ms": -90, "live_delta_valid": True, "bar_state": 0,
        "cumulative_delta_ms": -155, "estimated_lap_ms": 148320, "best_lap_ms": 148960,
        "lap_state": 2, "current_sector": 7, "sector_count": 9, "gnss_sats": 17,
        "gnss_pdop": 1.1, "gnss_hz": 10, "speed_kph": 87.4, "lat": lat, "lon": lon,
        "ref_ready": True, "car_state": "RUNNING", "log_dropped": 0, "wifi_rssi": -61,
        "heap_free": 145212, "lap_us_worst": 2210, "disp_us_worst": 18850,
        "ref_lap_ms": 148960,
        "gnss": {"baud": 460800, "req": 100, "act": 100, "nacks": 0, "auto": True,
                 "epochs": 41322},
        "gnss_meas_hz": 9.94, "gnss_worst_gap_ms": 212,
        "geo_active": "Craigie", "geo_zones": 5, "sf_len": 100, "sf_pts": 2,
        "style": "ROAD", "style_lat": 0.214, "gate_g": 0.209,
        "synth": {"cand": 58, "gate": 0.209, "dgate": 0, "dsf": 1, "clust": 13,
                  "dcap": 0, "ddur": 4, "lap_m": 1975, "sp_m": 117, "sp_ms": 1200,
                  "final": 9, "fb": False},
        "level_stale": False, "yaw_agreed": True, "lap_pitted": False,
        "timing_live": True, "sf_line": True, "bar_range_ms": 2000,
        "last_lap": {"n": n, "ms": ms, "delta": delta, "promoted": promoted,
                     "sc": len(secs)},
        "sectors": sectors,
        "last_sectors": [{"t": t, "d": d} for t, d in secs],
    }


ROUTES = {
    "/data": data,
    "/refpath": lambda: [{"lat": a, "lon": b} for a, b in REF],
    "/geozones": lambda: {"zones": ZONES},
    "/geo/list": lambda: {"Craigie": ZONES, "Wanneroo": [], "Collie": [], "Kewdale": []},
    "/pitstate": lambda: {"t": "flagstate", "yellow": True, "sc": False, "red": False},
    "/wifi": lambda: {"ssid": "MME_AP", "connected": True, "ip": "192.168.0.41",
                      "ip_mode": "dhcp", "rssi": -61, "from_nvs": False},
    "/update": lambda: {"version": "v0.17.0", "fw": "v0.17.0", "user": "mme", "auth": True,
                        "sketch_size": 1437696, "free_sketch": 2756608,
                        "free_space": 4194304, "running": "app0", "running_addr": 65536,
                        "running_size": 4194304, "target": "app1", "target_size": 4194304,
                        "ota_capable": True, "ready": False, "why": "lap in progress",
                        "active": False, "pct": 0},
    "/imu": lambda: {"roll": 1.42, "pitch": -3.18, "yaw": -7.5, "busy": False,
                     "mount": "DASH_VERTICAL", "suggest": -7.38, "conf": 71, "n": 3214},
    "/thr": lambda: {"brake": 0.20, "corner": 0.28, "accel": 0.16, "mindur": 200},
    "/logs": lambda: {"cur": 28, "full": False, "used_pages": 20512, "total_pages": 262080,
                      "sessions": [{"id": i, "bytes": 2032 * (90 + 37 * i)} for i in range(22, 29)]},
}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            body = (HTML_HEAD + HTML_SCRIPT.replace("</body>", HOOK + "</body>")).encode()
            ctype = "text/html; charset=utf-8"
        elif path in ROUTES:
            body = json.dumps(ROUTES[path]()).encode()
            ctype = "application/json"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Agile web UI mock on http://localhost:%d/" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()

"""Render every Agile TFT screen (firmware v0.17.0) to SVG.

The ST7789 panel is 284x76 after setRotation(3). This script emulates the
subset of Adafruit GFX the firmware uses (fillScreen, fillRect, drawRect,
setCursor, setTextSize, setTextColor with and without background, print with
wrap) and replays each screen with the same coordinates, strings and colours
as the source. Text uses a monospace font scaled to the 6x8 GFX glyph cell,
so layout, wrapping and truncation match the panel; glyph shapes are
approximate.

Usage:  python render_tft.py            (writes ./screens/*.svg)
"""

import os
from xml.sax.saxutils import escape

W, H = 284, 76
SCALE = 3
BEZEL = 5

# RGB565 colours from the firmware
COL_BLACK, COL_WHITE = 0x0000, 0xFFFF
COL_GREEN, COL_RED, COL_PURPLE = 0x07E0, 0xF800, 0x780F
COL_GRAY, COL_DARKGRAY = 0x4208, 0x2104
COL_ORANGE, COL_CYAN, COL_YELLOW = 0xFD20, 0x07FF, 0xFFE0
COL_AMBER_DIM, COL_BLUE_MID = 0x9B20, 0x213F
COL_MIDGRAY, COL_UNMAPPED = 0x7BEF, 0x10A2


def hex565(c):
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    return "#%02X%02X%02X" % (r * 255 // 31, g * 255 // 63, b * 255 // 31)


class Panel:
    def __init__(self):
        self.ops = []
        self.cx = self.cy = 0
        self.size = 1
        self.fg = COL_WHITE
        self.bg = None
        self.fill_screen(COL_BLACK)

    # --- GFX primitives -------------------------------------------------
    def fill_screen(self, c):
        self.ops = [("rect", 0, 0, W, H, c)]

    def fill_rect(self, x, y, w, h, c):
        if w > 0 and h > 0:
            self.ops.append(("rect", x, y, w, h, c))

    def draw_rect(self, x, y, w, h, c):
        self.ops.append(("frame", x, y, w, h, c))

    def set_cursor(self, x, y):
        self.cx, self.cy = x, y

    def set_text_size(self, s):
        self.size = s

    def set_text_color(self, fg, bg=None):
        self.fg, self.bg = fg, bg

    def print(self, text):
        cw, ch = 6 * self.size, 8 * self.size
        run_x, run_y, run = self.cx, self.cy, ""
        for c in text:
            if self.cx + cw > W:                     # Adafruit GFX wrap rule
                self._flush(run_x, run_y, run)
                self.cx, self.cy = 0, self.cy + ch
                run_x, run_y, run = self.cx, self.cy, ""
            if self.bg is not None:
                self.fill_rect(self.cx, self.cy, cw, ch, self.bg)
            run += c
            self.cx += cw
        self._flush(run_x, run_y, run)

    def _flush(self, x, y, run):
        if run.strip():
            self.ops.append(("text", x, y, self.size, self.fg, run))

    # --- SVG ------------------------------------------------------------
    def svg(self, title):
        ow, oh = W + 2 * BEZEL, H + 2 * BEZEL
        out = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" role="img" aria-label="%s">'
            % (ow * SCALE, oh * SCALE, ow, oh, escape(title)),
            "<title>%s</title>" % escape(title),
            '<rect x="0" y="0" width="%d" height="%d" rx="4" fill="#161616" '
            'stroke="#3a3a3a" stroke-width="0.6"/>' % (ow, oh),
            '<g transform="translate(%d,%d)" shape-rendering="crispEdges">'
            % (BEZEL, BEZEL),
            '<clipPath id="p"><rect width="%d" height="%d"/></clipPath>' % (W, H),
            '<g clip-path="url(#p)">',
        ]
        for op in self.ops:
            if op[0] == "rect":
                _, x, y, w, h, c = op
                out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                           % (x, y, w, h, hex565(c)))
            elif op[0] == "frame":
                _, x, y, w, h, c = op
                out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" '
                           'fill="none" stroke="%s" stroke-width="1"/>'
                           % (x + 0.5, y + 0.5, w - 1, h - 1, hex565(c)))
            else:
                _, x, y, s, c, run = op
                n = len(run)
                out.append(
                    '<text x="%d" y="%.1f" font-family="DejaVu Sans Mono,Consolas,'
                    'Menlo,monospace" font-size="%.2f" font-weight="bold" fill="%s" '
                    'textLength="%d" lengthAdjust="spacingAndGlyphs" '
                    'xml:space="preserve">%s</text>'
                    % (x, y + 7 * s, 9.6 * s, hex565(c), n * 6 * s - s, escape(run)))
        out += ["</g>", "</g>", "</svg>"]
        return "\n".join(out)


# ------------------------------------------------------------------------
# Firmware drawing routines, replayed
# ------------------------------------------------------------------------

def text_bounds_w(text, size):
    """getTextBounds() width with wrapping, as the classic GFX font does it."""
    x, minx, maxx = 0, W, -1
    cw = 6 * size
    for _ in text:
        if x + cw > W:
            x = 0
        minx, maxx = min(minx, x), max(maxx, x + cw - 1)
        x += cw
    return maxx - minx + 1


def centred(p, l1, l2, bg, fg):
    p.fill_screen(bg)
    p.set_text_color(fg)
    p.set_text_size(3)
    w = text_bounds_w(l1, 3)
    p.set_cursor((W - w) // 2, 8 if l2 else (H - 24) // 2)
    p.print(l1)
    if l2:
        p.set_text_size(2)
        w = text_bounds_w(l2, 2)
        p.set_cursor((W - w) // 2, 46)
        p.print(l2)


def idle(p, notice="none", sf_valid=True, level_stale=False, map_count=9,
         sats=14, pdop=1.2, circuit="Craigie", sf_tag="LINE", ip="192.168.0.41"):
    p.fill_screen(COL_BLACK)
    p.set_text_size(1)
    p.set_text_color(COL_CYAN, COL_BLACK)
    p.set_cursor(6, 2)
    p.print("Mullaloo Motorsport Engineering")
    p.set_text_color(COL_MIDGRAY, COL_BLACK)
    p.set_cursor(6, 12)
    p.print("AGILE - Predictive Delta Timer")

    col = COL_WHITE
    if notice == "map_prompt":
        col, buf = COL_YELLOW, "MAP %u SEC: OK=USE HOLD=NEW" % map_count
    elif notice == "map_loaded":
        col, buf = COL_GREEN, "MAP OK - CROSS LINE"
    elif notice == "recon_abort":
        col, buf = COL_ORANGE, "RECON ABORTED"
    elif notice == "low_events":
        col, buf = COL_ORANGE, "CHECK IMU MOUNT"
    elif level_stale:
        col, buf = COL_ORANGE, "LEVEL ME"
    else:
        buf = "DRIVE TO START LINE" if sf_valid else "DRIVE TO START & SET"
    p.set_text_size(2)
    p.set_text_color(col, COL_BLACK)
    p.set_cursor(6, 24)
    p.print(buf[:21].ljust(21))                      # idlePad(.., IDLE_W_NOTICE)

    p.set_text_size(1)
    p.set_text_color(COL_WHITE, COL_BLACK)
    p.set_cursor(6, 48)
    row = "SAT %u PDOP %.1f %s S/F:%s" % (sats, pdop, circuit, sf_tag)
    p.print(row[:40].ljust(40))

    foot = "LapTimer v0.17.0" + ("  " + ip if ip else "")
    p.set_text_color(COL_DARKGRAY, COL_BLACK)
    p.set_cursor(6, 66)
    p.print(foot[:45].ljust(45))


LADDER = [500, 1000, 2000, 5000, 10000, 20000, 30000]


def bar_fraction(d, full):
    mag = min(abs(d), full)
    knee = full * 0.25
    f = 0.5 * mag / knee if mag <= knee else 0.5 + 0.5 * (mag - knee) / (full - knee)
    return f if d < 0 else -f


def dash(p, delta=0, bar_state="ok", bar_range=1000, cumul=0, est=0,
         sectors=None, current=0, sector_live=0):
    """OWN_NORMAL: delta bar + info row + micro-sector strip."""
    p.fill_screen(COL_BLACK)
    cx, half = W // 2, W // 2 - 1
    # --- drawDeltaBarTime ---
    if bar_state == "noref":
        p.fill_rect(cx - 48, 9, 96, 10, COL_AMBER_DIM)
    elif bar_state == "gray":
        p.fill_rect(cx - 48, 9, 96, 10, COL_GRAY)
    elif bar_state == "ok":
        sw = int(bar_fraction(delta, bar_range) * half)
        if sw < 0:
            p.fill_rect(cx - 1 + sw, 2, -sw, 24, COL_RED)
        elif sw > 0:
            p.fill_rect(cx + 2, 2, sw, 24, COL_GREEN)
    p.fill_rect(cx - 1, 0, 3, 28, COL_WHITE)
    if bar_state == "ok":
        lbl = ("%ds" % (bar_range // 1000)) if bar_range >= 1000 else ("%dms" % bar_range)
        p.fill_rect(W - 26, 0, 26, 9, COL_BLACK)
        p.set_text_size(1)
        p.set_text_color(COL_GRAY, COL_BLACK)
        p.set_cursor(W - 24, 1)
        p.print(lbl)
    # --- drawInfoRow ---
    p.set_text_size(2)
    q = int(cumul / 1000)                            # C truncation toward zero
    r = abs(int(cumul - q * 1000))
    txt = "%+d.%03d" % (q, r)
    p.set_text_color(COL_RED if cumul > 10 else COL_GREEN if cumul < -10 else COL_GRAY)
    p.set_cursor(6, 33)
    p.print(txt)
    if est > 0:
        e = "%d:%02d.%03d" % (est // 60000, (est % 60000) // 1000, est % 1000)
        p.set_text_color(COL_WHITE)
        p.set_cursor(W - 6 - len(e) * 12, 33)
        p.print(e)
    # --- drawSectorBar ---
    sectors = sectors or []
    n = max(1, min(32, len(sectors)))
    seg = W // n
    x0 = (W - seg * n) // 2
    bias = 0
    if bar_state == "ok":
        bias = 1 if sector_live < -10 else -1 if sector_live > 10 else 0
    cmap = {0: COL_GRAY, 1: COL_GREEN, 2: COL_RED, 3: COL_PURPLE}
    for i in range(n):
        x = x0 + i * seg
        if i >= len(sectors):
            p.fill_rect(x + 1, 52, seg - 2, 22, COL_UNMAPPED)
        elif i == current and sectors[i] is None:
            p.fill_rect(x + 1, 52, seg - 2, 22, COL_DARKGRAY)
            ws = (seg - 2) * 2 // 3
            xo = x + 1 + (seg - 2 - ws) if bias > 0 else x + 1 if bias < 0 \
                else x + 1 + (seg - 2 - ws) // 2
            p.fill_rect(xo, 52, ws, 22, COL_WHITE)
        elif sectors[i] is not None:
            p.fill_rect(x + 1, 52, seg - 2, 22, cmap[sectors[i]])
        else:
            p.fill_rect(x + 1, 52, seg - 2, 22, COL_DARKGRAY)


def diag(p, title, rows):
    p.fill_screen(COL_BLACK)
    p.set_text_size(1)
    p.set_text_color(COL_CYAN, COL_BLACK)
    p.set_cursor(6, 2)
    p.print(title)
    p.set_text_color(COL_WHITE, COL_BLACK)
    for i, r in enumerate(rows):
        p.set_cursor(6, 16 + i * 11)
        p.print(r)


def boot(p, imu_ok=True, upright=True, az=1.00, gnss="ok", log_ok=True, ota=True):
    p.fill_screen(COL_BLACK)
    p.set_text_size(2)
    p.set_text_color(COL_CYAN)
    p.set_cursor(6, 6)
    p.print("LapTimer v0.17.0")
    p.set_text_color(COL_WHITE)
    p.set_cursor(6, 30)
    p.set_text_size(1)
    p.print("booting...")
    p.set_cursor(6, 56)
    if imu_ok and not upright:
        p.set_text_color(COL_RED)
        p.print("IMU MOUNT? vert %+.2fG (want +1.00)" % az)
    elif imu_ok:
        p.set_text_color(COL_GREEN)
        p.print("IMU vert %+.2fG" % az)
    p.set_cursor(6, 44)
    p.set_text_color(COL_GREEN if imu_ok else COL_RED)
    p.print("IMU OK" if imu_ok else "IMU FAIL")
    p.set_cursor(80, 44)
    p.set_text_color(COL_RED if gnss == "fail" else COL_GREEN)
    p.print("GNSS FAIL" if gnss == "fail" else "GNSS OK")
    p.set_cursor(6, 66)
    if gnss == "fail":
        p.set_text_color(COL_RED, COL_BLACK)
        p.print("GNSS FAIL")
    elif gnss == "low":
        p.set_text_color(COL_ORANGE, COL_BLACK)
        p.print("GNSS 5Hz (want 10) nack2")
    else:
        p.set_text_color(COL_GREEN, COL_BLACK)
        p.print("GNSS 10Hz 460k8")
    p.set_cursor(160, 44)
    p.set_text_color(COL_GREEN if log_ok else COL_GRAY)
    p.print("LOG OK" if log_ok else "LOG --")
    p.set_cursor(220, 44)
    p.set_text_color(COL_GRAY)
    p.print("CAN --")
    p.set_cursor(6, 58)
    p.set_text_color(COL_GREEN if ota else COL_RED)
    p.print("OTA app0>app1" if ota else "OTA NO SLOT")


def export(p, mode="ready", pct=0):
    p.fill_screen(COL_BLACK)
    p.set_text_size(2)
    p.set_text_color(COL_CYAN)
    p.set_cursor(6, 4)
    p.print("USB LOG EXPORT")
    p.set_text_size(1)
    p.set_text_color(COL_WHITE)
    if mode == "no_tinyusb":
        p.set_cursor(6, 30)
        p.set_text_color(COL_RED)
        p.print("BUILD LACKS TinyUSB MSC")
        p.set_cursor(6, 44)
        p.set_text_color(COL_WHITE)
        p.print("Rebuild: USB Mode = USB-OTG (TinyUSB)")
    elif mode == "wiping":
        p.set_cursor(6, 30)
        p.print("ERASING ALL LOGS...")
        p.draw_rect(6, 44, 272, 12, COL_WHITE)
        p.fill_rect(8, 46, 268 * pct // 100, 8, COL_RED)
    else:
        p.set_cursor(6, 28)
        p.print("27 sessions  39/508 MB used")
        p.set_cursor(6, 42)
        p.set_text_color(COL_GREEN)
        p.print("Connect USB-C to PC (read-only)")
        p.set_cursor(6, 56)
        p.set_text_color(COL_GRAY)
        p.print("Hold OK 5s = ERASE ALL LOGS")
        p.set_cursor(6, 66)
        p.print("Power via RAW_BATT required")
        if mode == "nand_fail":
            p.set_cursor(6, 30)
            p.set_text_color(COL_RED)
            p.print("NAND INIT FAILED")


def ota(p, title="FIRMWARE UPDATE", pct=42, msg="writing", fail=False):
    p.fill_screen(COL_BLACK)
    p.set_text_size(2)
    p.set_text_color(COL_RED if fail else COL_CYAN)
    p.set_cursor(6, 4)
    p.print("OTA FAILED" if fail else title)
    p.draw_rect(6, 30, W - 12, 18, COL_WHITE)
    p.fill_rect(8, 32, (W - 16) * pct // 100, 14, COL_RED if fail else COL_GREEN)
    p.set_text_size(1)
    p.set_text_color(COL_WHITE, COL_BLACK)
    p.set_cursor(6, 54)
    p.print(("%3u%%  %-26.26s" % (pct, msg)))
    p.set_cursor(6, 66)
    p.set_text_color(COL_GRAY if fail else COL_AMBER_DIM, COL_BLACK)
    p.print("resuming - nothing written   " if fail else "DO NOT POWER OFF             ")


def synth_detail(p):
    p.fill_screen(COL_BLACK)
    p.set_text_size(1)
    p.set_text_color(COL_CYAN, COL_BLACK)
    p.set_cursor(4, 2)
    p.print("SYNTH  1975m  gate 0.21G")
    p.set_text_color(COL_WHITE, COL_BLACK)
    for y, t in ((15, "cand 58 -> clust 13 -> FINAL 9"),
                 (27, "drop: gate 0  sf 1  cap 0  dur 4"),
                 (39, "spacing 117m / 1200ms")):
        p.set_cursor(4, y)
        p.print(t)
    p.set_cursor(4, 51)
    p.set_text_color(COL_GREEN, COL_BLACK)
    p.print("OK  p95lat 0.21G")
    p.set_text_color(COL_GRAY, COL_BLACK)
    p.set_cursor(4, 64)
    p.print("release DOWN to return")


# ------------------------------------------------------------------------
# Scenario catalogue: (file, title, builder)
# ------------------------------------------------------------------------

G, R, X = 1, 2, 0          # sector colours: green, red, gray
NINE_DONE = [G, R, G, G, X, R, G, G, R]

SCREENS = [
    # Boot
    ("boot_ok", "Boot splash, all subsystems OK", lambda p: boot(p)),
    ("boot_gnss_low", "Boot splash, GNSS below target rate",
     lambda p: boot(p, gnss="low")),
    ("boot_faults", "Boot splash, IMU and GNSS failed, no log store",
     lambda p: boot(p, imu_ok=False, gnss="fail", log_ok=False)),
    ("boot_imu_mount", "Boot splash, IMU mounted upside down",
     lambda p: boot(p, upright=False, az=-0.98)),
    ("boot_no_ota", "Boot splash, no second OTA slot",
     lambda p: boot(p, ota=False)),
    # Diagnostic pages
    ("diag_1_firmware", "Diagnostic page 1/5, firmware", lambda p: diag(p, "1/5  FIRMWARE", [
        "FW  v0.17.0", "Heap 142 KB free", "PSRAM 8071 KB free",
        "Trace DUAL (promotion armed)", "Flash 16 MB"])),
    ("diag_2_gnss", "Diagnostic page 2/5, GNSS", lambda p: diag(p, "2/5  GNSS", [
        "Baud   460800", "Rate   req 100ms  act 100ms", "       = 10 Hz OK",
        "meas 9.94Hz  worst gap 212ms", "GPS L1 GAL E1/E5a BDS B1C/B2a"])),
    ("diag_3_imu", "Diagnostic page 3/5, IMU", lambda p: diag(p, "3/5  IMU", [
        "Mount  DASH_VERTICAL", "Trim   roll +1.4  pitch -3.2",
        "Yaw    -7.5 deg (manual)", "Vert   +1.00G OK", "Thr    0.20/0.28/0.16 200ms"])),
    ("diag_4_store", "Diagnostic page 4/5, log store", lambda p: diag(p, "4/5  STORE", [
        "Session 28", "Pages   20512 / 262080", "Used    7%",
        "Sessions 27 stored", "Geo Craigie  S/F line"])),
    ("diag_5_wifi", "Diagnostic page 5/5, Wi-Fi", lambda p: diag(p, "5/5  WIFI", [
        "SSID   MME_AP", "State  connected", "IP     192.168.0.41",
        "RSSI   -61 dBm", "OK to exit"])),
    # USB export
    ("export_ready", "USB log export, ready", lambda p: export(p)),
    ("export_wiping", "USB log export, erasing all logs", lambda p: export(p, "wiping", 63)),
    ("export_no_tinyusb", "USB log export, build without TinyUSB",
     lambda p: export(p, "no_tinyusb")),
    # Idle
    ("idle_drive_to_line", "Idle, circuit armed, waiting for the S/F line",
     lambda p: idle(p)),
    ("idle_no_sf", "Idle, no circuit and no S/F", lambda p: idle(
        p, sf_valid=False, circuit="NO CIRCUIT", sf_tag="NONE", ip="", sats=9, pdop=2.1)),
    ("idle_legacy_point", "Idle, legacy point S/F only", lambda p: idle(
        p, circuit="NO CIRCUIT", sf_tag="PT")),
    ("idle_level_me", "Idle, IMU trim stale (LEVEL ME)", lambda p: idle(p, level_stale=True)),
    ("idle_map_prompt", "Idle, stored sector map offered", lambda p: idle(p, notice="map_prompt")),
    ("idle_map_loaded", "Idle, stored map accepted", lambda p: idle(p, notice="map_loaded")),
    ("idle_recon_aborted", "Idle, recon lap aborted (stationary)",
     lambda p: idle(p, notice="recon_abort")),
    ("idle_check_imu", "Idle, synthesis fell back (CHECK IMU MOUNT)",
     lambda p: idle(p, notice="low_events")),
    # Recon and approve
    ("recon_lap", "Recon lap in progress (no sectors yet)",
     lambda p: dash(p, bar_state="off", sectors=[])),
    ("approve", "Recon approve overlay", lambda p: centred(
        p, "ROAD 9 SEC", "OK=KEEP HOLD=REDO 12s", COL_BLACK, COL_CYAN)),
    ("approve_slow_recon", "Recon approve overlay, SLOW RECON style (text overflows)",
     lambda p: centred(p, "SLOW RECON 9 SEC", "OK=KEEP HOLD=REDO 12s", COL_BLACK, COL_CYAN)),
    ("synth_detail", "Synthesis breakdown (DOWN held on approve)", synth_detail),
    # Racing dash
    ("race_gaining", "Racing, gaining 0.8 s, 1 s scale", lambda p: dash(
        p, delta=-820, bar_range=1000, cumul=-1234, est=146512,
        sectors=[G, G, R, G, None, None, None, None, None], current=4, sector_live=-120)),
    ("race_losing", "Racing, losing 3.4 s, 5 s scale", lambda p: dash(
        p, delta=3400, bar_range=5000, cumul=2870, est=151020,
        sectors=[R, R, G, R, R, R, None, None, None], current=6, sector_live=340)),
    ("race_small_delta", "Racing, +0.15 s on a 0.5 s scale", lambda p: dash(
        p, delta=150, bar_range=500, cumul=60, est=147800,
        sectors=[G, R, G, None, None, None, None, None, None], current=3, sector_live=0)),
    ("race_negative_subsecond", "Racing, cumulative -0.412 s (prints +0.412)",
     lambda p: dash(p, delta=-412, bar_range=1000, cumul=-412, est=147100,
                    sectors=[G, R, None, None, None, None, None, None, None],
                    current=2, sector_live=-40)),
    ("race_noref", "Racing, no reference yet (lap after a stored map, or delta lost)",
     lambda p: dash(p, bar_state="noref", cumul=0,
                    sectors=[X, X, None, None, None, None, None, None, None], current=2)),
    ("race_gray", "Racing, active sector too short to time (BAR_GRAY)",
     lambda p: dash(p, bar_state="gray", cumul=-310, est=146900,
                    sectors=[G, G, G, R, None, None, None, None, None], current=4)),
    ("race_outlap", "Racing, out-lap after the pits (gray until rejoin)",
     lambda p: dash(p, bar_state="noref", cumul=0,
                    sectors=[X, X, X, G, None, None, None, None, None], current=4)),
    ("race_lap_complete", "Racing, all nine sectors completed", lambda p: dash(
        p, delta=-150, bar_range=2000, cumul=-640, est=0, sectors=NINE_DONE, current=9)),
    ("race_32_sectors", "Racing, 32-sector circuit", lambda p: dash(
        p, delta=-6200, bar_range=10000, cumul=-5900, est=152300,
        sectors=[G, G, R, G, G, X, G, R, G, G, R, G, G, G, R, G, G, G, G]
        + [None] * 13, current=19, sector_live=-200)),
    # Car state
    ("car_pit_entry", "Car state PIT ENTRY", lambda p: centred(
        p, "PIT ENTRY", "SLOW DOWN", COL_WHITE, COL_BLACK)),
    ("car_pits", "Car state PITS", lambda p: centred(p, "PITS", None, COL_BLACK, COL_ORANGE)),
    ("car_refueling", "Car state FUELLING", lambda p: centred(
        p, "REFUELING", None, COL_ORANGE, COL_BLACK)),
    ("car_pit_exit", "Car state PIT EXIT", lambda p: centred(
        p, "PIT EXIT", "PUSH", COL_WHITE, COL_BLACK)),
    ("custom_zone", "Custom geofence zone override", lambda p: centred(
        p, "Custom", None, COL_GRAY, COL_WHITE)),
    # Pit board
    ("pit_request", "Pit message PIT REQUEST", lambda p: centred(
        p, "PIT REQUEST", None, COL_BLUE_MID, COL_WHITE)),
    ("pit_now", "Pit message PIT NOW", lambda p: centred(
        p, "PIT NOW", None, COL_BLUE_MID, COL_WHITE)),
    ("pit_update_req", "Pit message UPDATE REQ", lambda p: centred(
        p, "UPDATE REQ", None, COL_BLUE_MID, COL_WHITE)),
    ("pit_more_pace", "Pit message MORE PACE", lambda p: centred(
        p, "MORE PACE", None, COL_BLUE_MID, COL_WHITE)),
    ("pit_less_pace", "Pit message LESS PACE", lambda p: centred(
        p, "LESS PACE", None, COL_BLUE_MID, COL_WHITE)),
    ("flag_yellow", "Latched YELLOW FLAG", lambda p: centred(
        p, "YELLOW FLAG", None, COL_YELLOW, COL_BLACK)),
    ("flag_safety_car", "Latched SAFETY CAR", lambda p: centred(
        p, "SAFETY CAR", None, COL_ORANGE, COL_BLACK)),
    ("flag_red", "Latched RED FLAG", lambda p: centred(
        p, "RED FLAG", None, COL_RED, COL_WHITE)),
    # Button hold feedback
    ("hold_short", "OK held 0.9-1.2 s (no action on release)", lambda p: centred(
        p, "HOLD...", "RELEASE = NO ACTION", COL_BLACK, COL_GRAY)),
    ("hold_sf", "OK held 1.2-10 s (release sets S/F)", lambda p: centred(
        p, "SET S/F", "HOLD 10s = IMU RESET", COL_BLACK, COL_CYAN)),
    ("hold_imu", "OK held 10 s+ (release levels the IMU)", lambda p: centred(
        p, "IMU RESET", "RELEASE NOW", COL_BLACK, COL_GREEN)),
    # Toasts
    ("toast_sf_set", "Toast: S/F SET", lambda p: centred(p, "S/F SET", None, COL_BLACK, COL_CYAN)),
    ("toast_sf_not_set", "Toast: S/F NOT SET", lambda p: centred(
        p, "S/F NOT SET", "NO GNSS FIX", COL_BLACK, COL_ORANGE)),
    ("toast_imu_sampling", "Toast: IMU reset sampling", lambda p: centred(
        p, "IMU RESET", "SAMPLING - HOLD STILL", COL_BLACK, COL_CYAN)),
    ("toast_imu_ok", "Toast: IMU reset succeeded", lambda p: centred(
        p, "IMU RESET", "SUCCESSFULLY", COL_BLACK, COL_GREEN)),
    ("toast_imu_fail", "Toast: IMU reset failed", lambda p: centred(
        p, "IMU RESET", "FAILED - HOLD STILL", COL_BLACK, COL_RED)),
    ("toast_memory_cleared", "Toast: learned state cleared", lambda p: centred(
        p, "MEMORY", "CLEARED", COL_BLACK, COL_ORANGE)),
    ("toast_memory_cleared_sf", "Toast: learned state and S/F cleared", lambda p: centred(
        p, "MEMORY", "CLEARED + S/F", COL_BLACK, COL_ORANGE)),
    ("toast_reset_cancelled", "Toast: reset cancelled", lambda p: centred(
        p, "RESET", "CANCELLED", COL_BLACK, COL_CYAN)),
    # Learned-state reset
    ("nuke_armed", "Learned-state reset armed (countdown)", lambda p: centred(
        p, "ERASE MEMORY?", "OK=CANCEL  wiping in 4s", COL_BLACK, COL_ORANGE)),
    # OTA
    ("ota_progress", "OTA firmware update in progress", lambda p: ota(p)),
    ("ota_verified", "OTA verified, rebooting", lambda p: ota(
        p, pct=100, msg="verified - rebooting")),
    ("ota_failed", "OTA failed (shown briefly before tasks resume)", lambda p: ota(
        p, pct=17, msg="Flash Write Failed", fail=True)),
    ("ota_rebooting", "Web reboot, committing the log page", lambda p: ota(
        p, title="REBOOTING", pct=100, msg="committing log")),
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "screens")
    os.makedirs(out, exist_ok=True)
    for name, title, build in SCREENS:
        p = Panel()
        build(p)
        with open(os.path.join(out, name + ".svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(p.svg(title))
    print("wrote %d screens to %s" % (len(SCREENS), out))


if __name__ == "__main__":
    main()

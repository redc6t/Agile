"""G-meter session stats (firmware v1.1.0) recomputed from an Agile log file.

Two independent paths over the same CSV:

  GStats      mirrors gsEpoch() in the firmware, epoch by epoch, including
              the dt rule (iTOW step to the previous row, > 500 ms = 0) and
              the session / lap blocks. mock_server.py replays logs with it.
  hand()      recomputes each stat straight from the filtered rows, as you
              would in a spreadsheet: filter, then sum / min / max.

Rows counted: lap running (state != 0) and speed >= 10 km/h. Phase test
order brake, corner, accel, as the recon detector, on the reporting
thresholds (default 0.20 / 0.28 / 0.16 g; pass others with --thr).

Usage:
    python gstats_check.py <LOG_xxxx.CSV> [--thr 0.20,0.28,0.16]
"""

import csv
import sys

MIN_KPH = 10.0
MAX_DT_MS = 500
COAST, BRAKE, CORNER, ACCEL = 0, 1, 2, 3
NAMES = ["coast", "brake", "corner", "accel"]


def phase_of(ax, ay, thr):
    b, c, a = thr
    if ax < -b:
        return BRAKE
    if abs(ay) > c:
        return CORNER
    if ax > a:
        return ACCEL
    return COAST


def read_rows(path):
    """Data rows of a log file; '#' rows (events, padding) are skipped."""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    rows = []
    for r in csv.DictReader(lines):
        try:
            rows.append({"itow": int(r["iTOW"]), "v": float(r["speed_kph"]),
                         "ax": float(r["along_g"]), "ay": float(r["lat_g"]),
                         "lap": int(r["lap"]), "state": int(r["state"])})
        except (KeyError, ValueError, TypeError):
            continue
    return rows


def new_block():
    return {"t": [0, 0, 0, 0], "cv": 0.0, "bg": 0.0, "cmin": 0.0,
            "bpk": 0.0, "lpk": 0.0, "apk": 0.0}


def summary(b):
    """The figures /data gs.s / gs.l carries."""
    t = b["t"]
    return {"t": list(t),
            "cav": b["cv"] / t[CORNER] if t[CORNER] else 0.0, "cmin": b["cmin"],
            "bpk": b["bpk"], "bav": b["bg"] / t[BRAKE] if t[BRAKE] else 0.0,
            "lpk": b["lpk"], "apk": b["apk"]}


class GStats:
    """Mirror of the firmware accumulator (gsEpoch / gsSync)."""

    def __init__(self, thr=(0.20, 0.28, 0.16)):
        self.thr = thr
        self.prev = None
        self.ses = new_block()
        self.lap = new_block()
        self.lap_n = None
        self.last = (0.0, 0.0, COAST, 0.0)      # ax, ay, ph, v

    def epoch(self, itow, v, ax, ay, lap, counting):
        dt = 0
        if self.prev is not None:
            dt = itow - self.prev
            if dt < 0:
                dt += 604800000
            if dt > MAX_DT_MS:
                dt = 0
        self.prev = itow
        ph = phase_of(ax, ay, self.thr)
        self.last = (ax, ay, ph, v)
        if lap != self.lap_n:
            self.lap, self.lap_n = new_block(), lap
        if not counting or v < MIN_KPH:
            return
        for a in (self.ses, self.lap):
            a["t"][ph] += dt
            a["lpk"] = max(a["lpk"], abs(ay))
            if ph == CORNER:
                a["cv"] += v * dt
                if a["cmin"] == 0.0 or v < a["cmin"]:
                    a["cmin"] = v
            elif ph == BRAKE:
                a["bg"] += -ax * dt
                a["bpk"] = max(a["bpk"], -ax)
            elif ph == ACCEL:
                a["apk"] = max(a["apk"], ax)


def mirror(rows, thr):
    g = GStats(thr)
    laps = {}
    for r in rows:
        g.epoch(r["itow"], r["v"], r["ax"], r["ay"], r["lap"], r["state"] != 0)
        laps[g.lap_n] = summary(g.lap)
    return summary(g.ses), laps


def hand(rows, thr):
    """Spreadsheet-style: weight column, filter, then aggregate."""
    w = [0]
    for p, r in zip(rows, rows[1:]):
        d = (r["itow"] - p["itow"]) % 604800000
        w.append(d if d <= MAX_DT_MS else 0)
    kept = [(wi, r, phase_of(r["ax"], r["ay"], thr))
            for wi, r in zip(w, rows) if r["state"] != 0 and r["v"] >= MIN_KPH]
    corner = [(wi, r) for wi, r, ph in kept if ph == CORNER]
    brake = [(wi, r) for wi, r, ph in kept if ph == BRAKE]
    accel = [(wi, r) for wi, r, ph in kept if ph == ACCEL]
    t = [sum(wi for wi, _, ph in kept if ph == k) for k in range(4)]
    tc, tb = sum(wi for wi, _ in corner), sum(wi for wi, _ in brake)
    return {"t": t,
            "cav": sum(wi * r["v"] for wi, r in corner) / tc if tc else 0.0,
            "cmin": min((r["v"] for _, r in corner), default=0.0),
            "bpk": max((-r["ax"] for _, r in brake), default=0.0),
            "bav": sum(wi * -r["ax"] for wi, r in brake) / tb if tb else 0.0,
            "lpk": max((abs(r["ay"]) for _, r, _ in kept), default=0.0),
            "apk": max((r["ax"] for _, r in accel), default=0.0)}


def fmt(s):
    tot = sum(s["t"]) or 1
    pc = [100.0 * s["t"][k] / tot for k in (BRAKE, CORNER, ACCEL, COAST)]
    return {"Avg cornering speed": "%.1f km/h" % s["cav"],
            "Min cornering speed": "%.1f km/h" % s["cmin"],
            "Peak braking": "%.3f g" % s["bpk"],
            "Avg braking": "%.3f g" % s["bav"],
            "Peak lateral": "%.3f g" % s["lpk"],
            "Peak acceleration": "%.3f g" % s["apk"],
            "Time split B/C/A/Co": "%.1f / %.1f / %.1f / %.1f %%" % tuple(pc),
            "Counted time": "%.1f s" % (sum(s["t"]) / 1000.0)}


def main():
    path = sys.argv[1]
    thr = (0.20, 0.28, 0.16)
    if "--thr" in sys.argv:
        thr = tuple(float(x) for x in sys.argv[sys.argv.index("--thr") + 1].split(","))
    rows = read_rows(path)
    ses, laps = mirror(rows, thr)
    ref = hand(rows, thr)
    a, b = fmt(ses), fmt(ref)
    print("%s: %d rows, thresholds %s g\n" % (path, len(rows), "/".join("%.2f" % x for x in thr)))
    print("| Stat | Firmware mirror | Hand check | Match |")
    print("|---|---|---|---|")
    ok = True
    for k in a:
        m = a[k] == b[k]
        ok &= m
        print("| %s | %s | %s | %s |" % (k, a[k], b[k], "yes" if m else "NO"))
    print("\nPer lap (firmware mirror, lap block at the end of each lap):\n")
    print("| Lap | Avg corner | Min corner | Peak brake | Avg brake | Peak lat | Peak accel | B/C/A/Co % |")
    print("|---|---|---|---|---|---|---|---|")
    for n, s in laps.items():
        if not sum(s["t"]):
            continue
        f = fmt(s)
        print("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            n, f["Avg cornering speed"], f["Min cornering speed"], f["Peak braking"],
            f["Avg braking"], f["Peak lateral"], f["Peak acceleration"],
            f["Time split B/C/A/Co"].replace(" %", "")))
    print("\nALL MATCH" if ok else "\nMISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

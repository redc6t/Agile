"""Build derived, analysis-ready files from a folder of raw Agile unit logs (LOG_nnnn.CSV).

Raw logs are never modified. Outputs go to <session>/derived/:
  manifest.csv        one row per raw file: group, firmware, times, km, laps, how it ended, heap
  events.csv          every '# m=' event line of every file, with local time where it can be derived
  race_10hz.csv.gz    every 10 Hz row inside the race window, with race time, 12 h block, race lap
  laps.csv            every race lap from S/F crossing to S/F crossing (absolute time, so laps
                      survive unit resets), pit / reset flags, stint number
  crashes.csv         one row per unplanned warm reset
  crashes/            per-crash timeline: rows + events from 60 s before to 30 s after the reset

Usage (from the repo root):
  python -I Sessions/tools/build_session_logs.py <session_dir> --gps-week 2026-11-08 \
      --race-start "2026-11-13 04:30" --race-end "2026-11-14 16:30"

Time: rows carry GPS iTOW (ms of GPS week) but no week number, so --gps-week (the Sunday that
starts the GPS week) is required; files whose iTOW does not fall in order inside that week are
left without absolute time. Events carry only millis since boot; they are placed on the GPS
clock with the offset measured at nearby events that sit between two consecutive 10 Hz rows.
"""
import argparse, bisect, csv, glob, gzip, math, os, re
from datetime import datetime, timedelta

GPS_UTC_LEAP_S = 18
LOCAL_UTC_H = 8                     # AWST, no DST in WA
COLLIE = (-33.4301, 116.2432)       # Collie Motorplex S/F
SITE_RADIUS_KM = 5
WARM_BOOT_MAX_MS = 15000            # boot line before 15 s = software reset (cold boot ~31 s)
COLS = ['iTOW', 'lat_deg', 'lon_deg', 'speed_kph', 'sats', 'pdop', 'fix', 'along_g', 'lat_g',
        'vert_g', 'yaw_dps', 'lap', 'sector', 'delta_ms', 'cumul_delta_ms', 'state', 'car_state',
        'geo_override', 'geo_label']
EV_RE = re.compile(r'# m=(\d+) (\S+) ?(.*)')


def km_between(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


class Log:
    def __init__(self, path):
        self.path, self.name = path, os.path.basename(path)
        self.fw, self.boot_m = '', None
        self.rows = []        # list of (itow, fields list)
        self.events = []      # list of dict(m, tag, text, prev, next) prev/next = row indexes
        self.parse()

    def parse(self):
        for line in open(self.path, encoding='utf-8', errors='replace'):
            line = line.rstrip('\r\n')
            if line.startswith('# m='):
                mm = EV_RE.match(line)
                if not mm:
                    continue
                m, tag, text = int(mm.group(1)), mm.group(2), mm.group(3).strip()
                if text.startswith('boot ') and self.boot_m is None:
                    self.boot_m, self.fw = m, text.split()[1]
                self.events.append(dict(m=m, tag=tag, text=text, prev=len(self.rows) - 1))
                continue
            if not line or not line[0].isdigit():
                continue
            p = line.split(',')
            if len(p) != len(COLS):
                continue          # truncated last row before a reset
            try:
                itow, fix = int(p[0]), int(p[6])
                float(p[1]); float(p[3])
            except ValueError:
                continue
            if fix < 3:
                continue
            self.rows.append((itow, p))
        for e in self.events:
            e['next'] = e['prev'] + 1 if e['prev'] + 1 < len(self.rows) else None
        # m -> iTOW offset from events bracketed by two consecutive 10 Hz rows
        self.anchor_m, self.anchor_off = [], []
        for e in self.events:
            if e['prev'] >= 0 and e['next'] is not None:
                a, b = self.rows[e['prev']][0], self.rows[e['next']][0]
                if 0 < b - a <= 200:
                    self.anchor_m.append(e['m'])
                    self.anchor_off.append(a + 50 - e['m'])

    def itow_of_m(self, m):
        if not self.anchor_m:
            return None
        i = bisect.bisect_left(self.anchor_m, m)
        cands = [j for j in (i - 1, i) if 0 <= j < len(self.anchor_m)]
        j = min(cands, key=lambda k: abs(self.anchor_m[k] - m))
        return m + self.anchor_off[j]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('session')
    ap.add_argument('--gps-week', required=True, help='Sunday starting the GPS week, YYYY-MM-DD')
    ap.add_argument('--race-start', required=True, help='local time, "YYYY-MM-DD HH:MM"')
    ap.add_argument('--race-end', required=True)
    ap.add_argument('--block-h', type=float, default=12)
    a = ap.parse_args()

    week0_local = datetime.strptime(a.gps_week, '%Y-%m-%d') - timedelta(seconds=GPS_UTC_LEAP_S) \
        + timedelta(hours=LOCAL_UTC_H)
    race0 = datetime.strptime(a.race_start, '%Y-%m-%d %H:%M')
    race1 = datetime.strptime(a.race_end, '%Y-%m-%d %H:%M')
    race0_ms = (race0 - week0_local).total_seconds() * 1000
    race1_ms = (race1 - week0_local).total_seconds() * 1000

    def local(itow):
        return '' if itow is None else (week0_local + timedelta(milliseconds=itow)).strftime('%Y-%m-%d %H:%M:%S.%f')[:-5]

    def block(itow):
        if itow is None or not race0_ms <= itow <= race1_ms:
            return ''
        h = (itow - race0_ms) / 3.6e6
        k = int(h // a.block_h)
        return f'{int(k * a.block_h)}-{int((k + 1) * a.block_h)}h'

    def race_s(itow):
        return '' if itow is None or not race0_ms <= itow <= race1_ms else f'{(itow - race0_ms) / 1000:.1f}'

    raw = os.path.join(a.session, 'unit_logs')
    out = os.path.join(a.session, 'derived')
    os.makedirs(os.path.join(out, 'crashes'), exist_ok=True)
    logs = [Log(p) for p in sorted(glob.glob(os.path.join(raw, 'LOG_*.CSV')))]

    # GPS-week validity: walk back from the newest file; iTOW must keep decreasing. The first
    # file that breaks the order belongs to an earlier week, and so does everything before it.
    timed, last, broken = {lg.name: False for lg in logs}, float('inf'), False
    for lg in reversed(logs):
        if not lg.rows:
            timed[lg.name] = not broken
            continue
        if broken or lg.rows[-1][0] > last or lg.rows[0][0] > lg.rows[-1][0]:
            broken = True
            continue
        timed[lg.name], last = True, lg.rows[0][0]

    # ---------- per-file summary ----------
    summ = []
    for i, lg in enumerate(logs):
        r = lg.rows
        t = timed[lg.name]
        pos = (float(r[0][1][1]), float(r[0][1][2])) if r else None
        km_site = km_between(pos, COLLIE) if pos else None
        dist = sum(float(p[3]) for _, p in r) / 3.6 * 0.1 / 1000
        moving = sum(1 for _, p in r if float(p[3]) > 20) / 600
        vmax = max((float(p[3]) for _, p in r), default=0)
        boot_laps = max((int(p[11]) for _, p in r), default=0)
        heaps = [int(x) for e in lg.events for x in re.findall(r'minheap=(\d+)', e['text'])]
        last_sys = next((e for e in reversed(lg.events) if e['tag'] == 'SYS/INFO' and 'heap=' in e['text']), None)
        nxt = logs[i + 1] if i + 1 < len(logs) else None
        texts = ' | '.join(e['text'] for e in lg.events)
        if 'reboot requested via web' in texts:
            end = 'web reboot'
        elif 'web update start' in texts and nxt and nxt.fw != lg.fw:
            end = 'OTA update'
        elif nxt and nxt.boot_m is not None and nxt.boot_m < WARM_BOOT_MAX_MS:
            end = 'WARM RESET (crash)'
        elif nxt:
            end = 'power off'
        else:
            end = 'last file'
        gap_s = ''
        if end == 'WARM RESET (crash)' and r and nxt and nxt.rows and t and timed.get(nxt.name):
            gap_s = f'{(nxt.rows[0][0] - r[-1][0]) / 1000:.1f}'
        summ.append(dict(
            file=lg.name, size_mb=f'{os.path.getsize(lg.path) / 1e6:.2f}', fw=lg.fw,
            boot_m_s=f'{lg.boot_m / 1000:.1f}' if lg.boot_m is not None else '',
            boot_kind=('' if lg.boot_m is None else 'warm' if lg.boot_m < WARM_BOOT_MAX_MS else 'cold'),
            rows=len(r), start_local=local(r[0][0]) if r and t else '', end_local=local(r[-1][0]) if r and t else '',
            uptime_end_s=f'{lg.events[-1]["m"] / 1000:.0f}' if lg.events else '',
            km_from_collie=f'{km_site:.1f}' if km_site is not None else '',
            dist_km=f'{dist:.1f}', moving_min=f'{moving:.1f}', vmax_kph=f'{vmax:.1f}', boot_laps=boot_laps,
            minheap_min=min(heaps) if heaps else '',
            last_heap=re.search(r' heap=(\d+)', last_sys['text']).group(1) if last_sys else '',
            end=end, lost_s_to_next_row=gap_s, _t=t, _pos=km_site))

    # groups (needs neighbours for files without a fix)
    for i, s in enumerate(summ):
        lg = logs[i]
        if s['_pos'] is not None and s['_pos'] > SITE_RADIUS_KM:
            s['group'] = 'off-site'
            continue
        if s['_t'] and lg.rows:
            t0, t1 = lg.rows[0][0], lg.rows[-1][0]
            if t1 < race0_ms:
                s['group'] = 'Collie practice' if float(s['moving_min']) > 5 else 'Collie pre-race'
            elif t0 > race1_ms:
                s['group'] = 'Collie post-race'
            else:
                s['group'] = 'race' if float(s['dist_km']) > 1 else 'race, parked'
            continue
        # no timed rows: inherit from timed neighbours
        prev = next((summ[j] for j in range(i - 1, -1, -1) if summ[j]['_t'] and logs[j].rows), None)
        nxt = next((summ[j] for j in range(i + 1, len(summ)) if summ[j]['_t'] and logs[j].rows), None)
        if prev and nxt and prev.get('group', '').startswith('race') and logs[summ.index(nxt)].rows[0][0] <= race1_ms:
            s['group'] = 'race, parked (no fix logged)'
        elif nxt and logs[summ.index(nxt)].rows[0][0] < race0_ms and prev and prev['group'].startswith('Collie'):
            s['group'] = 'pre-race (no fix logged)'
        else:
            s['group'] = 'bench / boot only (no fix)'
    mf = ['file', 'group', 'fw', 'boot_kind', 'boot_m_s', 'start_local', 'end_local', 'uptime_end_s', 'rows',
          'dist_km', 'moving_min', 'vmax_kph', 'boot_laps', 'km_from_collie', 'minheap_min', 'last_heap',
          'end', 'lost_s_to_next_row', 'size_mb']
    with open(os.path.join(out, 'manifest.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, mf, extrasaction='ignore'); w.writeheader(); w.writerows(summ)

    # ---------- events.csv ----------
    with open(os.path.join(out, 'events.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['file', 'fw', 'uptime_s', 'local_time', 'race_s', 'block', 'tag', 'text'])
        for lg in logs:
            for e in lg.events:
                it = lg.itow_of_m(e['m']) if timed[lg.name] else None
                w.writerow([lg.name, lg.fw, f'{e["m"] / 1000:.3f}', local(it), race_s(it), block(it), e['tag'], e['text']])

    # ---------- race_10hz.csv.gz + laps ----------
    race_logs = [lg for lg, s in zip(logs, summ) if s['group'].startswith('race') and lg.rows]
    race_lap, crossings = 0, []   # crossings: (itow, file)
    lap_rows = {}                 # race_lap -> stats
    with gzip.open(os.path.join(out, 'race_10hz.csv.gz'), 'wt', newline='', compresslevel=6) as f:
        w = csv.writer(f)
        w.writerow(['local_time', 'race_s', 'block', 'race_lap', 'file', 'fw', 'boot_lap'] + COLS[1:] + ['iTOW'])
        for lg in race_logs:
            prev_lap = None
            for itow, p in lg.rows:
                if not race0_ms <= itow <= race1_ms:
                    continue
                lap = int(p[11])
                if prev_lap is not None and lap > prev_lap:
                    race_lap += 1
                    crossings.append((itow, lg.name))
                prev_lap = lap
                st = lap_rows.setdefault(race_lap, dict(files=set(), fw=set(), vmax=0, pit_rows=0, boot_laps=set()))
                st['files'].add(lg.name); st['fw'].add(lg.fw); st['boot_laps'].add(lap)
                st['vmax'] = max(st['vmax'], float(p[3]))
                if p[16] in ('2', '4'):
                    st['pit_rows'] += 1
                w.writerow([local(itow), race_s(itow), block(itow), race_lap, lg.name, lg.fw, lap] + p[1:] + [p[0]])

    with open(os.path.join(out, 'laps.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['race_lap', 'start_local', 'end_local', 'block', 'lap_s', 'stint', 'pit_lap',
                    'spans_reset', 'files', 'fw', 'boot_laps', 'vmax_kph'])
        stint = 1
        for k in range(1, len(crossings)):
            t0, f0 = crossings[k - 1]; t1, f1 = crossings[k]
            st = lap_rows.get(k, dict(files=set(), fw=set(), vmax=0, pit_rows=0, boot_laps=set()))
            pit = st['pit_rows'] >= 100        # ≥10 s in PITS / FUELLING
            w.writerow([k, local(t0), local(t1), block(t0), f'{(t1 - t0) / 1000:.1f}', stint, int(pit),
                        int(f0 != f1), ' '.join(sorted(st['files'])), ' '.join(sorted(st['fw'])),
                        ' '.join(map(str, sorted(st['boot_laps']))), f'{st["vmax"]:.1f}'])
            if pit:
                stint += 1

    # ---------- crashes ----------
    with open(os.path.join(out, 'crashes.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['n', 'file', 'fw', 'crash_local', 'race_s', 'uptime_s', 'last_heap', 'minheap_in_file',
                    'speed_kph', 'car_state', 'boot_lap', 'sector', 'lat', 'lon', 'lost_s', 'next_file',
                    'last_events'])
        n = 0
        for i, (lg, s) in enumerate(zip(logs, summ)):
            if s['end'] != 'WARM RESET (crash)':
                continue
            n += 1
            nxt = logs[i + 1]
            last_row = lg.rows[-1] if lg.rows else None
            it = last_row[0] if last_row and timed[lg.name] else None
            p = last_row[1] if last_row else [''] * len(COLS)
            # a crash after a long stationary period: the events go on after the last row
            last_ev_it = lg.itow_of_m(lg.events[-1]['m']) if timed[lg.name] and lg.events else None
            crash_it = max(x for x in (it, last_ev_it) if x is not None) if (it or last_ev_it) else None
            lastev = ' || '.join(f'{e["tag"]} {e["text"]}' for e in lg.events[-3:])
            w.writerow([n, lg.name, lg.fw, local(crash_it), race_s(crash_it), s['uptime_end_s'], s['last_heap'],
                        s['minheap_min'], p[3], p[16], p[11], p[12], p[1], p[2], s['lost_s_to_next_row'],
                        nxt.name, lastev])
            if crash_it is None:
                continue
            lo, hi = crash_it - 60000, crash_it + 30000
            tl = []
            for src in (lg, nxt):
                if not timed[src.name]:
                    continue
                for itow, q in src.rows:
                    if lo <= itow <= hi:
                        tl.append((itow, 0, src.name, src.fw, 'row', ','.join(q)))
                for e in src.events:
                    et = src.itow_of_m(e['m'])
                    if src is nxt and e['m'] < 20000:
                        et = None        # pre-fix boot events: place them right after the crash
                        tl.append((crash_it + 1, 1, src.name, src.fw, 'event', f'm={e["m"]} {e["tag"]} {e["text"]}'))
                        continue
                    if et is not None and lo <= et <= hi:
                        tl.append((et, 1, src.name, src.fw, 'event', f'm={e["m"]} {e["tag"]} {e["text"]}'))
            tl.sort(key=lambda x: (x[0], x[1]))
            with open(os.path.join(out, 'crashes', f'crash_{n:02d}_{lg.name[:-4]}.csv'), 'w', newline='',
                      encoding='utf-8') as cf:
                cw = csv.writer(cf)
                cw.writerow(['local_time', 'file', 'fw', 'kind', 'content (row: ' + ','.join(COLS) + ')'])
                for et, _, fn, fw, kind, c in tl:
                    cw.writerow([local(et), fn, fw, kind, c])

    print(f'{len(logs)} files, {len(race_logs)} race files with rows, {race_lap} S/F crossings, '
          f'{sum(1 for s in summ if s["end"] == "WARM RESET (crash)")} warm resets -> {out}')


if __name__ == '__main__':
    main()

# 36 Hours of Collie, 13–14 Nov 2026, firmware v0.22.0 → v0.23.0

The race ran from Fri 13 Nov 04:30 to Sat 14 Nov 16:30 AWST. The car retired with a clutch failure about 57 minutes before the end.
Thursday practice (LOG_0013) has its own write-up in `../2026-11-12_Collie/README.md`.

## Folders

| Path | What |
|---|---|
| `unit_logs/` | The raw logs, LOG_0001 to LOG_0050, exactly as they came off the unit. They are read-only. Never edit them. |
| `derived/` | Analysis-ready files built from `unit_logs/`. They can be rebuilt at any time (see below). |

Rebuild from the repo root (about 5 s):

```
python -I Sessions/tools/build_session_logs.py Sessions/2026-11-12_36H_of_Collie --gps-week 2026-11-08 --race-start "2026-11-13 04:30" --race-end "2026-11-14 16:30"
```

## derived/

| File | What | Use it for |
|---|---|---|
| `manifest.csv` | One row per raw file: group, firmware, cold or warm boot, local start and end, km, laps, lowest free memory, how the file ended, and seconds of data lost before the next file. | Finding the right file. |
| `events.csv` | Every `# m=` event line from all 50 files (about 19,000 lines), with local time, race time and 12 h block added. | **Start every investigation here.** Grep it by tag or text. |
| `race_10hz.csv.gz` | Every 10 Hz row inside the race window (957,436 rows, 33 MB). Adds `local_time`, `race_s`, `block`, `race_lap`, `file`, `fw` and `boot_lap`. | Pace, positions, G, sector deltas. Load with `pandas.read_csv(...)`. |
| `laps.csv` | All 914 race laps, timed from S/F crossing to S/F crossing on the GPS clock, so laps that span a reset are still timed. Adds a stint number, `pit_lap`, `spans_reset` and the source files. | Lap and stint analysis, comparing the 12 h blocks. |
| `crashes.csv` | One row per unplanned warm reset: time, uptime, free memory, speed, position, sector, last 3 events, and seconds lost. | The crash investigation. |
| `crashes/crash_NN_LOG_xxxx.csv` | Rows and events from 60 s before to 30 s after each reset, across both files, on one timeline. | Looking closely at one crash. |

The 0–12h / 12–24h / 24–36h blocks are a column (`block`), not separate files, so you can filter on them without cutting through a stint.

## How the time is worked out

- **Rows:** each row's GPS iTOW is placed in the GPS week starting Sun 8 Nov 2026. The unit has no clock and stores no week number, so files from earlier weeks (LOG_0002, LOG_0003) get no absolute time.
- **Events:** each event has only its millis since boot. It is placed on the GPS clock using the offset measured at nearby events that sit between two consecutive 10 Hz rows. Events in files with no fix (LOG_0030, LOG_0033, LOG_0041) get no time.
- **Laps:** `race_lap` counts S/F crossings from the start of the race. `boot_lap` is the unit's own counter, which goes back to 0 at every boot.

## What the logs show

### Coverage

- **Laps:** 914 laps, about 2,340 km. The median lap was 96.2 s. The best was 90.3 s, on lap 840 (Sat 12:05, v0.23.0, LOG_0042).
- **Laps by block:** 384 in 0–12h, 339 in 12–24h and 191 in 24–36h.
- **Long stops:**
  - Sat 00:23–00:50: LOG_0030, parked.
  - Sat 04:45–08:38: LOG_0033 to LOG_0037, parked with three short runs.
- **The data ends at Sat 14:32:** the last file (LOG_0050) ends parked in the pits at 14:34. That is about 2 h before the finish, not 57 minutes. Check which one is right.

### Unit resets: 21 unplanned warm resets

A cold boot logs its `boot` line at about 31 s, and a software reset logs it at about 8 s.

| Firmware | Resets | Uptime before the reset | Lowest free memory in the file |
|---|---|---|---|
| v0.22.0 | 14 | 2 min to 4 h 10 min | mostly 120–760 B |
| v0.23.0, OTA at about Sat 11:50 (LOG_0041) | 7 | 6–18 min (one 80 min) | 156–8,436 B |

- **Memory exhaustion is the prime suspect.** It continues the 4.5 KB low point seen at practice. But some resets came with 5–8 KB free at the last 60 s sample, and LOG_0036 crashed at 120 s uptime with 48 KB free. So not every reset can be put down to memory yet.
- **Each reset loses about 2.5–10.7 s of rows,** and the last row before it is half-written.
- **Each reset also costs a recon lap:** the sectors are rebuilt and the lap counter goes back to 0.
- **Planned restarts are not counted as crashes:** LOG_0040 ended with a web reboot and LOG_0041 with the OTA update.

## Group of each raw file

| Group | Files |
|---|---|
| Bench / boot only, no fix | 0001, 0004–0012 |
| Craigie (also copied to `../2026-11-06_Craigie/`) | 0002 |
| Off-site, 172 km from Collie, stationary | 0003 |
| Collie practice, Thu 12 Nov | 0013 |
| Pre-race (0017 = OTA to v0.22.0, 0019 = parked at Collie Fri 03:31) | 0014–0019 |
| Race | 0020–0029, 0031, 0032, 0035, 0037–0040, 0042–0050 |
| Race, parked (no driving) | 0030, 0033, 0034, 0036, 0041 |

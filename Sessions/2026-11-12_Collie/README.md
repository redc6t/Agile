# Collie practice, 12 Nov 2026, firmware v0.21.1

Two runs in one unit log (`unit_logs/LOG_0013.CSV`, one boot, 69 min, 12,713 rows at 10 Hz, 0 log drops).
`pitwall_recording_20261112_1719.jsonl` is the pit-wall recording of run 1: `/data` every 2 s plus every `/events` row.
`unit_logs/` holds every log on the unit when it was pulled, LOG_0001 to LOG_0015. LOG_0002 is the earlier Craigie session (v0.20.1).

## Laps

Times marked * come from the unit's NEW BEST / lap-close events. The rest are from the log rows (±0.1 s).

| Run | Lap | Time | Vmax km/h | Peak lat G | Peak brake G | Notes |
|---|---|---|---|---|---|---|
| 1 | 1 | 1:42.200* | 128.7 | 1.33 | 0.75 | recon lap in traffic: 71 candidates, 15 sectors, 90% |
| 1 | 2 | 1:36.698* | 136.2 | 1.19 | 0.79 | reference |
| 1 | 3 | 1:35.453* | 136.2 | 1.20 | 0.94 | reference |
| 1 | 4 | 1:35.561* | 136.2 | 1.24 | 0.92 | +0.108 s; sector deltas add up to the lap delta exactly |
| 1→2 | 5 | (pitted, 17:41) | 134.9 | 1.22 | 0.77 | in-lap, pit stop and out-lap all in one lap: the pit lane does not cross the S/F line |
| 2 | 6 | ~1:37.2 | 136.7 | 1.23 | 0.99 | |
| 2 | 7 | ~1:35.7 | 134.8 | 1.30 | 0.75 | |
| 2 | 8 | 1:34.055* | 136.8 | 1.33 | 1.03 | **best lap, final reference** |
| 2 | 9 | ~1:34.8 | 136.3 | 1.35 | 0.91 | |
| 2 | 10 | (in-lap, not closed) | 118.6 | 1.08 | 0.64 | ended in the pits zone |

## Recon and style

- **Style:** TRACK, with p95 lateral 0.830 G and p95 longitudinal 0.470 G over 10,220 samples. TRACK needs p95 lateral of at least 0.60 G, so the margin was 0.23 G. Craigie (LOG_0002) measured 0.410 G and came out BRISK.
- **Style is a label only:** it shows on the display and in the logs. The synthesis gate comes from the candidate peak order statistic (0.174 G here), not from the style.
- **Synthesis:** 2,590 m lap, target 17 sectors, 71 candidates. None were dropped by the gate, 2 were dropped near S/F, they formed 14 clusters, and the result was 15 sectors at 90%.
- **Stored map not offered:** the stored map was Craigie's (12 sectors, 95%). The map prompt only appears within `MAP_REUSE_RADIUS_M` (500 m) of the map's S/F line, and Craigie is about 190 km away. So the unit correctly ran a fresh recon lap. Promoting lap 2 then saved the Collie map over the Craigie one.

## Unit health

- **GNSS:** steady at 10 Hz (9.97–10.03 measured), worst gap between fixes 151 ms, 19–21 satellites on track, PDOP 1.0–1.2. It reacquired from 3 satellites after the power cycle.
- **Wi-Fi:** −27 to −36 dBm over the whole session.
- **Free memory now:** about 35 KB.
- **Lowest free memory was 4,476 B,** recorded between 2,100 and 2,160 s uptime (lap 4). The backlight was changed from the web UI at 2,143 s, so the Config tab was probably open then. Before that, the lowest was 8,596 B, between 1,860 and 1,920 s, right after the recon lap closed.
- **Worst loop time was 82 ms,** in the same 1,860–1,920 s window as the recon close. No fixes or log rows were lost.

## To look at after the event (no changes before it)

1. **Lowest free memory of 4.5 KB:** find out what allocates during racing. Suspects are the Config tab's 5 s `/recon?b=1` refresh, several web clients at once, and the reference promotion. Until then, keep one browser on the unit and avoid leaving the Config tab open while the car is out.
2. **Best lap shared across circuits:** the best lap is one global value. The boot value of 1:53.650 came from a previous circuit, and the Collie recon lap only replaced it because it was faster.
3. **Pit lane misses the S/F line:** lap 5 lasted 17 min. Pitted laps are excluded correctly, but a pit-lane S/F line or a lap close at pit exit would keep lap numbers in step.
4. **Sector 14 matched 23.5 m off the line** on the in-lap, through the pit-entry side.
5. **S/F zone has 4 points:** it still warns at every boot. Redraw it as a 2-point line.
6. **Pits zone edge:** before the GNSS settled, the car flickered between PITS and RUNNING at the zone edge. From 17:10 the car showed RUNNING while it was still in the pit area.

# Agile Firmware Changelog

Format: `vMAJOR.MINOR.PATCH - YYYY-MM-DD`. Tag each release in git as `fw-vX.Y.Z`.

## v1.0.0 - unreleased (NOT compiled, NOT run on hardware)

First release, built on v0.23.1 (reset diagnostics) after the 36 Hours of Collie (13–14 Nov 2026: 914 laps, 21 unplanned warm resets, see `Sessions/2026-11-12_36H_of_Collie/`). Firmware 1.0.0 for hardware v1.0. The lap trigger, recon detection, sector synthesis, sector pass, live and cumulative delta, reference promotion and the prediction maths are unchanged, except where D5, D8 and D9 below say otherwise. Nothing here has been compiled; the page JavaScript was syntax-checked and loaded against the mock server.

### Boot
- **One linear boot:** TFT → IMU → PSRAM buffers → GNSS → NVS / zones / map → log → tasks. The TFT `delay(120)` is the only fixed wait left. Estimated warm boot about 2 s (was 8.1 s) and cold boot about 3–4 s (was 31.7 s), not counting sky acquisition. New `SYS/INFO bootms` row with the time of each stage.
- **GNSS probe order follows the reset reason.** After a power-on it tries 9600 first, after a warm reset 460800, with 115200 and 38400 as the last resort; one short attempt each. Evidence: every power-on log found the receiver at 9600 after about 25 s of 460800 and 115200 attempts; every warm boot found it at 460800 in about 1.5 s.
- **`nacks=2` on every boot fixed.** `CFG-RATE-NAV` is a U2 key (`u-blox_config_keys.h:1146`) and was written with `setVal8`. The receiver NAKed it, and the retry made it 2. It is now written as U2. The value is the receiver default, so the rate was never affected. The `GNSS` row adds `nack=<key names>` and `probe=<ms>`.
- **Boot fault hold:** 6 s → 1.5 s, and only for a real fault: no GNSS, GNSS below 10 Hz, no IMU, no log, no zones armed, or a PSRAM failure. All 25 race boots held 6 s for the benign NACK. The fault text goes to the boot line, to `/data boot_fault` and to the boot row (`fault=`).
- **Boot splash:** the Mullaloo Motorsport Engineering logo, the red / orange / off-white stripes (shortening from top to bottom) and the three words, in the sticker colours. It replaces the old title page with its per-stage line and stays up for 3 s while the boot runs behind it. On a real fault, a plain fault screen follows it for 1.5 s. The `bootms` row gains `ready=` (boot work done) and `splash=` (the wait to complete the 3 s), so a warm boot now shows the splash for 3 s while `ready=` measures the boot itself. Preview: `Documentation/Display/screens/boot_splash.png`.
- **Rate readback polled** for up to 400 ms instead of a fixed 250 ms wait. The 5 Hz fallback is kept.
- **No `delay(300)` after `Serial.begin`;** no serial waits anywhere.

### RAM (internal)
| Item | Before | After |
|---|---|---|
| `refFallback[4500]` (fallback trace for a PSRAM failure that never happens) | 54,000 B .bss | deleted |
| `candidates[256]` | 7,168 B .bss | PSRAM |
| `geoZones[10]` | 5,680 B .bss | PSRAM |
| `g_jsonBuf` | 4,096 B .bss | PSRAM, 6,144 B |
| `/recon` String | 4,096–7,168 B heap per request | ≈ 0.8–2.5 KB (no candidate feed) |
| Response bodies of `/data`, `/recon`, `/events`, `/refpath`, `/geozones` | internal String copy held until sent | per-response PSRAM block, freed when the response ends |

**About 71 KB of static internal RAM is freed.** Expected steady free heap is about 90–110 KB, against 21–44 KB in the race. This is an estimate; the first boot's `mem` row will show the real figure. If a PSRAM allocation fails, the boot shows `PSRAM FAIL` and laps are still timed at the line, without a trace or delta.

**Not moved (v1.1):** `g_physBlock` (8 KB), `g_sessions` (≈5 KB), `g_preLog` (2.6 KB), the 7 KB log queue.

### Removed
- **`gnssDiagnose()` and `GNSS_DIAG_*`:** the bring-up baud and loopback scan, serial only, about 10 s when it ran. The wiring is proven: all 50 race logs found the receiver.
- **`RECON_DIAG`, `IMU_TRACE`, `OTA_VERBOSE`:** serial-only output. `RECON_DIAG` printed one line per candidate from `lapTask`.
- **`TFT_BL_DETECT` / `backlightDetect()`:** the backlight mod is fitted on every unit.
- **DOWN-held boot diagnostic pages** (`runBootDiagScreens`): their content is on `/data` and in the boot rows.
- **Held-DOWN synthesis breakdown** on the approve screen.
- **`EVT/INFO recon cand` rows:** one per candidate, 2,197 in the race. Acceptance is validated; the `SYNTH/INFO` summary per recon stays.
- **Every `Serial.print*`** goes through `DBG_*` macros, compiled out with `DEBUG_SERIAL 0`, so nothing can block on an unread USB-CDC port. The race showed `lapTask` worst loops of 126–141 ms after each recon close, while `RECON_DIAG` was printing.

### Reliability (the race resets: internal heap exhausted under web load over a stalling 4G link)
- **WebSocket client cap:**
  - At most 4 WebSocket clients. A 5th is closed with code 1013, and the page falls back to HTTP polling.
  - Each client gets a `hello` frame on connect.
  - `ws.cleanupClients(4)` runs every second from `loop()`. It was never called before.
- **Live frame sent per client.** It goes through `ws.availableForWrite(id)` / `ws.text(id)`: a client with a full queue skips the frame instead of queueing it.
  - `Sauce/build_opt.h` (`-DWS_MAX_QUEUED_MESSAGES=8`, copy it next to the `.ino`) lowers the library's queue limit from 32 to 8. The core copies `build_opt.h` from the sketch folder (`platform.txt` prebuild hooks 5 and 6).
- **Admission control:**
  - When internal free heap drops below 12 KB or the largest block below 6 KB, `/data`, `/recon`, `/events`, `/refpath`, `/geozones` and `/geo/list` answer `503` with an empty body and `Retry-After: 2`, and the live push pauses.
  - Service resumes above 16 KB / 8 KB.
  - One `WEB/WARN shed start` row and one `WEB/INFO shed end` row per episode.
- **Task watchdog:**
  - Every task kicks a heartbeat. A lap, gnss, imu, logw or disp task silent for 8 s writes `WDT/ERR task <name> stalled`, flushes the log and restarts (unplanned).
  - `loopTask` is under the IDF task watchdog (`enableLoopWDT()`).
- **Web statistics:** `mem` row and breadcrumb gain `ws`, `rpm`, `inflight`, `r503`, `shed`. An unplanned reset also logs a `reset web ...` row with the web load at the last breadcrumb.

### Recovery
- **Unplanned warm reset near the stored map:** the map is accepted automatically, through the same path as the driver's OK, with a `MAP/INFO auto-accepted after reset` row. In the race, the 21 resets each cost a recon lap and the stored map was reused once, by hand (LOG_0020). A planned boot (power-on, OTA, `/reboot`) keeps the prompt.
- **Race lap counter** in RTC no-init RAM (survives panic, watchdog and software resets; cleared at power-on). It goes up at every S/F crossing that starts a lap, so the lap in progress at a reset is counted correctly. It appears in `/data race_lap`, the vitals row (`rl=`), the `time` and boot rows. `POST /session/new` restarts it, stationary only.
- **Unplanned-reset count** per session in `/data rst.unplanned_n`.

### Geofence
- **Exit debounce (D5).** A pits, pit lane or fuel polygon is entered on the first fix inside and left after 20 consecutive fixes outside (2 s). Zone changes wait for 30 valid fixes after boot or a GNSS dropout. The race had 64 car-state flips under 10 s apart; practice flickered PITS/RUNNING before the GNSS settled. **Not replayed:** the race's pit polygons were never logged.
- **4-point S/F zone (D7)** is converted on load to the line through points 1–2, the line every lap was already timed on. It is logged once as INFO; all 25 race boots had warned.
- **Off-line sector pass (D8).** A pass more than 12 m sideways from the boundary, or made in a pit state, is timed but GRAY and kept out of the cumulative delta. Race `SEC` rows: 12,398 passes, p99.9 7.1 m, then 11 outliers at 18–27 m. Practice: sector 14 matched 23.5 m off the line.
- **No lap start in a pit state (D9):** an S/F crossing in the pit lane no longer starts a recon or a lap (`LAP/INFO S/F crossed in PITS - no lap started`).

### Display
- **No driver prompts.** The approve screen reads `TRACK 15 SEC / MAP KEPT IN 12s`, and the idle notice reads `MAP 15 SEC - PIT WALL`; the web holds the control. The OK holds stay for bench use.
- **No prediction on a pitted lap.** Pitted laps ran up to 427 s; the completed lap is still held 3 s at the line.
- **Name on screen:** `Agile FW v1.0.0` on the boot and idle screens.

### Web
- **Polling that cannot pile up.**
  - Every poller (`/data`, `/recon`, `/events`) is chained: the next request starts only after the last one ends.
  - Each request is aborted after 1.5 s.
  - Errors and 503s back off 1 → 2 → 5 s, with 0–3 s jitter after repeated errors.
  - Polling pauses while the tab is hidden.
  - `/data` drops to every 2 s while WebSocket `live` frames arrive.
  - The WebSocket reconnects with back-off and jitter, and 30 s after a 1013.
- **Status strip, always visible:**
  - Shows link state (live, polling, stale, reconnecting, shedding), firmware, uptime, heap and largest block, GNSS, car state, race lap, WebSocket clients and the boot fault. It greys out when the data is stale.
  - Reset banner, e.g. `Unit restarted 14:06:16 (PANIC), 3rd unplanned reset this session`.
- **`/recon` candidate feed removed.** `ev` is always `[]` and `next = n`; the counts are kept.

### Logging
- **`SYS/INFO time` row** at the first valid GNSS time after boot, then hourly: `utc=`, `week=`, `tow=`, `ls=18`, `fw=`, `ses=`, `rl=`. The race logs carried no date.
- **`SEC` rows are NAND only.** They no longer pass through the 64-row web ring; there were 13,272 in the race.
- **Event text is ASCII only,** sanitised in the formatter, and the format strings are fixed at the source.
- **`logFlushNow()`:** the writer drains and programs the page before a watchdog restart. OTA and planned reboots keep `otaQuiesce()`. Nothing writes NAND from a panic.
- **10 Hz CSV format unchanged,** so `build_session_logs.py` reads v1.0.0 logs as they are.

### API (backward compatible; see `Documentation/Interface.md`)
- **`/data` adds:** `fw`, `up_s`, `utc_s`, `boot_ms`, `boot_fault`, `session_id`, `race_lap`, `boot_lap`, `map_auto`, `rst{reason,code,planned,unplanned_n,prev_up_s}`, `heap_min`, `heap_big`, `psram_free`, `web{ws,rpm,inflight,r503,shed}`, `gnss_nack`.
- **New:** `POST /session/new`, the WebSocket `hello` frame, and 503 shedding.
- **OTA** is allowed in PITS or FUELLING while stationary, as well as with no lap running. The race refused a flash in the pits with `refused: lap in progress`.

### Deferred to v1.1
- **Driver display (C1–C4, C6):** off-screen canvas, sprung delta bar, delta-number deadband, transitions, degraded marker. They are the bulk of the display rework and need the panel to verify.
- **D1:** synthesis off the 10 Hz path. Re-assess first now that the `RECON_DIAG` serial output is gone.
- **D3:** per-circuit persistence of best lap, reference path and prediction history. Until then the delta returns from lap 2 after a reset, and best lap is still global.
- **D6:** close the lap at pit exit, and the pit-stop timer.
- **D10:** the replay harness. A draft is in `Sauce/tools/replay_harness.py`, not run, so D5/D8/D9 are argued from the logs, not replayed.
- **Web app (B2–B12, A5):** the four-tab reorganisation, lap history, gzip page and OTA queue. A draft page is in `Sauce/Agile_v1_0_0_page.html`, not wired in.
- **Logs (E4, E6):** compact `SEC` rows and the log tool update.

## v0.23.0 - unreleased (not run on hardware)
- **Predicted lap time.** The web Live tab's lap cell used to count up from the line, and the TFT's lap time was reference + live delta: every lap opened at the best lap and carried every loss to the flag 1:1. Both now show a prediction:
  - At the line it is the sum of a per-sector base: 0.25 × reference (best) sector + 0.50 × average of recent clean laps + 0.25 × last clean lap. With no clean lap yet it is the reference.
  - During the lap it is elapsed + (rest of the current sector + later sectors) × form. Form is the median of actual/base over the sectors done so far, with incidents (more than 6% off) left out, clamped to ±2% and weighted by √(share of sectors done).
  - A one-off mistake stays on the clock but is not projected onto the rest of the lap. A steady gain or loss scales what is left. At the line the prediction equals the real lap time, which is held 3 s (cyan on the TFT, **Last Lap** on the web).
- A lap is learnt from when it is not pitted, every sector is timed, and it is within 107% of the reference. A sector over 110% of its reference keeps its previous history. History resets when the sector map changes (recon, stored map, reset, S/F set).
- Display only: sector timing, the delta bar, cumulative delta, sector colours, best lap, reference promotion and the CAN status frame (`estimated_lap_ms`) are unchanged.
- Web lap cell: **Predicted Lap**, with `elapsed` and `at line` (the prediction made at the start of the lap) underneath.
- New `/data` fields `predicted_lap_ms`, `pred_line_ms`, `pred_final`, `pred_form`; the `live` WS frame adds `pl`, `pf`. `/data` buffer 3584 → 4096 bytes.
- One `PRED/INFO` event row per lap: lap time, prediction at the line and its error, form, clean or excluded. Use these to tune the weights after the race.
- Checked in a host port of the maths (reference pace, 1.5% slow, a 4 s mistake, 1% fast, pitted lap). Not run on hardware.

## v0.22.0 - unreleased (not run on hardware)
- **PIT LANE zone** (type 7, polygon): the corridor from pit entry to pit exit. For car state it counts as pits. Inside any pits or pit lane polygon from RUNNING or PIT ENTRY is PITS, and PIT EXIT holds until the car is clear of every pits and pit lane polygon. Leaving a fuel zone inside the lane returns to PITS. It's logged as `pit lane entered` when the car is in a lane polygon and no pits polygon. At Collie on 12 Nov the pits polygon didn't cover the whole lane, so the car read RUNNING in the pit area. Like the pits polygon, it must not cover the racing line.
- Config tab: **+ Add Zone** takes a type and an optional name and starts drawing it. Without a name it gets the type name, numbered if already used (`PIT LANE`, `PIT LANE 2`). Every zone has a rename button (✎). Rename, then Save Config and Load to Device. Several zones of one type are allowed, up to 10 per circuit (`MAX_GEOFENCE_ZONES`) and the ~3.9 KB NVS limit. The editor shows the count and refuses an 11th zone or a polygon over 32 points, both of which the device used to drop silently.
- Zone labels are HTML-escaped wherever the page draws them, since they are now free text.
- Circuits saved by older versions load unchanged: zone types 1–6 keep their numbers.

## v0.21.1 - unreleased (run on hardware 12 Nov, Collie)
- Confirmed on track: `pits zone entered (was RUNNING)` logged with no entry line crossed, and a 5-lap and a 4-lap run timed normally (see `Sessions/2026-11-12_Collie`).
- Pits zone triggers from RUNNING as well as PIT ENTRY: inside any pits polygon is PITS, so the pit entry line is optional. It used to fire only from PIT ENTRY, so a circuit without an entry line, or a car that booted in the garage, stayed RUNNING in the pits. Not from PIT EXIT, which still holds until the car is clear of every pits polygon. Entry and exit are logged as `GEO/INFO` rows.
- With two pits polygons, the car leaves PITS only when outside both. The polygon it was not in used to force PIT EXIT.
- A pits polygon must not cover the racing line: with no entry line in front of it, a car on track inside it is PITS and timing is gated.

## v0.21.0 - unreleased (not run on hardware)
Engineer view for running the car from the pits. Web-side visibility only: recon detection, synthesis, sector timing, delta and geofence logic are unchanged.
- Live tab: **Driver Display** mirror (what the TFT shows now, from the display owner stack), **Recon & Sector Map** card (state, live candidate feed with counts and peaks per type, verdict with style, sector count, confidence and synthesis breakdown) and a live **Event Log** of every `sysLogEvent` row.
- Remote OK: **Keep recon map** (approve overlay) and **Use stored map** (idle MAP prompt after a reboot) via `POST /approve`. **Discard & redo recon** uses the existing `/nuke` (S/F kept): the next S/F crossing starts a new recon lap.
- Config tab: read-only **Sector Map**: reference lap, recon candidates coloured by type (faded below the synthesis gate), numbered boundaries, finish sector, optional stored map, and a table of which event each boundary came from.
- New `GET /recon`, `GET /events`, `POST /approve`. `sysLogEvent` rows are also copied to a 64-row PSRAM ring.
- New `EVT/INFO` log row per recon candidate (type, peak, duration, onset time and position), so a missed corner can be explained from the CSV.
- `candidateCount` is incremented after the candidate is filled, so a web read never sees a half-written entry.
- Page size grows from ~69 KB to ~93 KB.

## v0.20.1 - unreleased (compiles, not run on hardware)
- Finish sector: the stretch from the last IMU boundary to S/F is now a timed sector, closed by the S/F crossing, with its own split, colour, delta and `SEC ... at S/F` log row. LOG_0002 showed 1.4–1.9 s per lap that was never compared, so sector times summed about 1.5 s short of the lap. Maps saved by older versions get it appended on load; the sector strip shows one more cell.
- `geo_label` log column is empty outside custom zones (it kept the last custom label for the rest of the session).
- v0.20.0 confirmed on track (LOG_0002, Craigie): fuel zone entered twice from RUNNING, boot rows present, every boundary passed within 0.1–1.9 m.

## v0.20.0 - unreleased (compiles, not run on hardware)
- Fuel zone triggers from any car state: inside the polygon is FUELLING (REFUELING on the TFT), leaving it returns to PITS if still inside the pits polygon, else RUNNING. It used to fire only from PITS, so a parked test never showed it. Entry and exit are logged as `GEO/INFO` rows.
- Sector boundaries complete at the car's closest approach to the boundary point, time-interpolated between fixes, instead of on entering a 30 m circle. LOG_0028 showed sector 1 about 2 s green on every lap and a matching loss on the run to S/F. Stored sector maps stay valid.
- Boot-time GNSS, IMU and GEO log rows are written again (the pre-log flush ran before the log queue existed, since v0.15.0).
- New `SEC/INFO` log row per boundary: measured and reference time, delta, GREEN/RED/TIE/GRAY, skips, lateral distance at the pass.
- Config tab: device settings moved from the narrow left column into a grid of panels below the circuit editor.

## v0.19.0 - unreleased (compiles, not run on hardware)
- Unit orientation NORMAL / INVERTED, saved in NVS `lt_imu` key `orient`. It sets the display rotation (3 / 1) and the IMU signs together: INVERTED negates left, up and yaw rate (enclosure rolled 180° about forward).
- Level Now learns it. If gravity reads below −0.5 g on the vertical axis, the unit is installed the other way up: the trim is computed in the flipped frame, then orientation and trim are saved and the unit reboots. Only with no lap in progress and at 5 km/h or less; otherwise the toast says `ORIENT FLIP / BLOCKED - STOP CAR` and nothing is saved.
- No automatic flip at boot. The boot check shows `IMU FLIPPED? HOLD OK 10s TO RELEARN` instead.
- `GET /imu` adds `orient`, `flip` and `level`. New `POST /imu/orient` sets it by hand (bench fallback). The web IMU card shows and sets the orientation.
- v0.18.0 stays the stable release with the orientation fixed.

## v0.18.0 - unreleased (provisional, not run on hardware)
- TFT backlight brightness 10–100 % from the web Config tab: slider with live preview, Day/Dusk/Night presets, saved to NVS `lt_disp`, applied before the TFT starts. Endpoints `GET /brightness`, `POST /brightness`.
- Needs the v1.1 rework: TFT LED pin cut from GND and switched low-side by an MGSF1N03LT1G, gate on GPIO48 via 100 Ω with 10 kΩ to 3V3. The mod is detected at boot; a stock board reports "not fitted". See `Documentation/TechnicalSpec.md` §7.4.1.

## v0.17.x
- Current series as consumed by PWSM (`lib/adapters/pltd.js`). Import source and history here.

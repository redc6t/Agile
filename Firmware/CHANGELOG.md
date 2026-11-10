# Agile Firmware Changelog

Format: `vMAJOR.MINOR.PATCH - YYYY-MM-DD`. Tag each release in git as `fw-vX.Y.Z`.

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

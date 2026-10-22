# Agile Firmware Changelog

Format: `vMAJOR.MINOR.PATCH - YYYY-MM-DD`. Tag each release in git as `fw-vX.Y.Z`.

## v0.18.0 - unreleased (provisional, not run on hardware)
- TFT backlight brightness 10–100 % from the web Config tab: slider with live preview, Day/Dusk/Night presets, saved to NVS `lt_disp`, applied before the TFT starts. Endpoints `GET /brightness`, `POST /brightness`.
- Needs the v1.1 rework: TFT LED pin cut from GND and switched low-side by an MGSF1N03LT1G, gate on GPIO48 via 100 Ω with 10 kΩ to 3V3. The mod is detected at boot; a stock board reports "not fitted". See `Documentation/TechnicalSpec.md` §7.4.1.

## v0.17.x
- Current series as consumed by PWSM (`lib/adapters/pltd.js`). Import source and history here.

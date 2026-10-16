# PLTD Documentation

| Document | Contents |
|---|---|
| [Architecture.md](Architecture.md) | System overview, tasks, data flow, timing logic, storage, trackside network |
| [Pseudocode.md](Pseudocode.md) | Firmware v0.17.0 as pseudocode, module by module, with state diagrams |
| [Display.md](Display.md) | Every driver-display screen and scenario, rendered from the firmware drawing code |
| [WebUI.md](WebUI.md) | Web app (Live and Config tabs), with screenshots |
| [Interface.md](Interface.md) | WebSocket and HTTP API used by pit wall clients (PWSM) |
| `Display/render_tft.py` | Regenerates `Display/screens/*.svg` |
| `WebUI/mock_server.py` | Serves the real web UI from a firmware source file against mock data |
| `Manuals/` | User / install manuals (driver, pit crew, installation in car) |
| `Flowchart/` | Lap/sector state machine, car state, boot flow diagrams |

# Crash investigation: 21 unplanned resets, 36 Hours of Collie

Data: `derived/crashes.csv`, `derived/crashes/`, `derived/heap_timeline.csv`, `derived/events.csv`.
Source: `Sauce/Agile_v0_22_0.txt` and `Agile_v0_23_0.txt`.

## Summary

**The web/network side is running internal RAM out, not the timing code.**

- **Most likely mechanism:**
  - Every pit-wall browser reaches the unit over the car's 4G link.
  - When that link stalls, the unit keeps unsent `/data` responses, WebSocket frames and TCP buffers in internal heap.
  - The Live tab keeps firing `/data` every 500 ms whether or not the last one came back.
  - Once internal heap is gone, the next allocation fails and the ESP32 resets. The log can't tell which reset reason it was.
- **How sure:** this fits every piece of evidence below, but nothing proves it yet. The logs carry no reset reason, web client count or largest free block. v0.23.1 (in `Sauce/`) adds all three.

## What was found

### 1. A software reset, not a power loss

- **Warm boot:** the boot row comes at about 8 s instead of about 31 s.
- **GNSS stayed powered:** it was still at 460800 baud on the next boot.
- **Mid-write:** the last row before the reset is half-written.
- **Count:** 14 resets on v0.22.0 and 7 on v0.23.0. LOG_0040's web reboot and LOG_0041's OTA are excluded.

### 2. No slow leak: short spikes and sustained lows

- **Free heap in normal running:** it swings between about 21 and 44 KB and keeps coming back to about 41 KB. It doesn't trend down over a 4 h boot.
- **The low-water mark (`minheap`) drops in steps:**
  - LOG_0021 hit 212 B at 85 min, then ran another 2.75 h before resetting.
  - LOG_0022 hit 156 B at 113 min.
  - These are short spikes that nearly exhausted the heap and then recovered.
- **Some files end at a sustained low instead:** the last 60 s sample read 476 B (0049), 548 B (0046), 604 B (0044), 740 B (0027), 1,020 B (0045, then power-cycled) and 2,068 B (0026). Something held the heap down for over a minute before the reset.
- **Other resets came 0–60 s after a normal 21–36 KB sample.** A single failed allocation never shows in `minheap`, so this is consistent with the same cause.

### 3. Web traffic, not lap logic, drives the dips

- **The lows don't line up with logged events.** Of 80 one-minute windows where `minheap` reached a new low under 8 KB, most contain no event other than sector rows.
- **The recon close shows up**, as do the reference promotion and Wi-Fi drops, but they don't explain most dips.
- **Crash 12 is the cleanest case (LOG_0036):**
  - It was a cold boot in the pits, with **73.6 KB free** before Wi-Fi.
  - Wi-Fi came up at 80 s, and by 120 s free heap was **49.8 KB**.
  - It reset within the next 60 s, with no lap logic running (state 0).
- **LOG_0037 shows the same drop:** 19 KB free one minute after its Wi-Fi came up.
- **What it points to:** browsers reconnecting cost tens of KB, and a burst of them is enough on its own to reset the unit.

### 4. The unit's own Wi-Fi link is fine

- **Signal:** RSSI is −30 dBm median everywhere on the lap, with a worst sample of −46. The access point (MME_AP, 192.168.0.x) is the car's RUT956.
- **Where the risk is:** the weak part is the RUT956's 4G link to the pits (Tailscale), which the unit can't see.
- **Crash positions:** 8 of the 18 on-track crashes fall between 50% and 70% of lap time, the far end of the circuit. That's about 2× what a uniform spread would give. It's suggestive but not proof (n=18). It's worth checking the RUT956 mobile-signal history for that sector.

### 5. Web behaviour that makes it worse (v0.21.0 → v0.23.0 page)

| Source | Behaviour | Why it hurts over 4G |
|---|---|---|
| `pollData` | `setInterval(pollData, 500)`, **no busy guard**, no timeout | A 3 s stall leaves up to 6 requests in flight per browser. Each one holds a request object, a ~2.5 KB response String and a TCP send buffer in internal RAM. |
| `wsPushLive` | `ws.textAll()` at 10 Hz from the display task | Each stalled client queues up to `WS_MAX_QUEUED_MESSAGES` = 32 frames (~3 s, roughly 10+ KB) before the library drops it. |
| `ws.cleanupClients()` | **never called** (the library says to call it periodically) | Dead or extra WebSocket clients are not trimmed. |
| `/recon` | 1 s poll, with 50 ms chained polls while candidates catch up. Builds a `String` with `reserve(4096)` (7168 with `b=1`), then the response copies it. | 4 KB sits right at the internal/PSRAM malloc threshold, so it lands in internal RAM, twice. |
| `/events` | 1.5 s poll, with 100 ms chained polls while catching up | Smaller, but it piles on after every reboot. |
| Every open tab | No back-off when hidden or on errors | Phones in pockets keep polling. |

### 6. v0.22.0 vs v0.23.0

- **The difference:** v0.23.0's resets came mostly 6–18 min apart, against minutes to hours on v0.22.0.
- **What changed in the code:** the v0.22 → v0.23 diff only adds static arrays (`g_jsonBuf` 3584 → 4096, `g_predLast` / `g_predAvg`), about 1 KB less heap, and slightly bigger `/data` and WebSocket frames.
- **So the jump probably isn't the prediction code by itself.** v0.23.0 ran from about Sat 11:52, the last 3 hours of the race. More viewers then, or worse 4G (traffic peaks near the finish), would also explain it. The two can't be separated without the v0.23.1 breadcrumb.

### 7. What each reset cost

- **Lost rows:** 2.5–10.7 s each.
- **A recon lap and a reference:** sectors are rebuilt and the boot lap counter goes back to 0.
- **The stored map was not reused:** LOG_0020 is the only file where it was accepted, by the engineer from the web.
- **Total:** 21 resets means about 21 laps with no delta on the driver display.

## Fix plan (for after review; nothing changed yet)

### A. Web page: no firmware timing code touched

1. `pollData`: busy guard plus `AbortController` timeout (about 1.5 s), and chain with `setTimeout` after completion instead of `setInterval`.
2. Back off on errors (1 s → 2 s → 5 s), and stop polling while `document.hidden`.
3. Don't poll `/data` while the WebSocket `live` frame is arriving: the WS already carries the fast fields. Drop `/data` to 2 s then.
4. Add random jitter (0–3 s) to reconnects after a reboot, so the browsers don't all arrive at once.

### B. Firmware: web server admission and limits

5. Call `ws.cleanupClients(4)` every 1 s from `loop()`, and refuse a 5th WebSocket client.
6. `wsPushLive`: send per client only when `client->canSend()`, instead of `textAll`. A stalled client then skips frames instead of queueing 32 of them. Consider `-DWS_MAX_QUEUED_MESSAGES=8`.
7. Load shedding: if internal free heap is under about 12 KB or the largest block is under about 6 KB, answer `/data`, `/recon` and `/events` with `503` and no body.
8. `/recon` and `/geo` buffers: build into PSRAM (`heap_caps_malloc(MALLOC_CAP_SPIRAM)`) or chunked responses, not internal `String`s.

### C. Firmware: surviving a reset without losing the stint

9. On an **unplanned** warm reset, when the car is within `MAP_REUSE_RADIUS_M` of the stored map's S/F, use the stored map without waiting for approval. Also keep the lap counter and best lap in RTC no-init RAM, using the v0.23.1 breadcrumb. One reset then costs seconds, not a recon lap.

### D. Proof first

10. Compile v0.23.1 (reset reason, breadcrumb, mem row with largest block, WS client count and task stacks).
11. **Bench reproduction:**
    - Unit on the bench with GNSS, open 3–4 browsers, and throttle or briefly cut their link (DevTools "Slow 3G" / offline, or pull the RUT956 WAN for 5–10 s) while watching `/data` `heap_free`.
    - **If heap collapses and the unit resets, the mechanism is confirmed.**
    - Then apply A and B and repeat.
12. Pull the RUT956 mobile-signal and event log for 13–14 Nov, and check for drops around the crash times in `crashes.csv`.

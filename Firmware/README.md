# PLTD Firmware

| Path | Contents |
|---|---|
| `PLTD/` | Arduino sketch. The folder name must match `PLTD.ino` (Arduino IDE rule). |
| `lib/` | Project-local or patched libraries not installed through the Library Manager. |
| `tools/` | Host-side helpers: flashing scripts, log parsers, test harnesses. |
| `releases/` | Tagged binaries, one folder per version (`vX.Y.Z/`) with `PLTD.ino.bin`, bootloader and partition table. |
| `CHANGELOG.md` | Firmware version history. |

## Toolchain

- Arduino IDE 2.x, ESP32 Arduino core 3.x
- Board: ESP32-S3 (record exact board, flash size, PSRAM and partition scheme here once fixed)
- Libraries: ArduinoJson, ESPAsyncWebServer / AsyncTCP, u-blox GNSS, LSM6DSV16X (pin versions in `CHANGELOG.md` per release)

## Secrets

Wi-Fi credentials go in `PLTD/secrets.h`, which is git-ignored. Keep a `secrets.example.h` in the sketch folder with placeholder values.

## Rules carried over from BTTM

- GPIO 45 and 46 on ESP32-S3 are input-only. Never assign as outputs.
- Verify strapping pin states before assigning SPI/I2C buses.
- Arduino ctags does not parse C++11 raw string literals: JS in PROGMEM must be indented or use arrow functions.
- FreeRTOS: pin acquisition tasks (GNSS, IMU) and comms tasks (Wi-Fi, WebSocket) to separate cores.

## Flashing a release

```
esptool.py --chip esp32s3 --port COMx write_flash 0x0 PLTD.ino.merged.bin
```

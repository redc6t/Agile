# PLTD Hardware

| Path | Contents |
|---|---|
| `PCB/` | LibrePCB project (schematic + board). Source of truth. |
| `Fabrication/` | Outputs per board revision, `vX.Y/`: Gerbers zip, BOM, CPL, schematic and PCB print PDFs (JLCPCB). |
| `Enclosure/` | Mechanical: Onshape exports (STEP for editing, STL/3MF for printing). |
| `Datasheets/` | Key component datasheets, or `links.md` pointing to vendor URLs. |
| `pcb_changelog.txt` | Board revision history. |

## Naming

`PLTD_vX.Y_BOM.xlsx`, `PLTD_vX.Y_Schematic_Print.pdf`, `PLTD_vX.Y_PCB_Print.pdf`, `PLTD_vX.Y_Gerber.zip`, `PLTD_vX.Y_CPL.csv`.

Tag each released board in git as `hw-vX.Y`.

## Core components

| Function | Part | Interface | Notes |
|---|---|---|---|
| MCU | ESP32-S3 | - | GPIO 45/46 input-only; check strapping pins |
| GNSS | u-blox NEO-M9N | UART | Same module as BTTM |
| IMU | ST LSM6DSV16X | SPI / I2C | FIFO + hardware timestamp |
| Storage | microSD | SPI / SD_MMC | |
| Display | TBD | TBD | |

## License

Hardware design files are licensed CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0/).

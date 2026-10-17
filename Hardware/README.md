# Agile Hardware

| Path | Contents |
|---|---|
| `PCB/` | LibrePCB project (schematic + board). Source of truth. |
| `Fabrication/` | Outputs per board revision, `vX.Y/`: Gerbers zip, BOM, CPL, schematic and PCB print PDFs (JLCPCB). |
| `Enclosure/` | Mechanical: Onshape exports (STEP for editing, STL/3MF for printing). |
| `Datasheets/` | Key component datasheets, or `links.md` pointing to vendor URLs. |
| `pcb_changelog.txt` | Board revision history. |

## Naming

`Agile_vX.Y_BOM.xlsx`, `Agile_vX.Y_Schematic_Print.pdf`, `Agile_vX.Y_PCB_Print.pdf`, `Agile_vX.Y_Gerber.zip`, `Agile_vX.Y_CPL.csv`.

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

Hardware design files are licensed under the CERN Open Hardware Licence v2, Strongly Reciprocal (CERN-OHL-S-2.0, https://ohwr.org/cern_ohl_s_v2.txt).

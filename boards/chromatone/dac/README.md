# chromatone/dac

I2S DAC experiment for the Chromatone Pi: an alternative to the USB audio dongle
decided in the design vault (`~/Source/chromatone/Hardware/Raspberry Pi.md`).
Raspberry Pi Zero 2 W I2S -> TI PCM5102A -> 2.1 Vrms ground-centred line out on a
3.5 mm jack, into the self-powered speaker. Same cable-connected style as
`chromatone/isolator`; the two boards use different Pi pins and can coexist.

## Constituent parts (rev A)

| Ref | Part | Why | LCSC |
| --- | --- | --- | --- |
| U1 | TI PCM5102A, TSSOP-20 | Stereo DAC with built-in PLL (no MCLK from the Pi needed), charge pump for a ground-centred output, so no coupling caps | C107671 |
| U2 | Microne ME6211C33, SOT-23-5 | Low-noise 3.3 V LDO from the Pi's 5 V so the DAC's analog rail is not the Pi's noisy 3.3 V | C82942 (basic) |
| J1 | JST-XH 6-pin | 5V, GND, LRCK, DIN, BCK, XSMT from the Pi header | C144397 |
| J2 | PJ-320D 3.5 mm TRRS jack | Line out; ring 2 and sleeve grounded so a TRS plug works | C431535 |
| C5, C6, C7 | 2.2 uF X5R | Charge pump flying cap, VNEG rail, internal 1.8 V LDO output | pick basic |
| C1..C4, C10..C12 | 10 uF + 100 nF | LDO in/out, AVDD, CPVDD, DVDD decoupling | pick basic |
| R1..R3 | 33 R | Series damping on BCK, LRCK, DIN | pick basic |
| R4, R5 + C8, C9 | 470 R + 2.2 nF C0G | TI's recommended output filter | pick basic |
| R6 | 10k | XSMT pull-up: un-muted by default | pick basic |
| R7, D1 | 1k + green LED | 3.3 V present | pick basic |
| H1..H4 | M2.5 holes | with copper keepouts | |

## Pi wiring and configuration

| J1 pin | Signal | Pi header | GPIO |
| --- | --- | --- | --- |
| 1 | 5V | pin 2 or 4 | |
| 2 | GND | pin 6 | |
| 3 | LRCK | pin 35 | GPIO19 (PCM_FS) |
| 4 | DIN | pin 40 | GPIO21 (PCM_DOUT) |
| 5 | BCK | pin 12 | GPIO18 (PCM_CLK) |
| 6 | XSMT | any GPIO, optional | leave open to stay un-muted |

`/boot/firmware/config.txt`: `dtoverlay=hifiberry-dac` (the PCM5102A overlay, no
MCLK). The device then appears as an ALSA card; no driver install.

## Design notes

- SCK is grounded: the PCM5102A generates its clocks from BCK. FMT low (I2S), DEMP
  low, FLT low (normal latency).
- **XSMT needs clean edges (< 20 ns), so there is deliberately no RC on it.** The
  10k pull-up un-mutes at power-up; drive it from a GPIO for a pop-free mute.
- Output is 2.1 Vrms into >= 1 kOhm. That is line level, louder than a phone; start
  the speaker's volume low.
- Layout: 56 x 36 mm, 2 layers. Pi connector on the right edge, jack on the left
  edge, DAC centred, LDO on top. The two audio lines and XSMT run on the back
  layer; everything else on the front over a solid ground pour. 100 nF caps sit
  within 2 mm of AVDD, CPVDD and DVDD; the flying and VNEG caps are directly
  beside their pins.
- Test points: LRCK and BCK near J1, GND bottom left.
- LED current draw and the DAC itself are well under 100 mA from the Pi's 5 V.

`generate/` holds the scripts that produced the schematic and board, built on
`boardtools.schgen` / `boardtools.pcbgen` (see `generate/README.md`).

## Build

From the repo root:

```sh
make check  BOARD=chromatone/dac
make fab    BOARD=chromatone/dac      # -> boards/chromatone/dac/out/
make jlcpcb BOARD=chromatone/dac      # JLCPCB CPL + BOM -> out/jlcpcb/
```

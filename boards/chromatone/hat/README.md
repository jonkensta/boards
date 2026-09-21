# chromatone/hat

Raspberry Pi HAT that merges `chromatone/isolator` (ISO7720 isolated SPI -> SK9822 strip)
and `chromatone/dac` (PCM5102A I2S line out) onto one 65 x 56.5 mm board that plugs onto
the 40-pin header of a Pi 4B (or any 40-pin Pi; it overhangs a Zero 2 W). Both source
boards stay in the repo as history; this is the board to order.

## Status (2026-09-21)

- Schematic generated, ERC clean (`generate/schematic.py`). Netlist exported.
- **PCB not started**: `hat.kicad_pcb` is still the scaffold. `make check` passes only because
  parity DRC on an empty board reports nothing.
- Decisions taken: full HAT outline (holes 58 x 49 mm, header on the back at HAT-spec
  position: pin 1 at (8.37, 4.77) from the top-left corner, pins along the top edge); ID EEPROM
  footprint present but DNP; camera/display slots omitted (not used on the bike).
- Open question: with a Pi 4B in hand, try its onboard 3.5 mm jack into the speaker first. If
  it is good enough the DAC half (U2, U3, J3, C5..C16, R5..R11, D3, TP7..TP9) can be left
  unpopulated or dropped, and the board shrinks to isolator + header.

## Pi pins used

| Signal | Pi pin | GPIO | Goes to |
| --- | --- | --- | --- |
| 3V3 | 1 (17) | | ISO7720 VCC1, EEPROM pull-ups |
| 5V | 2 (4) | | ME6211 LDO -> +3V3_DAC |
| SCLK | 23 | GPIO11 | ISO7720 INA -> strip CI |
| MOSI | 19 | GPIO10 | ISO7720 INB -> strip DI |
| BCK | 12 | GPIO18 | PCM5102A BCK (33 R) |
| LRCK | 35 | GPIO19 | PCM5102A LRCK (33 R) |
| DIN | 40 | GPIO21 | PCM5102A DIN (33 R) |
| XSMT | 29 | GPIO5 | PCM5102A XSMT (10k pull-up; GPIO5 defaults to pull-up, so un-muted until driven) |
| ID_SD/ID_SC | 27/28 | GPIO0/1 | 24LC32 (DNP) |
| GND | 6, 9, 14, ... | | GND (Pi domain only) |

The LED domain (+5V_LED, GND_LED, J2 to pixel 0) touches nothing on the Pi. Everything in
`chromatone/README.md` about strip wiring, the VDD2 tap at pixel 0, 8 MHz SPI and probing
one domain at a time still applies.

## Layout plan (for the PCB pass)

- Header strip y < 7 mm (socket on the back; nothing else on the back). Route between header
  pads: 0.84 mm gaps take a 0.25 mm trace (0.4 mm just fits at 0.2 mm clearance).
- DAC block translated from `chromatone/dac` (jack on the left edge at x = 9, block at y 12..38);
  the old J1 traces become header escapes (BCK pin 12 at x = 21.07, LRCK pin 35 at 51.55,
  DIN pin 40 at 56.63, 5V pin 2 at 8.37, XSMT pin 29 at 43.93; odd pins y = 4.77, even 2.23).
- Isolator at the bottom right: U1 on a vertical 3 mm barrier at x ~ 46, LED island
  x > 47.5, y > 33 with J2 near (61, 36..44) and hole H4 inside it (keepout, nylon standoff).
  The GND pour is two overlapping rectangles that leave the island and the barrier out.
- EEPROM block top right (x 50..62, y 12..26), beside pins 27/28.
- Pi 4B PoE header sits under x 54..63, y 6..14: no back-side parts there (the socket is the
  only back-side part anyway). No component over the SoC on the back either.
- `pcbgen.Board.footprint(..., side='B')` places the socket the way the KiCad HAT template
  does; `outline_rect(radius=3.0)` draws the HAT corners.

## Files

- `hat.kicad_pro` / `.kicad_sch` / `.kicad_pcb` — KiCad project
- `generate/` — schematic generator (see its README); `pcb.py` to be written
- `sym-lib-table` / `fp-lib-table` — project library tables pointing at the shared `lib/`

## Build

```sh
make check  BOARD=chromatone/hat
make fab    BOARD=chromatone/hat
make jlcpcb BOARD=chromatone/hat
```

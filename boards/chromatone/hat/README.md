# chromatone/hat

Raspberry Pi HAT that merges `chromatone/isolator` (ISO7720 isolated SPI -> SK9822 strip)
and `chromatone/dac` (PCM5102A I2S line out) onto one 65 x 56.5 mm board that plugs onto
the 40-pin header of a Pi 4B (or any 40-pin Pi; it overhangs a Zero 2 W). Both source
boards stay in the repo as history; this is the board to order.

## Status (2026-09-21)

- Schematic and PCB generated (`generate/`), ERC and DRC clean including schematic parity.
  Not yet ordered; the JLCPCB BOM step below still applies.
- Codex review (2026-09-21): no electrical or layout blocker. Ordering notes: D2 (blue LED),
  J1 (2x20 socket) and R1/R2 (47 R) have no LCSC number yet; J1 is the only back-side part and
  is THT, so either choose JLCPCB Standard assembly (both sides) or hand-solder the socket
  (Economic assembly is single-sided). Keep the 8.5 mm body height if substituting.
- Decisions taken: full HAT outline (holes 58 x 49 mm, socket on the back at the HAT-spec
  position: pin 1 at (8.37, 4.77) from the top-left corner, pins along the top edge); ID EEPROM
  footprints present but DNP; camera/display slots omitted (not used on the bike).
- Open question: with a Pi 4B in hand, try its onboard 3.5 mm jack into the speaker first. If
  it is good enough the DAC half (U2, U3, J3, C5..C16, R5..R11, D3, TP7..TP9) can be left
  unpopulated, and a rev B could drop it.

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

## Layout (rev A, 65 x 56.5 mm, 2 layers)

- Header along the top edge, socket on the back (the only back-side part). 5V and BCK leave
  their pads on the back (5V down the west side, BCK east under the socket); everything else
  escapes on the front. Pin 25 (GND) needs a stub and via because the BCK run isolates its
  pour sliver.
- DAC block: the `chromatone/dac` layout rotated 90 deg onto the right half, jack on the bottom
  edge at x = 53 (the right edge is out: the Pi's USB stack rises above the HAT there),
  PCM5102A at (48, 19.5), the 33 R I2S resistors in a row under the header, LDO at (37, 23.5).
- Isolator block: the `chromatone/isolator` layout rotated 180 deg into the bottom left. J2 on
  the left edge, U1 on a vertical 3 mm barrier at x = 23, LED island x < 21.5 / y > 31.5 with
  its own pour; hole H3 sits inside it (copper keepout; use a nylon standoff there).
- SPI feeds (MOSI, SCLK) run down the middle as columns at x = 32 / 34; 3V3 hops under them on
  the back and runs down x = 35.5. ID EEPROM (DNP) in the left-centre with ID_SD/ID_SC on the
  back under the columns.
- Test points: SCLK, MOSI, GND_A (Pi domain), CLK, DATA, GND_B (LED domain), LRCK, BCK, GND
  (DAC). Probe one domain at a time.
- Pi 4B PoE header sits under x 54..63, y 6..14; nothing on the back there.
- `generate/drc.sh` regenerates and prints DRC findings in board-local mm.

## Files

- `hat.kicad_pro` / `.kicad_sch` / `.kicad_pcb` — KiCad project
- `generate/` — schematic and board generators (see its README)
- `sym-lib-table` / `fp-lib-table` — project library tables pointing at the shared `lib/`

## Build

```sh
make check  BOARD=chromatone/hat
make fab    BOARD=chromatone/hat
make jlcpcb BOARD=chromatone/hat
```

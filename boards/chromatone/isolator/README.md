# chromatone/isolator

Isolated SPI daughterboard for the Chromatone bike LED pole
(design vault: `~/Source/chromatone`, see `Hardware/Daughterboard.md`). Other Chromatone
boards would live beside this one under `boards/chromatone/`.

Carries SPI clock + data from a Raspberry Pi Zero 2 W (3.3 V, domain A) to an
SK9822/APA102 strip (5 V, domain B) through a galvanic digital isolator. The two
battery packs and their grounds stay fully separate; the isolator's 5 V-powered
output stage provides the level shift.

## Decisions (2026-09-15)

- **Isolation stays.** The LED side draws amps with switching noise; the Pi and
  audio stay on their own pack and ground. Only CLK and DATA cross the barrier.
- **Two-channel, both-forward digital isolator: TI ISO7720D** (SOIC-8, 100 Mbps,
  2.25–5.5 V each side, 3 kVrms). KiCad stock symbol `Isolator:ISO7720D`,
  footprint `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`, LCSC C486037 (~$0.30). It is
  fail-safe HIGH: with the Pi side unpowered the strip sees CLK/DATA held high,
  which is harmless (no clock edges, so no data is latched).
  Pin-compatible fallback: Chipanalog CA-IS3720HS (LCSC C428882).
  The 4-channel parts in the vault (Si8642, ADuM1401, ISO7341) all have reverse
  channels and are not needed.
- **VDD2 (LED side) is tapped from the strip's 5 V at pixel 0**, not a local
  regulator: the SK9822 datasheet gives no VIH, only an absolute maximum input of
  VDD + 0.3 V, so the isolator's output rail must never sit above the pixel's
  own rail. GND2 gets its own short return to pixel 0's ground, not the 5 A bus.
- **Series 47 Ω on CLK and DATA outputs**, 100 nF + 10 µF bypass on each side.
- **SPI clock: start at 8 MHz.** SK9822 needs > 30 ns clock high and low; at 16 MHz
  that is 31.25 ns nominal and the ISO7720's up to 5.9 ns pulse-width distortion
  plus cable effects eat the margin. Qualify anything faster with a scope at pixel 0.

## Layout (rev A, 46 x 30 mm, 2 layers)

- J1 (Pi) on the left edge, J2 (strip) on the right edge; pin 1 (square pad) is the
  top pin on both. Silk labels next to each pin.
- U1 centred; the 3 mm strip under it has no copper on either layer. Ground pours on
  the back are split there: GND (left) and GND_LED (right). A silk line marks the
  barrier on both sides.
- 100 nF directly beside each U1 supply pin with its ground via at the cap, 10 uF a
  little further out, 47 R in series with CLK and DATA next to U1,
  power LEDs bottom left (green, 3V3) and bottom right (blue, 5V_LED).
- Test points SCLK/MOSI + GND_A (Pi side) and CLK/DATA + GND_B (strip side), 1.5 mm
  pads. Use the ground pad of the same domain for the probe; a scope whose channel
  grounds are common will bridge the isolation if you probe both sides at once.
- Four M2.5 holes, no pads, with a 6.4 mm copper keepout under each so hardware cannot
  reach either pour. Use nylon standoffs anyway; metal ones tie all four corners together.
- Drill/place origin: bottom-left corner.

`generate/` holds the scripts that produced the schematic and board (see its README).

## Ordering

`make jlcpcb BOARD=chromatone/isolator` writes JLCPCB CPL/BOM files. The passives carry no
LCSC numbers yet; pick basic parts in JLCPCB's BOM tool (0603 100 nF, 10 uF/10 V,
47 R, 1 k, green and blue 0603 LEDs). Check LED and connector orientation in the
placement preview before paying.

## Files

- `isolator.kicad_pro` / `.kicad_sch` / `.kicad_pcb` — KiCad project
- `sym-lib-table` / `fp-lib-table` — project library tables pointing at the shared `lib/` in this repo

## Build

From the repo root:

```sh
make check  BOARD=chromatone/isolator   # ERC + DRC
make fab    BOARD=chromatone/isolator   # gerbers, drill, position, BOM, schematic PDF, STEP -> ./out/
make jlcpcb BOARD=chromatone/isolator   # JLCPCB CPL + BOM -> ./out/jlcpcb/
```

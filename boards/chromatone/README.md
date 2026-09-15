# chromatone

Isolated SPI daughterboard for the Chromatone bike LED pole
(design vault: `~/Source/chromatone`, see `Hardware/Daughterboard.md`).

Carries SPI clock + data from a Raspberry Pi Zero 2 W (3.3 V, domain A) to an
SK9822/APA102 strip (5 V, domain B) through a galvanic digital isolator. The two
battery packs and their grounds stay fully separate; the isolator's 5 V-powered
output stage provides the level shift.

## Decisions (2026-09-15)

- **Isolation stays.** The LED side draws amps with switching noise; the Pi and
  audio stay on their own pack and ground. Only CLK and DATA cross the barrier.
- **Two-channel, both-forward digital isolator: TI ISO7720D** (SOIC-8, 100 Mbps,
  2.25–5.5 V each side, 3 kVrms). KiCad stock symbol `Isolator:ISO7720D`,
  footprint `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`, LCSC C486037 (~$0.30).
  Pin-compatible fallback: Chipanalog CA-IS3720HS (LCSC C428882).
  The 4-channel parts in the vault (Si8642, ADuM1401, ISO7341) all have reverse
  channels and are not needed.
- **VDD2 (LED side) is tapped from the strip's 5 V at pixel 0**, not a local
  regulator: the SK9822 datasheet gives no VIH, only an absolute maximum input of
  VDD + 0.3 V, so the isolator's output rail must never sit above the pixel's
  own rail. GND2 gets its own short return to pixel 0's ground, not the 5 A bus.
- **Series 47 Ω on CLK and DATA outputs**, 100 nF + 10 µF bypass on each side.
- SPI clock target 8–16 MHz (SK9822 clock high/low width > 30 ns each).

## Files

- `chromatone.kicad_pro` / `.kicad_sch` / `.kicad_pcb` — KiCad project
- `sym-lib-table` / `fp-lib-table` — project library tables pointing at the shared `lib/` in this repo

## Build

From the repo root:

```sh
make check  BOARD=chromatone   # ERC + DRC
make fab    BOARD=chromatone   # gerbers, drill, position, BOM, schematic PDF, STEP -> out/chromatone/
make jlcpcb BOARD=chromatone   # JLCPCB CPL + BOM -> out/chromatone/jlcpcb/
```

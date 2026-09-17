# chromatone

Boards for the Chromatone bike LED pole. The design vault at `~/Source/chromatone`
(`Chromatone.md`, `Hardware/*.md`, `Open Questions.md`) holds the system design; this
directory holds the KiCad projects and the decisions taken while designing them.
Both boards were generated from `generate/` scripts (see each board's README), reviewed
in adversarial Codex loops, and are ERC/DRC clean with schematic parity.

| Board | What | Size | Order status (2026-09-17) |
| --- | --- | --- | --- |
| [`isolator/`](isolator/README.md) | ISO7720 galvanic isolator + level shifter: Pi SPI (3.3 V) -> SK9822 strip (5 V) | 46 x 30 mm | Rev A layout done. Isolator and connectors numbered; pick basic-part passives in JLCPCB's BOM tool. |
| [`dac/`](dac/README.md) | PCM5102A I2S line-out DAC (experiment, alternative to the USB audio dongle) | 56 x 36 mm | Rev A layout done. Every part has a verified JLCPCB number. |

Build any of them from the repo root: `make check|fab|jlcpcb BOARD=chromatone/<board>`.

## Decisions that supersede the vault

The vault's `Hardware/Daughterboard.md` and `Bill of Materials.md` still name 4-channel
isolators (Si8642, ADuM1401, ISO7341); those have reverse channels and were dropped.

- **Isolation stays.** The LED pack draws amps with switching noise; the Pi, its pack
  and the audio stay on their own ground. Only CLK and DATA cross, A -> B.
- **Two-channel, both-forward isolator: TI ISO7720D** (fail-safe HIGH: with the Pi off the
  strip sees CLK/DATA high, harmless). Chipanalog CA-IS3720HS is pin-compatible. The
  `F` variant defaults low if that is ever preferred.
- **The isolator's 5 V side is tapped at pixel 0**, not from a regulator or the battery.
  The SK9822 datasheet gives no VIH, only an absolute maximum input of VDD + 0.3 V, so the
  output rail must never sit above the pixel's own rail. GND2 gets its own short wire to
  pixel 0's ground.
- **SPI clock: start at 8 MHz.** SK9822 needs > 30 ns clock high/low; 16 MHz leaves about
  1 ns after the isolator's pulse-width distortion. Qualify faster with a scope at pixel 0.
- **Series 47 R on CLK/DATA, 100 nF + 10 uF per side, mounting holes with copper keepouts
  and nylon standoffs, ground test pad per domain.** Probing both domains with a scope whose
  channel grounds are common bridges the isolation.
- **Audio.** The vault decided USB DAC -> powered speaker over wired aux (tight sync, no
  Bluetooth lag). The I2S DAC board is an experiment on the same speaker; it uses GPIO18/19/21,
  so it coexists with the isolator's SPI0 pins. Not yet built or listened to.

## Strip wiring (isolator board)

```
LED pack (+) --10 A fuse--+-- 16 AWG ---------------------------+
LED pack (-) -------------+-- 16 AWG ---------------------------+
                          |                                     |
                    [C 470-1000 uF]                       [C 470-1000 uF]
                          |                                     |
                     pixel 0 pads                          pixel 159 pads
                     5V  CI  DI  GND ==== strip (~1.1 m) ==== 5V GND
                      |   |   |   |
                     J2.1 .2  .3  .4   <- 4-wire pigtail, under 30 cm
                     [ isolator board ]
J1 <- Pi: 1=3V3 (pin 1), 2=SCLK (GPIO11, pin 23), 3=MOSI (GPIO10, pin 19), 4=GND (pin 6)
```

- Power feeds both strip ends over a fused 16-18 AWG pair; that quarters the rail drop
  versus a single feed. Add a midpoint tap only if the far end visibly dims.
- One bulk electrolytic at each feed point, close to the strip pads. No caps mid-strip.
- J2 carries CLK, DATA and a milliamp-level 5 V/GND tap from pixel 0; the strip current
  never goes through the board or its JST-XH contacts.
- If the data run must exceed ~30 cm, twist CLK and DATA each with a GND_LED wire.

## DAC board wiring

J1: 1=5V (pin 2), 2=GND (pin 6), 3=LRCK (GPIO19, pin 35), 4=DIN (GPIO21, pin 40),
5=BCK (GPIO18, pin 12), 6=XSMT (optional GPIO, push-pull; leave open to stay un-muted).
`dtoverlay=hifiberry-dac` in `config.txt`. 2.1 Vrms line out; start the speaker low.
Keep the Pi cable ~20 cm. Mute at least 4 ms before cutting power to avoid a pop.

## Before ordering

1. Isolator: pick 0603 basic parts in JLCPCB's BOM tool (100 nF, 10 uF/10 V, 47 R, 1 k,
   green and blue LEDs); the descriptions are in the exported BOM.
2. Check LED polarity and connector orientation in JLCPCB's placement preview for both boards.
3. Economic assembly, 5 boards: roughly 40-60 USD per board type including parts and shipping.
4. Optional: rotate the JST-XH parts so pin 1 faces the cable exit you want in the enclosure.

## Bench checklist (rev A)

- Isolator: 3V3 and 5V LEDs both on; scope CLK at TP3 against GND_B only; confirm pixel 0
  latches at 8 MHz before raising the clock. Verify color order (BGR) on the real strip.
- DAC: LED on; ALSA card visible; play a tone, check for pops at start/stop; try XSMT from
  a GPIO; measure the 3.3 V rail noise if the audio is not clean.
- Both: the two pack grounds must never touch. Write it on the box.

## Loose ends

- `boardtools.pcbgen` does not yet propagate a schematic DNP flag onto footprints
  (parity DRC only warns); support was being added in a parallel session.
- Vault docs to update once a board is proven: `Daughterboard.md` (part choice, VDDB tap),
  `Power System.md` (bulk caps at feeds only), `Raspberry Pi.md` (I2S option), `Open Questions.md`
  (isolation part decided).

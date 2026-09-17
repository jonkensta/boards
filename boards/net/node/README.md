# net/node

One cell of a sensor "net": a small RP2040 board with an RGB LED, a buzzer, a sensor port and
four neighbour links. A node that detects something lights up and tells its neighbours; they
repeat the excitation one level weaker, so a wave ripples outwards and dies away. Any number
of nodes are tiled and cabled edge to edge (grid, hexagonal patch, irregular drape over a bush).

## Status: parked (2026-09-17)

Rev A schematic is generated, ERC-clean and committed, with the three sensor variants in
place. **No PCB layout, no firmware, nothing ordered.** `node.kicad_pcb` is still the empty
template, so `make check` passes only because DRC parity ignores footprints that were never
placed. Work stopped here deliberately; the open questions and the resume path are at the end.

## Decisions

- **Point-to-point neighbour links, not a bus.** The behaviour is local (each node only needs
  its neighbours), so the cable topology *is* the logic topology: no addressing, no
  termination, no row/column config, any shape. The port a message arrives on gives direction
  for free. A dead node is just a hole the wave flows around.
- **Link = 5 V, DATA, GND on a keyed JST-XH 3-pin**, straight cable, no crossover. DATA is a
  single-wire half-duplex UART: open-drain GPIO, 4k7 pull-up to 3.3 V on every node, 100 R in
  series. Four links on GPIO0..3 so one PIO block can run all four UARTs.
- **5 V rail through the net, ME6211 3.3 V LDO per node.** Proof-of-concept power: a dozen
  nodes on 5 V is fine; bus voltage and bucks come later if the LED gets serious.
- **No USB connector.** J6 is a bare 2x4 pad array (2.54 mm) for a pogo-pin jig carrying SWD,
  USB, RUN, BOOT and power. A virgin RP2040 (blank flash) boots straight into the ROM USB
  bootloader, so the first flash needs only a USB cable on the jig; SWD is there for debugging
  and for re-flashing without pressing anything. Later, firmware can update neighbours over the
  links (a UART bootloader), so the jig is only ever needed once per node.
- **LED: WS2812B-2020** so level maps to colour and brightness with one pin. D1 (1N4148W)
  drops its supply to about 4.3 V so 3.3 V logic meets the 0.7 x VDD input threshold.
- **Sensor port with build variants** (KiCad 10 design variants, all in one schematic):

  | variant   | populated                                    | use                          |
  |-----------|----------------------------------------------|------------------------------|
  | (default) | U3 VL53L0X time-of-flight + C20/C21          | proximity, distance -> level |
  | `vib`     | SW1 SW-18010P spring switch + C22 debounce   | draped over a bush           |
  | `bare`    | header J5 only                               | off-board modules            |

  J5 (5V, 3V3, INT, SDA, SCL, AIN, GND) is always fitted and takes LD2410 mmWave, AM312 PIR,
  any I2C breakout, or an analogue sensor. All options share the same nets (SENS_INT, I2C,
  SENS_AIN), so firmware needs no board knowledge beyond "which variant".
- **Buzzer:** 12 mm passive magnetic buzzer on 5 V, 2N7002 low-side switch, flyback diode.

## Pinouts

Link J1..J4 (N, E, S, W): 1 = +5V, 2 = DATA, 3 = GND.

Sensor header J5: 1 +5V, 2 +3V3, 3 SENS_INT (GPIO6), 4 SDA (GPIO8), 5 SCL (GPIO9),
6 SENS_AIN (GPIO26/ADC0), 7 GND.

Programming pads J6 (2x4, odd pins in one row, even in the other):

| pin | signal  | pin | signal          |
|-----|---------|-----|-----------------|
| 1   | USB_DP  | 2   | SWDIO           |
| 3   | USB_DM  | 4   | SWCLK           |
| 5   | GND     | 6   | RUN             |
| 7   | +5V     | 8   | BOOT (QSPI_SS)  |

USB D+/D- have the 27 R series resistors on the board. Ground BOOT while applying power to
force the USB bootloader on a programmed node.

GPIO: 0..3 links N/E/S/W, 4 LED_DIN, 5 BUZZ, 6 SENS_INT, 7 SENS_XSHUT, 8/9 I2C0, 26 ADC0.
Everything else is unconnected. Crystal 12 MHz on XIN/XOUT, flash W25Q16 on QSPI.

## Programming jig

Eight P75 pogo pins in a 2x4 grid on 2.54 mm pitch (perfboard or a small 3D-printed block),
plus two pins for the M2 holes or a printed frame to locate the board. Wire them to:

- a Raspberry Pi Debug Probe or a Pico running picoprobe (SWDIO, SWCLK, GND; power from +5V),
  flashed with `openocd` or `picotool load`; or
- a cut USB cable (D+, D-, GND, +5V) and a BOOT jumper: the node enumerates as `RPI-RP2`, drag
  the UF2 on.

Nothing is fitted on the board for this: the connector cost per node is zero.

## Variants and exports

`make check|fab|jlcpcb BOARD=net/node` builds the **default** variant (VL53L0X). For the others,
until the jobset grows per-variant outputs (CLAUDE.md ideas list):

```sh
cd boards/net/node
kicad-cli sch export bom --variant vib --exclude-dnp --group-by Value \
  --fields 'Reference,Value,Description,Footprint,MPN,Manufacturer,LCSC,${QUANTITY}' \
  --labels 'Refs,Value,Description,Footprint,MPN,Manufacturer,LCSC,Qty' -o out/node-bom-vib.csv node.kicad_sch
kicad-cli pcb export pos --variant vib --exclude-dnp --format csv --units mm --side both -o out/node-vib-pos.csv node.kicad_pcb
```

`${VARIANT}` in `-o` with several `--variant` flags writes one file per variant.

## Parts and cost

LCSC numbers in the schematic that still need checking on the order page: C2040 (RP2040),
C82317 (W25Q16JVSSIQ), C82942 (ME6211C33M5G-N), C9002 (12 MHz 3225), C8545 (2N7002).
Blank and to be picked in JLCPCB's BOM tool: WS2812B-2020, 1N4148W, VL53L0CXV0DH/1, JST
B3B-XH-A, SW-18010P, buzzer, all 0603 passives.

Rough per-node parts cost at 50 to 100 pieces: about $1.50 for the RP2040, flash, crystal and
LDO; $0.50 for connectors, LED, buzzer driver and passives; the VL53L0X adds about $1.50, the
spring switch a few cents. Add PCB and assembly. The ToF variant is the expensive one; the
bare variant plus a $1 PIR module on J5 is the cheapest way to get a working net.

## Firmware sketch

State = max(own sensor level, max over links of (neighbour level - 1)), decaying over time.
A node sends one byte per change on every link; a level that drops by one per hop guarantees
the wave terminates on any topology, loops included. Add a deliberate per-hop delay (tens of
ms) or the ripple is invisible. Flood with a hop count for global commands (colour, reset), and
put a WiFi gateway (ESP32 on J5, or a future variant) on one node if a host is wanted.

## Open questions (decide before resuming)

- **LED power class.** Rev A uses a WS2812B-2020 (about 60 mA max). A "powerful" LED per node
  changes the power design: a 12 V or 24 V bus with a buck per node, a constant-current driver,
  and connector current ratings. Decide the target net size and worst-case lit count first.
- **Sensor for the first batch.** VL53L0X (default variant) gives distance-scaled excitation but
  is the costliest part on the board; `bare` plus an off-board PIR or LD2410 on J5 is cheaper
  and enough to prove the wave behaviour.
- **Cable.** JST-XH keyed 3-pin is the rev A choice. Pre-made XH cables are cheap but each
  link needs one; check cable cost against node cost before ordering many.
- **LCSC numbers.** Only C2040, C82317, C82942, C9002 and C8545 are filled in and none are
  confirmed on the order page; the rest are blank on purpose.

## Resume path

1. Re-read this file and `generate/README.md`; regenerate the schematic only if the design
   changes (`python3 boards/net/node/generate/schematic.py`, then `make check BOARD=net/node`).
2. PCB layout as `generate/pcb.py`, following `boards/chromatone/isolator/generate/`: about
   40 x 40 mm, one link connector centred on each edge, LED in the middle, J6 pads and the
   sensor on the top side, M2 holes in the corners. Export the netlist first
   (`kicad-cli sch export netlist --format kicadsexpr`).
3. `make jlcpcb BOARD=net/node` for the default variant; the hand-run `--variant` commands
   above for `vib` and `bare`. Order a handful of default + bare boards.
4. Build the pogo jig (Programming jig section), bring up one node over USB, then write the
   link protocol (Firmware sketch) and the UART bootloader so the jig is a one-time touch.
5. Then revisit LED power and bus voltage for a larger net.

`generate/` holds the script that produced the schematic (see its README).

# net/node

One cell of a sensor "net": a small RP2040 board with an RGB LED, a sensor port and four
neighbour links. A node that detects something lights up and tells its neighbours; they
repeat the excitation one level weaker, so a wave ripples outwards and dies away. Any number
of nodes are tiled and cabled edge to edge (grid, hexagonal patch, irregular drape over a bush).

## Status: PCB placement done, routing not started (2026-09-20)

Rev A schematic is generated and ERC-clean (0784855, 587ccf0 added D4). `generate/pcb.py`
places every footprint on a **48 x 48 mm, 4-layer** board (e1650c8); nothing is routed, so
`make check` reports 146 unconnected items. **No firmware, nothing ordered, no jig built.**
A Codex review of the placement (findings summarised under Resume path) is the to-do list
for the next session. This file is meant to be enough to resume cold.

## Concept and first-iteration scope

- The original idea: a cheap board with a bright LED, connected to four others, those to four
  more, forming a net that can be laid over an object, a wall or a bush. Each board has a sensor;
  on detection it lights up and signals its neighbours, who act on it with the signal
  attenuated at each hop.
- The behaviour is a cellular automaton: node state depends only on its own sensor and its
  immediate neighbours. That fact drove every interconnect decision below.
- First iteration is a **proof of concept**: indoor, no outdoor-proofing (no ESD/TVS on the
  links, no sealed connectors, no conformal coat), a **proximity** sensor first, and **per-node
  cost is the priority** because there may be many nodes. The vibration switch for a bush is
  kept as a build variant so the same PCB serves both.

## Decisions

- **Point-to-point neighbour links, not a bus.** The behaviour is local, so the cable topology
  *is* the logic topology: no addressing, no termination, no row/column config, any shape
  (irregular patches, 3- or 6-neighbour nodes, a cut net still works). The port a message
  arrives on gives direction for free (waves, flow away from source). A dead node is a hole the
  wave flows around. Rejected: CAN per row and column (two controllers and transceivers per
  node, termination at every row/column end, forces a rectangular grid, needs position config;
  contention was never the issue, a 20-node row at 500 kbit/s is idle), RS-485 (same problems),
  wireless / ESP-NOW / BLE mesh (removes data wires but not power, and adjacency from RSSI is
  unreliable; only worth it with battery nodes and much smaller LEDs).
- **Link = 5 V, DATA, GND on a keyed JST-XH 3-pin** (J1..J4 = N, E, S, W), straight cable, no
  crossover. DATA is a single-wire half-duplex UART: the GPIO is driven open-drain in firmware
  (drive low, else input), 4k7 pull-up to 3.3 V on every node (two nodes on a link give an
  effective 2.35 k), 100 R in series as cheap protection against a mis-configured push-pull
  pin. Four links on GPIO0..3 so one PIO block can run all four UARTs. Because every node shares
  the 5 V rail, there is no "one end unpowered" case to worry about on the data line. A keyed
  connector matters: a reversed 3-pin cable would put 5 V on either the data pin or the ground.
- **RP2040** (QFN-56, LCSC C2040) because it needs no programmer (ROM USB bootloader), PIO
  gives as many UARTs as wanted, and it is cheap and always in stock. Alternatives noted:
  STM32G0B1 (six USARTs, USB DFU in ROM), ESP32-C3 (only two UARTs, but a free WiFi gateway
  node), CH32V003/PY32F003 (cheapest, but bit-banged UARTs and a WCH-Link/SWD programmer).
  Minimal RP2040 support per the Raspberry Pi "Hardware design with RP2040" guide: W25Q16
  QSPI flash, 12 MHz crystal with 27 pF loads and 1 k in series with XOUT, 10 k pull-ups on
  RUN and QSPI_SS, TESTEN to GND, USB_VDD / ADC_AVDD / VREG_VIN on 3.3 V, VREG_VOUT to DVDD
  with 1 uF, one 100 nF per IOVDD pin, 10 uF bulk.
- **5 V rail through the net, ME6211C33M5G 3.3 V LDO per node** (SOT-23-5, 500 mA, stable
  with ceramic input/output caps; AMS1117 was rejected because it wants a low-ESR tantalum
  output cap). Node draw is roughly 30 to 50 mA for the RP2040, up to 60 mA for the LED, about
  20 mA for the VL53L0X. A dozen nodes on 5 V is fine; bus voltage and bucks come later if the
  LED gets serious (see Decisions for the first batch).
- **No USB connector.** J6 is a bare 2x4 SMD pad array on 2.54 mm pitch (footprint
  `PinHeader_2x04_P2.54mm_Vertical_SMD`, nothing fitted, excluded from BOM and position files)
  for a pogo-pin jig carrying SWD, USB D+/D- (27 R series on the board), RUN, BOOT and 5 V. A
  virgin RP2040 (blank flash) boots straight into the ROM USB bootloader, so the first flash
  needs only a USB cable on the jig; SWD is there for debugging and for re-flashing without
  pressing anything. Later, firmware can update neighbours over the links (a UART bootloader),
  so the jig is only ever needed once per node. Tag-Connect was considered and rejected (the
  cable costs more than several nodes; a home-made pogo block does the same job).
- **LED: WS2812B-2020** so level maps to colour and brightness with one pin and the gradient is
  obvious in a room. D1 (1N4148W) drops its supply to about 4.3 V so 3.3 V logic meets the
  0.7 x VDD input threshold; C19 100 nF at the LED. A discrete RGB LED on three PWM pins was
  the cheaper alternative (no level issue) but dimmer and three pins. A "powerful" emitter with
  a MOSFET was left out of rev A on purpose. D4 is a second WS2812B-2020 chained on D2's DOUT,
  DNP in every variant: fitting it doubles the light with no firmware or power-design change
  (the LED budget becomes about 120 mA per node). Firmware must always send two pixels,
  whether or not D4 is fitted: D2 forwards the second pixel on DOUT and nothing listens.
- **Sensor port with build variants** (KiCad 10 design variants, all in one schematic):

  | variant   | populated                                    | use                          |
  |-----------|----------------------------------------------|------------------------------|
  | (default) | U3 VL53L0X time-of-flight + C20/C21          | proximity, distance -> level |
  | `vib`     | SW1 SW-18010P spring switch + C22 debounce   | draped over a bush           |
  | `bare`    | header J5 only                               | off-board modules            |

  J5 (5V, 3V3, INT, SDA, SCL, AIN, GND) is always fitted and takes LD2410 mmWave (5 V, about
  $3, fast), AM312 PIR (3.3 V, about $1, slow: roughly 2 s retrigger, which blurs a wave), any
  I2C breakout, or an analogue sensor on the ADC pin. All options share the same nets
  (SENS_INT, SENS_XSHUT, SDA/SCL, SENS_AIN), so firmware needs no board knowledge beyond
  "which variant". VL53L0X was chosen for the default because it is fast and returns distance,
  so the initial excitation can scale with how close the hand is. It runs at 3.3 V (AVDD range
  2.6 to 3.5 V; I/O tolerant up to AVDD), with 100 nF + 4.7 uF, XSHUT on GPIO7 (the RP2040's
  reset-default pull-down holds the sensor off until firmware raises it), GPIO1 interrupt is
  open drain and uses the shared 10 k SENS_INT pull-up. The spring switch is bouncy and
  event-like: 10 k pull-up, 100 nF debounce, treat it as a pulse in firmware. An IR reflective
  option (TCRT5000 on the ADC line) was considered but dropped for rev A: no stock KiCad symbol,
  and the header covers it.
- **No buzzer (dropped 2026-09-20).** Rev A had a 12 mm magnetic buzzer with a 2N7002 low-side
  switch on GPIO5; it was the largest part after the connectors, and sound would have had to
  share the 5 V budget with the LEDs (two LEDs already take most of a 5 A supply). GPIO5 is now
  a no-connect; a buzzer can come back in rev B as a small SMD part if sound turns out to matter.
- **Mechanical:** four M2 holes (H1..H4, no pads, excluded from BOM/pos). No jig locating
  holes on the board; the jig can register on the M2 holes or a printed frame.

## Pinouts

Link J1..J4 (N, E, S, W): 1 = +5V, 2 = DATA, 3 = GND.

Sensor header J5: 1 +5V, 2 +3V3, 3 SENS_INT (GPIO6), 4 SDA (GPIO8), 5 SCL (GPIO9),
6 SENS_AIN (GPIO26/ADC0), 7 GND.

Programming pads J6 (2x4, odd pins in one row, even in the other; on the board the two rows
are 5.05 mm apart and the columns 2.54 mm, see the PCB section):

| pin | signal  | pin | signal          |
|-----|---------|-----|-----------------|
| 1   | USB_DP  | 2   | SWDIO           |
| 3   | USB_DM  | 4   | SWCLK           |
| 5   | GND     | 6   | RUN             |
| 7   | +5V     | 8   | BOOT (QSPI_SS)  |

USB D+/D- have the 27 R series resistors on the board. Ground BOOT while applying power to
force the USB bootloader on a programmed node.

GPIO map: 0..3 LINK_N/E/S/W, 4 LED_DIN, 6 SENS_INT, 7 SENS_XSHUT, 8 SDA (I2C0), 9 SCL (I2C0),
26 SENS_AIN (ADC0). GPIO5 (ex buzzer), 10..25 and 27..29 are unconnected (no-connect flags).
Crystal on XIN/XOUT, flash on QSPI_SS/SCLK/SD0..3, SWCLK/SWDIO and RUN to J6.

## Reference designators

| ref        | part                                   | notes                                   |
|------------|----------------------------------------|-----------------------------------------|
| U1         | RP2040                                 | LCSC C2040 (verify)                     |
| U2         | W25Q16JVSSIQ, SOIC-8 208 mil           | C82317 (verify)                         |
| U3         | VL53L0CXV0DH/1                         | default variant only; LCSC blank        |
| U4         | ME6211C33M5G-N, SOT-23-5               | C82942 (verify); CE tied to VIN         |
| Y1, C1, C2, R1 | 12 MHz 3225 (C9002, verify), 27 pF, 1 k | per RP2040 design guide            |
| C3..C12    | 100 nF x8, 1 uF, 10 uF                 | 3.3 V decoupling (IOVDD x6, USB, ADC, VREG_VIN, bulk) |
| C13..C15   | 1 uF, 100 nF, 100 nF                   | DVDD (1.1 V core)                       |
| C16        | 100 nF                                 | flash                                   |
| C17, C18   | 10 uF                                  | LDO in/out                              |
| R2..R6     | 10 k, 10 k, 4k7, 4k7, 10 k             | RUN, QSPI_SS, SDA, SCL, SENS_INT pull-ups |
| J1..J4, R7/R9/R11/R13 (100 R), R8/R10/R12/R14 (4k7) | links N/E/S/W | JST B3B-XH-A, LCSC blank |
| J6, R15, R16 | pogo pads, 27 R x2               | J6 not in BOM/pos                       |
| D1, D2, D4, C19 | 1N4148W, WS2812B-2020 x2, 100 nF  | LED supply drop, LED, second LED (DNP), cap |
| J5         | 1x7 pin header                         | sensor port                             |
| C20, C21   | 100 nF, 4.7 uF                         | VL53L0X, default variant only           |
| SW1, C22   | SW-18010P, 100 nF                      | `vib` variant only (DNP otherwise)      |
| H1..H4     | M2 mounting holes                      | not in BOM/pos                          |

## Programming jig

Eight P75 pogo pins in a 2x4 grid: columns on 2.54 mm pitch, the two rows 5.05 mm apart (the
SMD header footprint, not a 2.54 mm grid; a printed block, not perfboard),
plus two pins for the M2 holes or a printed frame to locate the board. Wire them to:

- a Raspberry Pi Debug Probe or a Pico running picoprobe (SWDIO, SWCLK, GND; power from +5V),
  flashed with `openocd` or `picotool load`; or
- a cut USB cable (D+, D-, GND, +5V) and a BOOT jumper: the node enumerates as `RPI-RP2`, drag
  the UF2 on.

Nothing is fitted on the board for this: the connector cost per node is zero. The jig can also
be the 5 V supply for bench work on a single node.

## Variants and exports

Variants are stored per symbol instance in the schematic (see CLAUDE.md for the syntax) and
written by `generate/schematic.py` through `schgen.place(dnp=..., variants={...})`: U3, C20,
C21 carry `vib`/`bare` -> DNP; SW1 and C22 are DNP in the base and `vib` -> populated. The
variant name set is whatever appears on the symbols; nothing is registered in the project file.

`make check|fab|jlcpcb BOARD=net/node` builds the **default** variant (VL53L0X). For the others,
until the jobset grows per-variant outputs (CLAUDE.md ideas list, item 9):

```sh
cd boards/net/node
kicad-cli sch export bom --variant vib --exclude-dnp --group-by Value \
  --fields 'Reference,Value,Description,Footprint,MPN,Manufacturer,LCSC,${QUANTITY}' \
  --labels 'Refs,Value,Description,Footprint,MPN,Manufacturer,LCSC,Qty' -o out/node-bom-vib.csv node.kicad_sch
kicad-cli pcb export pos --variant vib --exclude-dnp --format csv --units mm --side both -o out/node-vib-pos.csv node.kicad_pcb
```

`${VARIANT}` in `-o` with several `--variant` flags writes one file per variant. Verified on
2026-09-16: `vib` lists SW1 and C22 and drops U3/C20/C21; `bare` lists neither set. Then
`python3 -m boardtools jlcpcb bom|pos` converts them exactly as `make jlcpcb` does.

## Parts and cost

LCSC numbers in the schematic that still need checking on the order page: C2040 (RP2040),
C82317 (W25Q16JVSSIQ), C82942 (ME6211C33M5G-N), C9002 (12 MHz 3225).
Blank and to be picked in JLCPCB's BOM tool: WS2812B-2020, 1N4148W, VL53L0CXV0DH/1, JST
B3B-XH-A, SW-18010P, all 0603 passives. As with the other boards, `Description`
carries ratings (X7R 16 V, C0G, etc.) into the JLCPCB Comment column.

Rough per-node parts cost at 50 to 100 pieces: about $1.50 for the RP2040, flash, crystal and
LDO; $0.50 for connectors, LED and passives; the VL53L0X adds about $1.50, the
spring switch a few cents. Add PCB (small 2-layer, cheap) and assembly (the RP2040 and the
VL53L0X are reflow-only; everything THT is hand-solderable). The ToF variant is the expensive
one; the bare variant plus a $1 PIR module on J5 is the cheapest way to get a working net.
Cables are a real line item: one 3-wire XH cable per link, roughly two per node in a grid.

## Firmware sketch

- **Link layer:** PIO single-wire UART on GPIO0..3, 9600 to 115200 baud, open-drain (drive
  low, release to input). One byte per change: the node's current level. Optional second byte
  for colour/mode later.
- **Automaton:** state = max(own sensor level, max over links of (neighbour level - 1)),
  decaying over time. A level that drops by one per hop guarantees the wave terminates on any
  topology, loops included. Add a deliberate per-hop delay (tens of ms) or the ripple across
  20 hops takes 20 ms and is invisible.
- **Direction:** the receiving port is known, so waves can be biased to flow away from the
  source, or colours can encode direction.
- **Sensor mapping:** VL53L0X distance -> initial level (closer = higher); PIR/switch -> fixed
  level pulse; ADC -> threshold.
- **Global commands:** flood with a hop count (colour, reset, brightness). A host can attach via
  a WiFi node (ESP32 on J5, or a future variant) or a node on the jig's USB.
- **Later:** UART bootloader over the links so a programmed node can flash its neighbours.

## Decisions for the first batch (2026-09-19)

- **Net size: 5 x 5, 25 nodes.** Order 30 boards (5 spares). A 5 x 5 grid has 40 links, so
  order about 50 XH cables plus a few to cut into power tails.
- **LED power class: WS2812B-2020 stays.** D4 (second LED, DNP) is the brightness hedge; a
  1 W emitter means a 12/24 V bus and a driver per node, which is rev B. Budget per node: about
  130 mA with one LED lit (RP2040 + VL53L0X + LED), 190 mA with D4 fitted; 3.3 to 4.8 A for the
  whole net at full white.
- **5 V injection: one tail per row**, into the free W connector at the grid edge, from a 5 V
  5 A supply. A single corner injection would push the full net current through one XH contact
  (rated 3 A) and drop several hundred mV over the first hops; per row the worst chain carries
  four nodes and drops about 0.1 V on 30 cm 26 AWG cables. Any edge connector works as a tail,
  so no board change.
- **Cable: JST-XH keyed 3-pin**, pre-made double-ended, one length for the whole net. 20 cm gives
  a net about 0.8 m square, 30 cm about 1.2 m; pick from where it will hang.
- **Sensor: one assembled build, the default (VL53L0X) variant.** J5 is always fitted, so a
  default board also takes a PIR or LD2410; `vib` is a default board plus a hand-soldered SW1
  (THT) and C22 (0603). A second assembly order for `bare` only pays past roughly 20 to 30 nodes
  of savings, so not for this batch.
- **Level scale:** corner to corner is 8 hops, so with one level lost per hop the excitation
  range must be well above 8 (use 0..255) or a corner touch never reaches the far corner.
- **Outdoor use** stays deferred: series R + TVS on each link, sealed connectors and a coating
  before any bush deployment that sees weather.
- **LCSC numbers.** Only C2040, C82317, C82942 and C9002 are filled in and none are
  confirmed on the order page; the rest are blank on purpose.

## PCB (rev A, in progress)

`generate/pcb.py` -> `node.kicad_pcb`, 48 x 48 mm, **4 copper layers**: F.Cu signals, In1.Cu
GND plane, In2.Cu +3V3 plane, B.Cu GND pour plus the 5 V ring and the back-layer crossings.
Why four: with 0.2 mm track / 0.2 mm clearance / 0.6 mm vias a via needs a 1.0 mm lane, so at
the RP2040's 0.4 mm pitch only every third pin can via near the chip; on two layers the QSPI
group (51..56) and the power/USB group (43..50) on the same edge fight for the same space, and
every IOVDD/DVDD pin still needs a cap and a ground return. Codex confirmed a six-track QSPI
escape does fit on two layers, so the plane argument (return paths, decoupling by via) is the
real one. JLCPCB 4-layer adds roughly $1 per board at this size.

Floorplan (board-local mm, origin top-left): J1..J4 centred on each edge (N top, E right, S
bottom, W left; pin 1 = +5V is the clockwise-first pin); M2 holes 3.5 mm in from each corner
with 3.2 mm keepouts on all copper layers; U1 rot 180 at (12, 13) so GPIO0..12 face the
centre on its right edge, crystal/SWD/RUN on its top edge, QSPI/USB/core power on its bottom
edge; U2 flash rot 90 directly below U1 (near row SD3/SCLK/SD0 straight down, far row
SS/SD1/SD2 around the right side); Y1/R1/C1/C2 above U1; D2/D4 at (21.5, 24)/(25.5, 24);
buzzer body centred (34.2, 26.7) with Q1/R17/R18 to its left and D3 above; U4 LDO top-right;
J6 pogo pads rot 90 at (12.5, 36) (even row y 33.5 = SWDIO/SWCLK/RUN/BOOT, odd row y 38.5 =
USB_DP/USB_DM/GND/+5V, columns 2.54 mm apart, rows 5.05 mm apart); U3 + C20/C21 + I2C
pull-ups bottom-centre; J5 rot 90 with pin 1 at (20.73, 38.6) so the J3 data trace passes
between pins 1 and 2 at x = 22 (0.32 mm to each pad, DRC-clean); SW1/C22 bottom-right.
Courtyards are DRC-clean; a bounding-box checker for quick iteration lives in the session
scratchpad only (parse F.CrtYd, transform by `at`, report overlaps).

## Resume path

1. Re-read this file, `generate/README.md` and the CLAUDE.md section on generating KiCad files.
   `generate/sch-1.png` is the rendered sheet. Regenerate the schematic only if the design
   changes; regeneration replaces every UUID. Regenerate the PCB with
   `kicad-cli sch export netlist --format kicadsexpr -o boards/net/node/generate/node.net
   boards/net/node/node.kicad_sch && python3 boards/net/node/generate/pcb.py` (the `.net` is
   git-ignored) and check with `make check BOARD=net/node` plus
   `kicad-cli pcb render --side top`.
2. Fix the pcbgen bugs Codex found first, with tests: (a) `copper_layers` re-inserts
   In1/In2 on every run because pcb.py reads its own output as the template (the committed
   board has six copies of each); skip layers already present. (b) A footprint without an
   `attr` clause loses the dnp/exclude flags. (c) `kicad-cli pcb export pos --variant vib` gives
   the opposite of the BOM because footprints carry only the base dnp; find the KiCad 10
   board-side variant syntax and emit it, or document that position files are exported per
   variant from the BOM's reference list instead.
3. Re-place per the review before routing: decoupling caps within ~2 mm of their pins (C9
   USB_VDD, C10 ADC_AVDD, C13 VREG_VOUT, C14/C15 DVDD are 5.6 to 7.3 mm away; C5/C8/C11/C16
   3.8 to 4.3 mm); R15/R16 together next to U1's USB pins; C17/C18 on U4's pin side; C20/C21 on
   U3's supply side (AVDDVCSEL/AVSSVCSEL); crystal cluster rotated so Y1's XIN pad is not
   6.8 mm from the pin and R1 is not over XIN's escape; a bypass cap for D4.
4. Route, in this order: 5 V ring on B.Cu (inset 1.5 mm, notched around the hole keepouts)
   feeding J1..J4 pin 1, J6 pin 7, U4, BZ1, D1, J5 pin 1; via every 3V3/GND pad to the planes;
   U1 escapes (right edge GPIOs fan out then via to B.Cu for LINK_N/E/W, LED_DIN, BUZZ, SDA/SCL,
   SENS_*; bottom edge: QSPI as above, USB_DM/DP via to B.Cu to R15/R16, DVDD 45/50 joined on
   B.Cu with 23; top edge: RUN/SWDIO/SWCLK left then down the west side to J6, XOUT straight
   to R1, XIN jogs right over the NC pins 15..18 to Y1, TESTEN to a GND via at (14.8, 8.5));
   then finish with `kicad-cli pcb drc --refill-zones --save-board --schematic-parity`. Place
   silk deliberately at the end (19 silk warnings now: references over pads).
5. README fixes from the review: J6 jig geometry (2.54 mm columns, 5.05 mm rows); D4 needs
   the firmware to always send two pixels; add the buzzer to the power budget (two LEDs already
   take 4.75 A of a 5 A supply, so pick the buzzer and cap simultaneous sound).
6. LCSC numbers, `make jlcpcb BOARD=net/node`, order (see Decisions for the first batch),
   check LED/connector orientation in the JLCPCB preview. Cables: JST-XH 3-pin pre-made,
   one length; XH has no strain relief, so a bush deployment needs a printed clip or tie.
7. Pogo jig, USB bring-up, link protocol, UART bootloader; then rev B (LED power, bus voltage).

`generate/` holds the scripts that produced the schematic and the board (see its README).

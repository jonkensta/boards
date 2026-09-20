# net/node

One cell of a sensor "net": a small RP2040 board with an RGB LED, a buzzer, a sensor port and
four neighbour links. A node that detects something lights up and tells its neighbours; they
repeat the excitation one level weaker, so a wave ripples outwards and dies away. Any number
of nodes are tiled and cabled edge to edge (grid, hexagonal patch, irregular drape over a bush).

## Status: parked (2026-09-17)

Rev A schematic is generated, ERC-clean and committed (0784855, 96f31b5), with the three
sensor variants in place. **No PCB layout, no firmware, nothing ordered, no jig built.**
`node.kicad_pcb` is still the empty template, so `make check` passes only because DRC parity
ignores footprints that were never placed. Work stopped here deliberately; open questions and
the resume path are at the end. This file is meant to be enough to resume cold.

## Concept and first-iteration scope

- The original idea: a cheap board with a bright LED, connected to four others, those to four
  more, forming a net that can be laid over an object, a wall or a bush. Each board has a sensor;
  on detection it lights or sounds and signals its neighbours, who act on it with the signal
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
  LED gets serious (see Open questions).
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
  (the LED budget becomes about 120 mA per node).
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
- **Buzzer:** 12 mm passive magnetic buzzer on 5 V, 2N7002 low-side switch (1 k gate, 100 k
  pull-down), 1N4148W flyback. Populated by default; make it DNP if sound is not wanted.
- **Mechanical:** four M2 holes (H1..H4, no pads, excluded from BOM/pos). No jig locating
  holes on the board; the jig can register on the M2 holes or a printed frame.

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

GPIO map: 0..3 LINK_N/E/S/W, 4 LED_DIN, 5 BUZZ, 6 SENS_INT, 7 SENS_XSHUT, 8 SDA (I2C0),
9 SCL (I2C0), 26 SENS_AIN (ADC0). GPIO10..25 and 27..29 are unconnected (no-connect flags).
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
| BZ1, Q1, R17, R18, D3 | buzzer, 2N7002 (C8545), 1 k, 100 k, 1N4148W | buzzer driver            |
| J5         | 1x7 pin header                         | sensor port                             |
| C20, C21   | 100 nF, 4.7 uF                         | VL53L0X, default variant only           |
| SW1, C22   | SW-18010P, 100 nF                      | `vib` variant only (DNP otherwise)      |
| H1..H4     | M2 mounting holes                      | not in BOM/pos                          |

## Programming jig

Eight P75 pogo pins in a 2x4 grid on 2.54 mm pitch (perfboard or a small 3D-printed block),
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
C82317 (W25Q16JVSSIQ), C82942 (ME6211C33M5G-N), C9002 (12 MHz 3225), C8545 (2N7002).
Blank and to be picked in JLCPCB's BOM tool: WS2812B-2020, 1N4148W, VL53L0CXV0DH/1, JST
B3B-XH-A, SW-18010P, buzzer, all 0603 passives. As with the other boards, `Description`
carries ratings (X7R 16 V, C0G, etc.) into the JLCPCB Comment column.

Rough per-node parts cost at 50 to 100 pieces: about $1.50 for the RP2040, flash, crystal and
LDO; $0.50 for connectors, LED, buzzer driver and passives; the VL53L0X adds about $1.50, the
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

## Open questions (decide before resuming)

- **LED power class.** Rev A uses a WS2812B-2020 (about 60 mA max). A "powerful" LED per node
  changes the power design: a 12 V or 24 V bus with a buck per node, a constant-current driver
  (AL8860 class), and connector current ratings. Decide the target net size and the worst-case
  number of lit nodes first; that sets the supply and the number of injection points.
- **Sensor for the first batch.** VL53L0X (default variant) gives distance-scaled excitation but
  is the costliest part on the board; `bare` plus an off-board PIR or LD2410 on J5 is cheaper
  and enough to prove the wave behaviour.
- **Cable.** JST-XH keyed 3-pin is the rev A choice. Pre-made XH cables are cheap but each
  link needs one; check cable cost against node cost before ordering many. 2.54 mm headers with
  Dupont jumpers would be cheaper but unkeyed (reversal puts 5 V on DATA or GND).
- **LCSC numbers.** Only C2040, C82317, C82942, C9002 and C8545 are filled in and none are
  confirmed on the order page; the rest are blank on purpose.
- **Outdoor use** was explicitly deferred: add series R + TVS on each link, sealed connectors,
  and a coating before any bush deployment that sees weather.

## Resume path

1. Re-read this file, `generate/README.md` and the CLAUDE.md section on generating KiCad files
   (labels, variants, property text). `generate/sch-1.png` is the rendered sheet. Regenerate
   only if the design changes (`python3 boards/net/node/generate/schematic.py`, then
   `make check BOARD=net/node`); regeneration replaces every UUID.
2. PCB layout as `generate/pcb.py`, following `boards/chromatone/isolator/generate/`: about
   40 x 40 mm, one link connector centred on each edge, LED in the middle, J6 pads and the
   sensor on the top side, M2 holes in the corners. Export the netlist first
   (`kicad-cli sch export netlist --format kicadsexpr`). Expect the RP2040's 0.4 mm QFN fan-out
   to be the hard part on two layers (see the TSSOP notes in CLAUDE.md for the via rules).
   Finish with `kicad-cli pcb drc --refill-zones --save-board --schematic-parity`.
3. Fill in / confirm LCSC numbers, `make jlcpcb BOARD=net/node` for the default variant, the
   hand-run `--variant` commands above for `vib` and `bare`. Order a handful of default + bare
   boards; check LED and connector orientation in the JLCPCB placement preview.
4. Build the pogo jig, bring up one node over USB, then write the link protocol and the UART
   bootloader so the jig is a one-time touch.
5. Then revisit LED power and bus voltage for a larger net (rev B).

`generate/` holds the script that produced the schematic (see its README).

# net/node

One cell of a sensor "net": a small RP2040 board with four corner RGB LEDs, a sensor and four
neighbour links. A node that detects something lights up and tells its neighbours; they
repeat the excitation one level weaker, so a wave ripples outwards and dies away. Any number
of nodes are tiled and cabled edge to edge (grid, hexagonal patch, irregular drape over a bush).

## Status: four corner LEDs and the pre-order fixes in, DRC clean, not reviewed (2026-09-25)

2026-09-25: the single LED D2 (and the DNP D4) became **four WS2812B-2020-V6, one per corner** (D1..D4,
chained NE -> NW -> SW -> SE), run from +5V through a 5 V buffer U5 instead of the old D1 drop diode; the
panel's pre-order findings went in at the same time (BOOT 1 k R19, TVS D5, USB backfeed Schottky D6, balanced
quiet piezo drive, J1..J4 / SW1 out of the placement file, no vias in the J6 pogo pads). Board still 48 x 48.
`make check` 0 / 0 / 0 and no warnings, `make parts` 25 lines 0 / 0. See the Decisions entries dated
2026-09-25. The earlier status follows.

Rev A schematic is generated and ERC-clean. `generate/pcb.py` places and routes the whole
board (48 x 48 mm, 4 layers); `make check BOARD=net/node` passes with 0 violations,
0 unconnected items, 0 schematic-parity issues and no warnings. On 2026-09-24 the board was
re-placed and re-routed to the floorplan rule in Decisions: the RP2040 and its immediate
support fill the centre square between the four link housings, the peripherals take the
corners, and no pad, via, part or courtyard comes within 3.7 mm of a mounting-hole centre.
The sensor header J5 was removed in the same pass (see Decisions, sensor variants). The side-entry
connectors, their tiling alignment and the earlier review fixes are unchanged; the new layout has
not been reviewed yet (see Resume path). **No firmware, nothing ordered, no jig built.** LCSC
numbers verified 2026-09-24 via `make parts` (see Parts and cost). Next: review,
`make jlcpcb BOARD=net/node`, order-page check, jig.

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
- **Side-entry link connectors** (2026-09-24): J1..J4 changed from the vertical B3B-XH-A
  (C144394) to the right-angle **S3B-XH-A(LF)(SN), LCSC C157928** (extended, ~142k in stock),
  so cables leave in the plane of the board and a node lies flat instead of standing on four
  upright plugs. Each housing sits on its own edge with the mouth facing out and **1.1 mm past
  the edge** (pin row 8.1 mm in). The housing is 11.5 mm deep (mouth 9.2 mm in front of the
  pins); flush mounting would cost another 1.1 mm of board on every side, and a bigger
  overhang leaves less of the 7 mm base on the board (at 1.1 mm about 6 mm is supported).
  Tiled nodes need at least 2.2 mm between boards plus the plug and cable bend. Footprint:
  `boards:JST_XH_S3B-XH-A_1x03_P2.50mm_Horizontal_EdgeMount`, the stock Connector_JST footprint
  with the silkscreen stopped 1.5 mm short of the mouth and the contact-slot marks removed.
  The stock silk crosses the board edge (`silk_edge_clearance` warnings), and trimming it in
  the generator instead gives `lib_footprint_mismatch` warnings. A through-hole footprint cannot be
  mirrored, so **pin 1 is now the counter-clockwise-first pin** of each edge (it was the
  clockwise-first pin with the vertical part). The pinout per connector is unchanged, and
  that is all a straight cable needs.
- **Tiling alignment** (2026-09-24): nodes are tiled by translation (every node the same way
  up), so each W connector J4 lines up exactly with the E connector J2 of its western neighbour
  and each S connector J3 with the N connector J1 of its southern neighbour. All four are also
  centred on their edges: pin 2 of J1/J3 at x 24.0 and of J2/J4 at y 24.0 (the board centre
  lines). `generate/pcb.py` derives the positions from two shared constants (W/2, H/2) and
  asserts both the alignment and the centring (1 um), so neither can silently regress. The pin
  rows coincide as sets, but because the footprint cannot be mirrored the pin numbers run the
  opposite way on facing edges: J2 (E) pin 1 is the south pin, J4 (W) pin 1 the north pin; J1
  (N) pin 1 is the east pin, J3 (S) pin 1 the west pin. A pin-1-to-pin-1 JST cable between two
  facing connectors therefore takes a half twist, which a loose cable does without complaint.
- **0402 caps at U1 pins 43..45** (2026-09-24): C10 (100 nF, ADC_AVDD), C11 (1 uF, VREG_VIN),
  C13 (1 uF, VREG_VOUT) and C15 (100 nF, DVDD) are 0402; every other passive stays 0603. The
  centred J4's courtyard starts 1.42 mm below U1's, less than a 0603 courtyard (1.46 mm), and
  the old 0603 column west of pins 43..45 sat exactly where J4 now is. In 0402 all four fit
  around U1's bottom-left corner with 1.4 to 2.9 mm of track from pin to pad (before: 2.6 to
  8.0 mm). Parts are JLCPCB basic: 100 nF Samsung CL05B104KB54PNC X7R 50 V (C307331) and 1 uF
  Samsung CL05A105KA5NQNC X5R 25 V (C52923; no basic 0402 1 uF is rated 50 V, and the rails
  are 3.3 V and 1.1 V). Their Descriptions end in "0402" so the BOM keeps them on separate lines.
- **Floorplan: MCU in the centre, peripherals in the corners, 3.7 mm hole clearance**
  (2026-09-24). The RP2040 and its immediate support (a cap at every supply pin, crystal,
  flash, LDO, USB series resistors) sit in the 26 mm centre square between the link housings,
  where the space is; each peripheral takes a corner, around its M2 hole, on the side where its
  pins leave U1 (rot 180): piezo BZ1 NE (driven from GPIO18/19 on U1's west edge since 2026-09-25, see
  crystal isolation), ToF U3 SE below J2
  (I2C / INT / XSHUT come off U1's east edge and cross the QSPI rows in one short B.Cu hop), pogo
  pads J6 SW (USB and, via the flash, BOOT leave U1's south edge; SWD comes down the west side),
  vibration switch SW1 NW (it needs only SENS_INT, one slow B.Cu lane under J1). The LEDs sat NE of
  U1 beside the crystal until 2026-09-25; they are now one per corner (see corner LEDs).
  **Hole clearance:** no copper pad, via, part body or courtyard within 3.7 mm of a hole
  centre, so a 5 mm M2 washer keeps more than 1.2 mm from every pad (before: C2's pad was
  3.08 mm from H1). Enforced twice. DRC: each hole gets a keepout annulus 2.6..3.7 mm
  (`pads`, `vias` and `footprints` not allowed; circumscribed polygon) besides the old 3.2 mm
  track keepout; the hole's own footprint (courtyard r 2.45) lies inside the annulus's hole, so
  the NPTH does not trip it. Verified on a copy: a cap pad and the piezo courtyard nudged into the
  annulus are both flagged, the holes are not. Generator: `pcb.py` asserts the pad-edge and
  courtyard distances from every hole centre (closest now: BZ1 courtyard 3.75 mm, pad J6.1
  6.43 mm).
- **Crystal isolation (2026-09-25).** An audit found switching copper beside the 12 MHz crystal
  nets (XIN, XOUT, the R1-Y1 node): BUZZ_B 0.51 mm, BUZZ_A 1.25 mm, +3V3 0.20 mm, DVDD 0.60 mm,
  SWCLK 1.0 mm, LINK_N 0.93 mm. Root cause: the piezo was on GPIO12/13 (pins 15/16), four pins
  from XIN/XOUT on the same package edge. Rule now: every non-GND net keeps >= 1.0 mm (same layer,
  edge to edge, tracks and pads) from crystal-net copper, the LED nets (LED_VDD, LED_DIN,
  D2 DOUT) and every D4 pad >= 2.0 mm; only the RP2040's own 0.4 mm-pitch pin field plus 1.5 mm
  of escape is exempt. `generate/xtal_check.py` measures it and `pcb.py` asserts it (checked: a
  LINK_N row nudged 0.4 mm and D4 moved 0.3 mm west each fail generation). Changes: the piezo
  moved to GPIO18/19 (pins 29/30, PWM slice 1, U1's NW corner; the only free even/odd pairs on
  the NE side are GPIO14/15 next to XIN, and GPIO8/9 whose escape collides with IOVDD 10's via,
  see the GPIO map) and reaches BZ1 on B.Cu under U1; XOUT follows XIN diagonally before turning
  north so IOVDD 22 / DVDD 23 / C5 stay >= 1 mm away (Y1 / R1 0.65 / 0.8 mm east, C2 vertical,
  C1 lower, LINK_N re-routed north of C2, D2 / D4 0.6 mm east); a F.Cu GND guard pour (priority 1,
  solid onto GND pads) covers the cluster. Its outline (`GUARD` in pcb.py: 24.12..31.5 x
  10.75..19.45, notched around R7 and D4) encloses nothing but GND and crystal copper, asserted
  with >= 0.2 mm from the outline to any other copper (checked: the old rectangle fails on D4's
  pads, LED_VDD and LINK_N). 19 GND vias, placed by script, stitch it to In1, 18 along its edge at
  <= 2 mm pitch except beside R1's XOUT pad (3.7), at C2's node pad (3.0 / 2.2) and at the U1
  escape (2.6); every one of the pour's three fill pieces has its own vias, and the load caps'
  and Y1's GND pads have short vias. In1 stays unbroken under the cluster (no other-net via
  inside the pour; In1 / In2 carry no tracks). The checker measures tracks (arcs included),
  vias, pads and zone copper, and raises on copper it does not model; D4's pads get the 2 mm
  rule whatever their net (GND included). **Known exemption:** within the RP2040's pad field plus
  1.5 mm, where the pins are 0.4 mm apart, the IOVDD 22 escape runs 0.20 mm and the DVDD 23
  escape 0.60 mm from XOUT's escape (SWCLK 1.0 mm). Pins 21 / 22 / 23 are adjacent, and 22 / 23
  are held in the NW fan's order by SWCLK / SWDIO / RUN, so no cheap re-route reaches 1 mm.
  Beyond that zone they are 1.07 mm (+3V3) and 1.51 mm (DVDD). Since the corner LEDs (2026-09-25) the
  2 mm rule covers +5V (the LED supply), LED_DATA, LED_DIN, LED_CH1..3 and every pad of D1..D4
  whatever its net; the nearest is J1.1 (+5V) at 2.11 mm from C2's node pad.
- **Pogo pads centred in the SW corner (2026-09-25).** J6 moved from (12.9, 40.3) to (12.4, 35.9),
  same orientation (rotating gains nothing): its courtyard is now 0.57 / 0.58 / 0.60 mm from J3's
  courtyard, J4's courtyard and H3's 3.7 mm ring (before 0.07 / 4.98 / 0.12 mm), the best the
  corner allows.
- **RP2040** (QFN-56, LCSC C2040) because it needs no programmer (ROM USB bootloader), PIO
  gives as many UARTs as wanted, and it is cheap and always in stock. Alternatives noted:
  STM32G0B1 (six USARTs, USB DFU in ROM), ESP32-C3 (only two UARTs, but a free WiFi gateway
  node), CH32V003/PY32F003 (cheapest, but bit-banged UARTs and a WCH-Link/SWD programmer).
  Minimal RP2040 support per the Raspberry Pi "Hardware design with RP2040" guide: W25Q16
  QSPI flash, 12 MHz crystal (Abracon ABM8-272-T3, the guide's part) with 15 pF loads and 1 k in series with XOUT, 10 k pull-ups on
  RUN and QSPI_SS, TESTEN to GND, USB_VDD / ADC_AVDD / VREG_VIN on 3.3 V, VREG_VOUT to DVDD
  with 1 uF, one 100 nF per IOVDD pin, 10 uF bulk.
- **5 V rail through the net, ME6211C33M5G 3.3 V LDO per node** (SOT-23-5, 500 mA, stable
  with ceramic input/output caps; AMS1117 was rejected because it wants a low-ESR tantalum
  output cap). Node draw is roughly 30 to 50 mA for the RP2040, up to 60 mA for the LED, about
  20 mA for the VL53L0X. A dozen nodes on 5 V is fine; bus voltage and bucks come later if the
  LED gets serious (see Decisions for the first batch).
- **No USB connector.** J6 is a bare 2x4 SMD pad array on 2.54 mm pitch (footprint
  `boards:PogoPads_2x04_P2.54mm`, the stock 2x4 SMD header pads without the paste layer so the
  stencil leaves them bare; nothing fitted, excluded from BOM and position files)
  for a pogo-pin jig carrying SWD, USB D+/D- (27 R series on the board), RUN, BOOT and 5 V. A
  virgin RP2040 (blank flash) boots straight into the ROM USB bootloader, so the first flash
  needs only a USB cable on the jig; SWD is there for debugging and for re-flashing without
  pressing anything. Later, firmware can update neighbours over the links (a UART bootloader),
  so the jig is only ever needed once per node. Tag-Connect was considered and rejected (the
  cable costs more than several nodes; a home-made pogo block does the same job).
- **LED: WS2812B-2020** (the V6 revision, WS2812B-2020-V6, C52917434; the original C965555 is
  discontinued) so level maps to colour and brightness with one pin and the gradient is
  obvious in a room. A discrete RGB LED on three PWM pins was the cheaper alternative (no level
  issue) but dimmer and three pins. A "powerful" emitter with a MOSFET was left out of rev A on
  purpose. Until 2026-09-25 there was one LED (D2) beside the crystal, a DNP second LED D4 on its
  DOUT and a 1N4148W (D1) dropping its supply to about 4.3 V; see corner LEDs and LED supply.
- **Four corner LEDs (2026-09-25).** D1..D4, one WS2812B-2020-V6 per corner, so a node is a 2 x 2
  sub-pixel grid and a pattern moving across the net shows its *direction* inside each node, not
  just a brightness step per node. Placement is 4-fold rotationally symmetric about the board centre
  (`pcb.py` lays out the NW corner once and rotates it): each LED centre is 4.0 mm in from one edge
  and 8.8 mm along it from the corner (NW (4.0, 8.8), NE (39.2, 4.0), SE (44.0, 39.2), SW (8.8, 44.0)),
  so the four sit on a 35.8 mm square turned about 12 deg, and a node tiled a quarter turn round looks
  the same. 8.8 mm is the least that keeps the LED courtyard outside the 3.7 mm hole ring (3.78 mm);
  the other corner parts (BZ1, U3, J6, SW1) did not have to move, and the board stays 48 x 48.
  Chain, in quadrant order (counter-clockwise from NE, as the link connectors' pin 1): LED_DIN ->
  **D1 NE (pixel 0) -> D2 NW (1) -> D3 SW (2) -> D4 SE (3)**; each hop runs along one edge (N, W, S)
  on F.Cu 3.45 mm in, turning 45 deg round the hole; the E edge (J2, U3, the I2C pull-ups) carries none.
  Each LED has its own 100 nF 0402 (C19, C23, C24, C25; C307331) beside its VDD pad with a via onto
  the 5 V ring's corner notch, and its own GND via (loop below). The SE LED is 5.4 mm from U3's
  centre (about 3.2 mm body to body), beside the sensor rather than above it: it is outside the
  25 deg emitter / receiver cones and lower than U3's window, but firmware should still range with
  D4 dark or dim if it shows crosstalk. Rejected: LEDs on the diagonals (7.5, 7.5): three corners
  hold BZ1, SW1 and J6 there; LEDs a quarter of the way in (12, 12) (a uniform lattice across tiled
  nodes) is inside the centre square and not "at the corners".
- **LED supply: +5V and a 5 V buffer, D1 removed (2026-09-25).** Four LEDs at full white draw
  4 x 36 mA = 144 mA, the 1N4148W's rating, and a drop diode is poor level shifting anyway: the V6
  idles at < 1 uA, so at idle a 1 A rectifier (SM4007PL, C64898, basic) drops only 0.3..0.4 V, LED
  VDD rises to about 4.9 V on a 5.25 V rail and VIH = 0.55 VDD = 2.7 V, above the RP2040's datasheet
  VOH minimum (2.62 V at IOVDD 3.3 V): negative margin by datasheet. Chosen instead: the LEDs run on
  +5V directly and **U5 SN74AHCT1G125DBVR (C7484, extended)**, powered from +5V, buffers GPIO4
  (LED_DATA, 3.3 V) onto LED_DIN. Margins at the worst corners (5.25 V rail, IOVDD 3.3 V): RP2040
  VOH 2.62 V min vs AHCT VIH 2.0 V: **0.62 V**; RP2040 VOL 0.5 V max vs AHCT VIL 0.8 V: 0.3 V; AHCT
  VOH 4.4 V min (VCC 4.5 V, 50 uA) vs LED VIH 0.55 x 5.25 = 2.89 V: **1.5 V**; AHCT VOL 0.1 V vs LED
  VIL 0.7 V: 0.6 V. Each LED regenerates the data for the next at its own VDD. /OE is tied low, C26
  100 nF at VCC. Cost: one extended part (a loading fee) and one 0402. Trade-off: the V6's supply
  rating is 3.3..5.3 V, so a 5.25 V rail leaves 50 mV; run the net at 5.0..5.1 V (see first batch).
  AHCT is specified from 4.5 V; powered from the jig through D6 (about 0.35 V drop) a weak USB port
  can sit just below that, which only matters if the LEDs are driven while flashing.
- **Protection and power path (2026-09-25).** D5 **SMF5.0A (C193402, MDD, SOD-123F, extended; no
  basic 5 V TVS exists)**, unidirectional, across +5V at the LDO's input (on the J4.1 feed beside
  C17). VRWM 5.0 V, VBR 6.4..7.0 V at 10 mA, VC 9.2 V at 21.7 A. It cannot hold the ME6211's 6.5 V
  absolute maximum at any real current (nothing with VBR <= 6.5 V would stay off at 5.25 V), so it is
  only an energy sink that limits how far a hot-plug LC ring (up to about twice the rail, ~10 V) can
  go; the actual peak is unmeasured and may exceed 7 V. That limitation covers every part on +5V:
  the LDO (6.5 V abs max), the LEDs (5.3 V max) and U5 (7 V abs max). The real fix for ringing is
  damping at the injection points (an electrolytic of a few hundred uF across each power tail) and
  plugging cables before switching on; both go in the build notes. Measure the plug-in transient on
  the first boards before hot-plugging the net routinely.
  D6 **B5819W (C8598, basic)**, Schottky, from J6.7 (the jig's USB 5 V, anode) to +5V (cathode): USB
  can power a node for programming, a powered net cannot backfeed the host.
- **BOOT through 1 k (2026-09-25).** R19 1 k (C21190) between QSPI_SS and the BOOT pogo pad J6.8, per
  the RP2040 hardware design guide (p. 9: the resistor "allows the QSPI_SS pin to safely over-drive
  the applied pull-down", "placed close to the flash chip"). R19 sits right below the flash's pin 1
  on the SS track; only the BOOT net runs to J6.8. R3 (10 k pull-up) stays on SS.
- **Hand-soldered parts out of the placement file (2026-09-25).** J1..J4 (and SW1) are THT and
  hand-soldered, and their CPL anchor is pin 1, 2.5 mm off the housing centre, so they carry
  `in_pos_files no` (footprint `exclude_from_pos_files`); SW1 repeats it in its `vib` variant entry
  because KiCad 10 reads a flag a variant leaves out as off, not as the base value (`pcbgen` now also
  carries the base exclusions into every variant, with a test). They stay in the BOM for `make parts`
  and loose ordering: on the JLCPCB order page the four J lines show as BOM parts without
  placements; leave them unselected (or have JLCPCB hand-fit them from the BOM, see THT parts).
- **No vias in the pogo pads (2026-09-25).** The SWDIO / SWCLK / RUN and BOOT vias sat inside the J6
  even-row pads, and J6.5's GND via inside its pad; they now sit just outside (0.15..0.17 mm from the
  pad edge, a short F.Cu stub in), so every pogo tip lands on flat copper. J6's geometry and position
  are unchanged.

- **Sensor build variants** (KiCad 10 design variants, all in one schematic):

  | variant   | populated                                    | use                          |
  |-----------|----------------------------------------------|------------------------------|
  | (default) | U3 VL53L0X time-of-flight + C20/C21          | proximity, distance -> level |
  | `vib`     | SW1 SW-18010P spring switch + C22 debounce   | draped over a bush           |
  | `bare`    | no sensor                                    | relay-only node: links + LED |

  All options share the same nets (SENS_INT, SENS_XSHUT, SDA/SCL), so firmware needs no board
  knowledge beyond "which variant". VL53L0X was chosen for the default because it is fast and
  returns distance, so the initial excitation can scale with how close the hand is. It runs at
  3.3 V (AVDD range 2.6 to 3.5 V; I/O tolerant up to AVDD), with 100 nF + 4.7 uF, XSHUT on GPIO5
  (the RP2040's reset-default pull-down holds the sensor off until firmware raises it: PADS_BANK0 GPIO
  reset value 0x56 has PDE = 1, PUE = 0, datasheet table 341), GPIO1
  interrupt is open drain and uses the shared 10 k SENS_INT pull-up. The spring switch is bouncy
  and event-like: 10 k pull-up, 100 nF debounce, treat it as a pulse in firmware. An IR reflective
  option (TCRT5000 on an ADC pin) was considered but dropped for rev A (no stock KiCad symbol).
- **Sensor header J5 removed** (2026-09-24). The 1x7 header (5V, 3V3, INT, SDA, SCL, AIN, GND)
  for off-board modules (LD2410 mmWave, AM312 PIR, I2C breakouts, an analogue sensor) was dropped
  in the floorplan pass: its 18.9 mm courtyard fits no corner (a corner arm is 18.55 mm between a
  link housing and the edge; the old J5 hung over the edge and drew two `silk_edge_clearance`
  warnings) and it cost the longest run on the board (SENS_AIN from U1's far side). GPIO26/ADC0 is
  now a no-connect, and `bare` changed from "header only" to "no sensor" (a relay node that only
  reacts to its neighbours; still useful to fill a net cheaply). Off-board sensors are out of
  rev A; a later revision can bring a header back on an edge.
- **Piezo sounder, not a magnetic buzzer (2026-09-20).** The 12 mm magnetic buzzer with its
  2N7002/flyback driver was dropped (largest part after the connectors, and it would have shared
  the 5 V budget with the LEDs). BZ1 is now a Murata PKMCS0909E4000-R1 9 x 9 x 1.9 mm SMD piezo
  *element* driven from GPIO18/GPIO19 (BUZZ_A/BUZZ_B, PWM slice 1 A/B; GPIO12/13 until 2026-09-25) through 100 R each: no transistor, no 5 V
  draw, and pitch is whatever frequency firmware drives (PWM or PIO). Driving the two pins in
  antiphase gives 6.6 Vpp (about 6 dB more); loudness is otherwise only coarse (near/far from
  the 4 kHz resonance, burst modulation). Roughly 65 to 70 dB at 10 cm: a beep in the room, not
  across it. Timbre is square-wave only; no speech or samples.
- **Mechanical:** four M2 holes (H1..H4, no pads, excluded from BOM/pos) with the 3.7 mm washer
  clearance above. No jig locating
  holes on the board; the jig can register on the M2 holes or a printed frame.

## Pinouts

Link J1..J4 (N, E, S, W): 1 = +5V, 2 = DATA, 3 = GND. On the board pin 1 is the
counter-clockwise-first pin of each connector. Facing connectors of tiled nodes line up pin row on pin row
with the numbers reversed (see Decisions, tiling alignment).

Programming pads J6 (2x4, odd pins in one row, even in the other; on the board the two rows
are 5.05 mm apart and the columns 2.54 mm, see the PCB section):

| pin | signal  | pin | signal          |
|-----|---------|-----|-----------------|
| 1   | USB_DM  | 2   | SWDIO           |
| 3   | USB_DP  | 4   | SWCLK           |
| 5   | GND     | 6   | RUN             |
| 7   | USB 5 V | 8   | BOOT            |

USB D+/D- have the 27 R series resistors on the board. Pad 7 feeds +5V through D6 (Schottky, so a
powered net cannot backfeed the USB host); pad 8 is BOOT, QSPI_SS through R19 1 k. Ground BOOT while
applying power to force the USB bootloader on a programmed node.

GPIO map: 0..3 LINK_N/E/S/W, 4 LED_DATA (3.3 V, into U5 -> LED_DIN), 5 SENS_XSHUT, 6 SENS_INT, 10 SDA (I2C1), 11 SCL (I2C1),
18/19 BUZZ_A/BUZZ_B (piezo, antiphase: PWM slice 1 channels A/B, U1 pins 29/30 on the west edge).
GPIO7..9, 12..17 and 20..29 are unconnected (no-connect flags; GPIO26/ADC0 went with J5, GPIO12/13
were the piezo pair until 2026-09-25). GPIO7..9 are left free on purpose: IOVDD pin 10 sits between GPIO7 and GPIO8 on the QFN, and with
0.4 mm pitch its decoupling via only fits if both neighbours stay unrouted (2026-09-20).
Crystal on XIN/XOUT, flash on QSPI_SS/SCLK/SD0..3, SWCLK/SWDIO and RUN to J6.

## Reference designators

| ref        | part                                   | notes                                   |
|------------|----------------------------------------|-----------------------------------------|
| U1         | RP2040                                 | C2040                                   |
| U2         | W25Q16JVSSIQ, SOIC-8 208 mil           | C82317                                  |
| U3         | VL53L0CXV0DH/1                         | C91199; default variant only            |
| U4         | ME6211C33M5G-N, SOT-23-5               | C82942; CE tied to VIN                  |
| Y1, C1, C2, R1 | 12 MHz 3225 ABM8-272-T3 (C20625731), 15 pF C0G (C1644), 1 k | per RP2040 design guide (HDG crystal, 10 pF load) |
| C3..C12    | 100 nF x8, 1 uF, 10 uF                 | 3.3 V decoupling (IOVDD x6, USB, ADC, VREG_VIN, bulk); C10 (100 nF, C307331) and C11 (1 uF, C52923) are 0402 |
| C13..C15   | 1 uF, 100 nF, 100 nF                   | DVDD (1.1 V core); C13 (1 uF, C52923) and C15 (100 nF, C307331) are 0402 |
| C16        | 100 nF                                 | flash                                   |
| C17, C18   | 10 uF                                  | LDO in/out                              |
| R2..R6     | 10 k, 10 k, 4k7, 4k7, 10 k             | RUN, QSPI_SS, SDA, SCL, SENS_INT pull-ups |
| R19        | 1 k (C21190)                           | QSPI_SS -> BOOT pad J6.8 (RP2040 HDG)   |
| J1..J4, R7/R9/R11/R13 (100 R), R8/R10/R12/R14 (4k7) | links N/E/S/W | JST S3B-XH-A(LF)(SN) side entry, C157928 (THT, hand-soldered: not in the position file) |
| J6, R15, R16, D6 | pogo pads, 27 R x2, B5819W (C8598) | J6 not in BOM/pos; D6 jig USB 5 V -> +5V |
| D1..D4     | WS2812B-2020-V6 x4 (C52917434)         | corner LEDs, chain D1 NE, D2 NW, D3 SW, D4 SE |
| C19, C23..C25, C26 | 100 nF 0402 (C307331)          | one per LED (D1..D4), U5                |
| U5         | SN74AHCT1G125DBVR (C7484), SOT-23-5    | 3.3 V -> 5 V LED data buffer, /OE low   |
| D5         | SMF5.0A (C193402), SOD-123F            | 5 V TVS on +5V at the LDO input         |
| BZ1, R17, R18 | PKMCS0909E4000-R1, 100 R x2    | piezo element (C910763), series R from GPIO18/19 |
| C20, C21   | 100 nF, 4.7 uF                         | VL53L0X, default variant only           |
| SW1, C22   | SW-18010P (C2681585), 100 nF           | `vib` variant only (DNP otherwise); SW1 THT, not in the position file |
| H1..H4     | M2 mounting holes                      | not in BOM/pos                          |

## Programming jig

Eight P75 pogo pins in a 2x4 grid: columns on 2.54 mm pitch, the two rows 5.05 mm apart (the
SMD header footprint, not a 2.54 mm grid; a printed block, not perfboard),
plus two pins for the M2 holes or a printed frame to locate the board. Pad centres (board-local
mm, origin at the top-left corner, y down; the pads sit in the SW corner): even row y 33.375 at
x 8.59 / 11.13 / 13.67 / 16.21 (SWDIO, SWCLK, RUN, BOOT), odd row y 38.425 at the same x
(USB_DM, USB_DP, GND, USB 5 V). Relative to H3's centre (3.5, 44.5): first column +5.09 mm in x, rows
-11.125 and -6.075 mm in y. (2026-09-25: moved 0.5 mm west and 4.4 mm north from (9.09, 37.775 /
42.825), centring J6 between J3, J4 and H3.) Wire them to:

- a Raspberry Pi Debug Probe or a Pico running picoprobe (SWDIO, SWCLK, GND; power from +5V),
  flashed with `openocd` or `picotool load`; or
- a cut USB cable (D+, D-, GND, 5 V on pad 7) and a BOOT jumper to GND (pad 8; R19 1 k on the
  board keeps QSPI_SS able to over-drive it): the node enumerates as `RPI-RP2`, drag the UF2 on.
  Pad 7 reaches +5V through D6, so the USB port powers the node (about 0.35 V lower) but a node
  that is still cabled into a powered net cannot push current back into the host. Keep the LEDs
  dark while flashing from USB (U5 is specified from 4.5 V).

Nothing is fitted on the board for this: the connector cost per node is zero. The jig can also
be the 5 V supply for bench work on a single node (through D6). Every pad is flat copper: the
vias sit just outside the pads (2026-09-25).

## Variants and exports

Variants are stored per symbol instance in the schematic (see CLAUDE.md for the syntax) and
written by `generate/schematic.py` through `schgen.place(dnp=..., variants={...})`: U3, C20,
C21 carry `vib`/`bare` -> DNP; SW1 and C22 are DNP in the base and `vib` -> populated. The
variant name set is whatever appears on the symbols; nothing is registered in the project file.

`make check|fab|jlcpcb BOARD=net/node` builds the **default** variant (VL53L0X). For the others,
until the jobset grows per-variant outputs (CLAUDE.md ideas list, item 9):

```sh
cd boards/net/node
kicad-cli sch export bom --variant vib --exclude-dnp --group-by 'Value,Description,Footprint,MPN,Manufacturer,LCSC' \
  --fields 'Reference,Value,Description,Footprint,MPN,Manufacturer,LCSC,${QUANTITY}' \
  --labels 'Refs,Value,Description,Footprint,MPN,Manufacturer,LCSC,Qty' -o out/node-bom-vib.csv node.kicad_sch
kicad-cli pcb export pos --variant vib --exclude-dnp --format csv --units mm --side both -o out/node-vib-pos.csv node.kicad_pcb
```

`${VARIANT}` in `-o` with several `--variant` flags writes one file per variant. Verified on
2026-09-16: `vib` lists SW1 and C22 and drops U3/C20/C21; `bare` lists neither set. Then
`python3 -m boardtools jlcpcb bom|pos` converts them exactly as `make jlcpcb` does.

## Parts and cost

Every BOM line has an MPN, Manufacturer and LCSC number, picked by exact-code lookups and
verified on 2026-09-24 with `make parts BOARD=net/node PARTS_ARGS='--boards 30'` and again on
2026-09-25 after the corner LEDs (25 lines, 0 errors, 0 warnings; 11 basic, 1 preferred, 10
extended parts, so 10 extended-part loading fees per order: U5 and D5 are new, D1 1N4148W went).
New parts, exact-code lookups 2026-09-25: SN74AHCT1G125DBVR C7484 (TI, extended, ~50k stock),
SMF5.0A C193402 (MDD, extended, ~580k), B5819W SL C8598 (CJ, basic), 1 k C21190 (basic), 100 nF
0402 C307331 (basic), WS2812B-2020-V6 C52917434 (extended, ~808k). The table lives in `generate/schematic.py`
(`PASSIVES` keyed by kind and value, plus per-symbol fields). Passives: UNI-ROYAL 0603WAF 1 % resistors (1 k C21190, 10 k
C25804, 4k7 C23162, 100 R C22775, 27 R C25190); 100 nF Yageo CC0603KRX7R9BB104 X7R 50 V
(C14663, also C22 in `vib`), 1 uF Samsung CL10A105KB8NNNC X5R 50 V (C15849), 10 uF
CL10A106MA8NRNC X5R 25 V (C96446), 4.7 uF CL10A475KO8NNNC X5R 16 V (C19666), 15 pF
CL10C150JB8NNNC C0G 50 V (C1644); the four 0402 caps at U1 pins 43..45 come from
`PASSIVES_0402` (see Decisions). As with the other boards, `Description` carries the real
ratings into the JLCPCB Comment column (and groups the BOM, so it is the same per value).

- **Crystal change.** Y1 was C9002 (YXC X322512MSB4SI), but JLCPCB lists it as a 20 pF-load,
  80 ohm ESR crystal, so the old "10 pF load" description was wrong and 27 pF caps were chosen
  for the wrong part. Y1 is now the crystal the RP2040 hardware design guide uses, Abracon
  ABM8-272-T3 (C20625731: 12 MHz, 10 pF load, 50 ohm ESR, 3225-4P), with the guide's 15 pF
  loads (15 pF in series pair plus ~3 pF stray is about 10 pF). Its pinout (1 and 3 crystal,
  2 and 4 GND, 1 and 3 diagonal) matches `Device:Crystal_GND24` and the existing footprint,
  so the layout is unchanged.
- **THT parts (J1..J4, and SW1 in `vib`).** All have LCSC numbers. Since 2026-09-25 they are out of
  the position file (hand-soldered, see Decisions), so `make jlcpcb` gives a CPL without them and a
  BOM that still lists them: the JLCPCB order page shows the J lines as parts without placements;
  leave them unselected and solder them by hand (or ask for hand-fitting, about $0.0164 per joint
  plus $3.58 per order, about $19 for 30 boards including the loading fees).

Rough per-node parts cost at 50 to 100 pieces: about $1.50 for the RP2040, flash, crystal and
LDO; about $0.85 for connectors, the four LEDs, U5, D5, D6 and passives; the VL53L0X adds about $1.50, the
spring switch a few cents. Add PCB (48 mm square, 4-layer, roughly $1 more than 2-layer at
JLCPCB) and assembly (the RP2040 and the
VL53L0X are reflow-only; everything THT is hand-solderable). The ToF variant is the expensive
one; the `bare` variant (no sensor) is the cheapest node, and a net only needs sensors on
some of its nodes.
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
  source, or colours can encode direction. With the four corner LEDs a node shows the wave
  crossing it: light the corners nearest the arriving port first.
- **LEDs:** one WS2812 chain of 4 pixels on GPIO4 (PIO, 800 kHz GRB), through U5 at 5 V. Pixel index
  -> corner: **0 = NE (D1), 1 = NW (D2), 2 = SW (D3), 3 = SE (D4)** (quadrant order, counter-clockwise
  from NE). Link ports map onto them: N = pixels 0 + 1, W = 1 + 2, S = 2 + 3, E = 3 + 0. Cap the
  total brightness in firmware (see first batch) rather than relying on the supply.
- **Sensor mapping:** VL53L0X distance -> initial level (closer = higher); switch -> fixed
  level pulse; `bare` nodes only relay.
- **Global commands:** flood with a hop count (colour, reset, brightness). A host can attach via
  a node on the jig's USB (the ESP32-on-J5 route went with J5; a WiFi variant is rev B).
- **Piezo:** PWM slice 1, GPIO18 = channel A (BUZZ_A), GPIO19 = channel B (BUZZ_B); same TOP for
  both, B output inverted (`pwm_set_output_polarity(1, false, true)`) and both at 50 % gives the
  antiphase 6.6 Vpp drive (+-3.3 V0-p, within Murata's +-12.5 V0-p maximum; the 65 dB rating is
  at +-1.5 V0-p); TOP sets the pitch (4 kHz resonance). **Never drive one pin with the other held
  low**: that puts a DC average across the element, and Murata prohibits DC on piezo sounders
  (removed 2026-09-25). Quieter, still balanced: phase-correct PWM, A at duty d, B inverted at duty
  1 - d, which gives two equal pulses of width d half a period apart (zero mean; the fundamental
  scales with sin(pi d), d = 50 % is full antiphase); or drive off resonance (e.g. 2 kHz), or burst
  it. Idle both low.
- **Later:** UART bootloader over the links so a programmed node can flash its neighbours.

## Decisions for the first batch (2026-09-19)

- **Net size: 5 x 5, 25 nodes.** Order 30 boards (5 spares). A 5 x 5 grid has 40 links, so
  order about 50 XH cables plus a few to cut into power tails.
- **LED power class: WS2812B-2020 stays**, now four per node (2026-09-25); a 1 W emitter means
  a 12/24 V bus and a driver per node, which is rev B. Budget per node from +5V: RP2040 30..50 mA
  and VL53L0X about 20 mA (both through the LDO), U5 and the idle LEDs negligible, the four LEDs
  4 x 36 mA = 144 mA at full white: about **215 mA per node** at full white (1.1 W), 70 mA dark.
  Net of 25: about **5.4 A** at full white everywhere, 1.8 A dark. That exceeds the 5 A supply
  below, so either use a **5 V 8 A (40 W)** supply or cap the global LED brightness in firmware at
  about 60 % (a wave rarely lights every corner of every node at once; 60 % keeps the worst case
  under 4 A). Set the supply to 5.0..5.1 V, not higher: the LEDs now see the rail directly and are
  rated to 5.3 V.
- **5 V injection: one tail per row**, into the free W connector at the grid edge, from a 5 V
  5 A supply. A single corner injection would push the full net current through one XH contact
  (rated 3 A) and drop several hundred mV over the first hops; per row the worst chain carries
  four nodes and drops about 0.1 V on 30 cm 26 AWG cables (with four LEDs per node the first
  node of a row carries 4 x 215 mA = 0.86 A through its ring, 0.8 mm B.Cu, fine; a row tail
  carries about 1.1 A, well inside the XH contact's 3 A). Any edge connector works as a tail,
  so no board change. Put a few hundred uF across each tail (hot-plug damping, see protection).
- **Cable: JST-XH keyed 3-pin**, pre-made double-ended, one length for the whole net. 20 cm gives
  a net about 0.8 m square, 30 cm about 1.2 m; pick from where it will hang.
- **Sensor: one assembled build, the default (VL53L0X) variant.** `vib` is a default board plus a
  hand-soldered SW1 (THT) and C22 (0603). A second assembly order for `bare` only pays past roughly 20 to 30 nodes
  of savings, so not for this batch.
- **Level scale:** corner to corner is 8 hops, so with one level lost per hop the excitation
  range must be well above 8 (use 0..255) or a corner touch never reaches the far corner.
- **Outdoor use** stays deferred: series R + TVS on each link, sealed connectors and a coating
  before any bush deployment that sees weather.
- **LCSC numbers.** Every fitted part has one, picked and verified 2026-09-24 with
  `make parts` (see Parts and cost); the order-page preview is still the final check for
  orientation.

## PCB (rev A, routed)

`generate/pcb.py` -> `node.kicad_pcb`, 48 x 48 mm, **4 copper layers**: F.Cu escapes and short
runs, In1.Cu GND plane, In2.Cu +3V3 plane, B.Cu GND pour plus the 5 V ring and the long signal
runs. Why four: with 0.2 mm track / 0.2 mm clearance / 0.6 mm vias a via needs 0.6 mm from any
neighbouring track centre, so at the RP2040's 0.4 mm pitch only a pin whose neighbours are
unrouted can via out; on two layers the QSPI group and the power/USB group on the same edge
fight for the same space, and every IOVDD/DVDD pin still needs a cap and a ground return.
JLCPCB 4-layer adds roughly $1 per board at this size.

Floorplan (board-local mm, origin top-left, y down; the rule is in Decisions). J1..J4 are
unchanged: side entry, one per edge, mouth 1.1 mm past the edge, pin row 8.1 mm in, pin 2 on the
edge's centre line (J1 N rot 180, pins 1/2/3 at x 26.5/24/21.5; J2 E rot 90, y 26.5/24/21.5;
J3 S rot 0, x 21.5/24/26.5; J4 W rot 270, y 21.5/24/26.5); each housing's courtyard reaches
10.9 mm in, so the centre square is 10.9..37.1. M2 holes 3.5 mm in from each corner, each with
the old 3.2 mm track keepout plus the 3.7 mm washer annulus.

- **Centre.** U1 rot 180 at (24, 24): GPIO0..11 on its east edge, crystal / SWD / RUN /
  IOVDD 22 / DVDD 23 north, QSPI / USB / core supply south, IOVDD 33 / 42 west. Caps: C5
  (IOVDD 22) and C14 (DVDD 23) just north of their pins, C6 / C7 (33 / 42) west, C4 (IOVDD 10)
  east, C3 (IOVDD 1) below the SE corner, the 0402 C10 / C11 (ADC_AVDD / VREG_VIN) and C13 / C15
  (VREG_VOUT / DVDD) at the SW corner, C9 + C8 (USB_VDD 48 + IOVDD 49, joined) below pins 48/49.
  Crystal NE of the north edge: Y1 rot 90 at (26.75, 15.9); XIN 45 deg up-right, under Y1's SW
  (GND) pad along y 17.9 and up into its SE pad, on to C1 (30.0, 18.0); XOUT 45 deg up-right
  beside XIN, then north on x 24.975 into R1 (25.8, 13.0); node R1 -> Y1's NW pad and C2
  (28.05, 12.4, vertical); nothing but GND under or around Y1 / C1 / C2 / R1 (F.Cu guard pour,
  see crystal isolation). Flash U2 rot 180 at (34.6, 33.5) SE of U1, C16 at its VCC pin. LDO U4
  NW at (15.5, 13.5) with C17 / C18 / C12, TVS D5 at (10.4, 17.3) on its 5 V feed from J4.1. LED
  buffer U5 rot 90 at (35.3, 7.0) in the N strip east of J1 (the old D1 spot), C26 beside its VCC
  pin; the old LEDs' spot NE of the crystal is empty.
  R15 / R16 (USB 27 R) at (20.2, 32.0 / 33.5). Link resistors: R7 / R8 NE of J1 at (31.2, 11.1 /
  9.05), R9 / R10 in the pocket east of U1 at (34.4, 26.8 / 28.3), R11 / R12 above J3 at
  (23.0 / 24.6, 35.6), R13 / R14 by J4 at (13.2, 24.0) / (16.1, 26.0). R2 (RUN) hangs under the
  RUN row, R3 (QSPI_SS) is below the flash, R19 (BOOT 1 k) at (40.4, 37.6) just below the flash's
  pin 1 at the end of the SS track.
- **Corners.** NE: BZ1 rot 0 at (42.5, 12.0), R17 / R18 below it (R17 west to BZ1.1, R18 east to BZ1.2). SE: U3 rot 180 at
  (43.8, 33.8) just below J2 (its housing ends 4.4 mm north of the sensor, well outside the
  25 deg field of view), C20 east and C21 (horizontal since 2026-09-25, at (44.2, 36.3)) south of it,
  the I2C pull-ups R4 / R5 between it and J2. SW: J6 pogo pads at (12.4, 35.9) rot 90, centred in the
  corner (see Programming jig), D6 at (15.4, 43.0) below it. NW: SW1 at (11.0, 7.5) with C22 and R6
  (SENS_INT pull-up) on its INT run.
- **Corner LEDs.** D1 NE (39.2, 4.0) rot 0, D2 NW (4.0, 8.8) rot 90, D3 SW (8.8, 44.0) rot 180, D4 SE
  (44.0, 39.2) rot 270: one NW layout rotated a quarter turn per corner (see Decisions). Per corner
  (NW frame): cap at (2.2, 8.365) with its +5V pad level with the LED's VDD pad (1.25 mm of track),
  VDD via at (2.8, 7.5) onto the ring's notch, cap GND via at (2.45, 9.75), LED GND via 0.8 mm east
  of the GND pad; DOUT leaves along the lane.

Routing plan, in the order pcb.py writes it (one function per block):

- **North.** Four GND vias in the exposed pad; TESTEN (19) runs inward onto it. NW fan: 26 / 25 /
  24 bend at y 19.9 / 19.7 / 19.5 onto rows 19.7 / 19.05 / 18.4 (RUN / SWDIO / SWCLK) and run west
  to staggered vias at x 11.4 / 10.0 / 10.7; 23 fans NW into C14 (DVDD via to B.Cu), 22 goes
  north into C5 (3V3 plane via between C5 and C14). Crystal as above.
- **Piezo.** BUZZ_A / B (29 / 30, U1's NW corner) drop through vias just west of the pins (between
  R2 and C6), run east under U1's body on B.Cu (y 21.8 / 22.4, north of the exposed-pad vias) and
  NE under the SCL / SDA rows, surface at (30.4, 19.6) / (31.2, 20.2) east of C1 and run east on
  F.Cu (y 19.6 / 20.2) to R17 / R18. GPIO -> R track 21.6 / 24.8 mm (was 15.9 / 13.0).
- **South.** 43+44 joined, west to C11 / C10 and C7's plane via; 45 into C13 / C15 and the DVDD
  via; 46 / 47 straight down to R15 / R16; 48+49 down x 23.6 into C9 and on to C8 (own 3V3 and GND
  vias); 50 to a DVDD via. QSPI fans SE (56 bends first): SD0 / SCLK / SD3 straight into the
  flash's west column, SS / SD1 / SD2 over its top and down its east side (x 39.6 .. 40.8).
- **East.** IOVDD 10 -> plane via -> C4. SCL / SDA (top) and INT / XSHUT (below C4) run east as
  a 0.65 mm bundle (y 20.8 .. 22.75), turn south at x 36.6 .. 38.55 into four vias, and one short
  B.Cu hop (rows y 28.6 .. 30.55) takes them under the QSPI columns to U3 and its pull-ups.
  LED_DIN and the links spread SE onto rows 25.1 .. 27.7 (0.65 mm; every row passing a via clears
  it by 0.65 mm): LW / LS / LED_DIN / LN end in staggered vias, LE runs through R9 (R10 pull-up)
  to a via and on B.Cu to J2.2. IOVDD 1 drops into C3.
- **LEDs** (`route_leds`). U5: VCC via onto a B.Cu stub north to the ring, C26 beside it, /OE into
  C26's GND, its GND pad to a via; Y east along y 6.4 under D1's GND via and up into D1's DIN. The
  chain is one NW-frame path (D2 DOUT down x 3.45 to y 38.5, 45 deg past H3 into D3 DIN) rotated
  onto the N (D1 -> D2), W (D2 -> D3) and S (D3 -> D4) edges: F.Cu, 3.45 mm in, inside the B.Cu
  ring, under the J1 / J4 / J3 housings (clear of their pins), >= 4.2 mm from each hole centre.
- **West and south-west.** LINK_W on B.Cu under U1 (y 25.75), up at (19.55, 25.2), F.Cu west
  past R14 to R13 and J4.2. DVDD from C14's via down x 18.8 on B.Cu to the C13 / C15 via and on to
  pin 50's via. SWD lanes on B.Cu at x 10.0 / 10.7 / 11.4 (under J4's housing) to vias 2.025 mm
  north of the J6 even-row pad centres (0.15 mm off the pad edge, short F.Cu stub in; until
  2026-09-25 they were inside the pads). USB: DM / DP run 0.6 mm apart from the resistors,
  down just east of J6.8 and west along the 1.9 mm gap between the pad rows, each dropping into
  its odd-row pad J6.1 / J6.3 (pin -> R -> pad 22.0 / 19.8 mm). LINK_S on B.Cu under U1 and
  down x 25.0 to R11 / R12, R11 -> J3.2 on F.Cu. QSPI_SS from a via on the SS row down x 32.0 on
  B.Cu to R3 (pull-up). BOOT from R19 (below the flash's pin 1) through a via, west on B.Cu along
  y 38.3 (north of J3's pins), up x 17.2 to a via just north of J6.8. J6.5's GND via sits below
  its pad, D6 takes J6.7 (USB 5 V) round to its anode, its cathode drops to the ring.
- **North-east.** LINK_N on B.Cu up x 31.9 to R7 / R8, R7 -> J1.2 along y 9.9 north of C2.
  LED_DATA on B.Cu up x 35.3, surfacing at (35.3, 13.5) and on F.Cu straight up into U5's A pin
  (crossing SENS_INT's B.Cu row). SENS_INT
  leaves the bundle through a via, runs up x 36.2 and west along y 10.4 on B.Cu (under J1, 1.8 mm
  north of the crystal cluster) to SW1.2, then on F.Cu to C22 and R6.
- **5 V ring** on B.Cu, 0.8 mm at inset 1.5 mm, square notches around all four M2 keepouts, now
  **closed** (the NW corner only holds SW1, so the old open corner and its two `track_dangling`
  warnings are gone). J1.1 .. J4.1 feed it on 0.4 mm B.Cu stubs, J6.7 through D6 and a via; the four LED VDD
  vias and U5's VCC stub tap it; widths are
  unchanged, so the row chain of Decisions for the first batch (at most about 0.8 A through a
  node) is carried as before. The LDO takes 5 V from J4.1 on F.Cu up the west edge.
- Every cap has its own vias except where noted (C10 / C11 share a GND via, C9 / C8 are tied, C13's
  GND goes to C15's via); U1's exposed pad has four.

Decoupling, routed pin-to-cap length (loop script: pin pad to cap supply pad along the copper,
then cap GND pad to its nearest via), before -> after the re-placement: C3 (IOVDD 1) plane cap
-> 3.3 mm; C4 (10) 1.5 -> 1.5; C5 (22) plane cap -> 3.2; C6 / C7 (33 / 42) 1.4 -> 1.4; C8 (49)
plane cap -> 5.4; C9 (48) 4.0 -> 3.8; C10 / C11 (43 / 44) 2.8 / 2.9 -> 3.5 / 2.9; C13 (45)
1.4 -> 1.4; C14 (23) 6.6 -> 3.9; C15 (50, through pin 45) 6.4 -> 6.3; C16 (flash) plane cap ->
1.9; C17 / C18 (LDO) 3.8 / 3.9 -> 4.1 / 1.9; C20 / C21 (U3) 1.7 / 1.7 -> 3.3 / 1.4; GND pad to
via 0.8 .. 1.8 mm (C20 2.6, through C21's via). Corner LEDs (2026-09-25, same for all four by symmetry): LED VDD
pad -> cap +5V pad 1.25 mm, cap GND pad -> via 0.94 mm, LED GND pad -> via 0.8 mm, the two GND vias
2.9 mm apart on In1 (the old single-LED loop through C19 was 8.7 mm); U5 VCC -> C26 1.35 mm, C26 GND
-> via 0.75 mm, U5 GND -> via 1.07 mm. Crystal copper (XIN + XOUT + node) 23.3 ->
16.2 mm (18.2 mm after the 2026-09-25 isolation pass: XIN 5.8 -> 6.7, XOUT 7.1 -> 7.5, node 3.3 -> 4.0); USB (pin -> R -> pad) DM 26.2 -> 23.6 mm, DP 26.7 -> 23.1 mm.

Last step of every regeneration: `kicad-cli pcb drc --refill-zones --save-board` so the
committed board carries the zone fills.

## Resume path

1. Re-read this file, `generate/README.md` and the CLAUDE.md sections on generating KiCad files
   (the 0.4 mm-pitch escape rules, the flatpak KiCad setup and the session-bounding rules are
   recorded there). `generate/sch-1.png` is the rendered sheet. Regenerate the schematic only if
   the design changes; regeneration replaces every UUID. Regenerate the PCB with the commands in
   `generate/README.md` (`pcb.py --place` writes placement only, for courtyard passes), then
   `make check BOARD=net/node`. Helper scripts that make a routing pass cheap (regenerate + DRC
   with board-mm locations, courtyard check, pad-box dump, decoupling-loop and net-length
   measurement) are described in CLAUDE.md; they lived in the session scratchpad and are not
   committed.
2. Known compromises, deliberately left: DVDD pin 50 has no cap of its own (C13 1 uF and C15
   100 nF sit at pin 45; pin 50 reaches them through a via and about 4 mm of B.Cu, as before;
   pins 48..51 leave no room for a pad and a via at pin 50); C8 (IOVDD 49) shares 48/49's
   joined pads with C9 and sits beside it; U3 sits just below J2 rather than deep in the
   SE corner, because the QSPI columns and the ring notch take the corner itself; the SWD lanes and
   SENS_INT run under link housings on B.Cu; the LED chain lanes run on F.Cu under the J1 / J4 /
   J3 housings; the SE LED is 5.4 mm from U3 (check ranging with D4 lit); D5 cannot hold the LDO
   under its 6.5 V maximum on a hard ring (damp at the power tails). All fine for a proof of
   concept at full-speed USB and 12 MHz.
3. **Review the new layout** (not yet done): a reproduction-based Codex round on the floorplan,
   the hole-clearance enforcement (annulus plus assertion), the J5 removal and the 2026-09-25
   changes (corner LEDs and their chain, U5 in place of D1, D5 / D6 / R19, the J6 vias, the
   variant pos-file carry-over in `pcbgen`), as for the earlier layouts. Order the boards **unpanelised** (economic PCBA, 48 x 48 needs no rails): the
   housings overhang 1.1 mm, so a JLCPCB panel would need > 2.2 mm between boards plus tolerance,
   not the default 2 mm.
4. Review the layout in the GUI once (silkscreen, the 1.1 mm connector overhang, U3's clearance
   to J2's housing, the corner LEDs' orientation marks). Silk is minimal: connector refs sit inside the
   housings, U1 / U3 and the passives have no silk reference.
5. `make jlcpcb BOARD=net/node`, order (see Decisions for the first batch), check the four LEDs'
   and U5's orientation in the JLCPCB preview; J1..J4 are not in the CPL (hand-soldered, leave their
   BOM lines unselected; every housing mouth must face out). Cables:
   JST-XH 3-pin pre-made, one length; XH has no strain relief, so a bush deployment needs a
   printed clip or tie.
6. Pogo jig (see Programming jig for the pad coordinates), USB bring-up, link protocol, piezo
   driver (PWM/PIO, balanced antiphase only), 4-pixel LED driver, UART bootloader; then rev B (LED power, bus voltage, maybe a
   sensor header on an edge).

`generate/` holds the scripts that produced the schematic and the board (see its README).

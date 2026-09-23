# KiCad board tooling. A board is any directory under boards/ holding <leaf>.kicad_{pro,sch,pcb}
# named after that directory, at any depth: boards/blinky/ or boards/chromatone/isolator/.
# The board id is the path relative to boards/ (e.g. chromatone/isolator).
# Exports are defined once in jobsets/fab.kicad_jobset (runs from the KiCad GUI too) and land
# in <board dir>/out/ (git-ignored).
#
#   make new NAME=id         scaffold boards/<id> from templates/board
#   make check  [BOARD=id]   off-grid lint + ERC + DRC (all boards, or one); STRICT=1 also fails on warnings
#   make fab    [BOARD=id]   check, then run the fab jobset -> boards/<id>/out/ (+ <leaf>-gerbers.zip)
#   make export [BOARD=id]   the jobset without the Makefile checks
#   make jlcpcb [BOARD=id]   fab, then JLCPCB-format BOM/CPL -> boards/<id>/out/jlcpcb/
#   make parts  [BOARD=id]   check the fab BOM's LCSC numbers/stock at JLCPCB (after make fab;
#                            network, manual pre-order check, not CI; PARTS_ARGS='--boards 10')
#   make route  BOARD=id     Freerouting autoroute (Docker) -> boards/<id>/out/route/, then DRC it
#   make test                boardtools unit tests
#   make smoke               scaffold throwaway boards in a temp dir and run the whole pipeline
#   make list                boards found under boards/
#   make clean               remove every boards/**/out/

KICAD_CLI ?= kicad-cli
PYTHON    ?= python3
STRICT    ?= 0
JOBSET    ?= jobsets/fab.kicad_jobset
PARTS_ARGS ?=
ROUTE_ARGS ?=

# boards/<id>/<leaf>.kicad_pro where leaf = last path component of <id>
PRO_FILES  := $(shell find boards -name '*.kicad_pro' 2>/dev/null | sort)
ALL_BOARDS := $(foreach p,$(PRO_FILES),$(if $(filter $(notdir $(patsubst %/,%,$(dir $(p)))).kicad_pro,$(notdir $(p))),$(patsubst boards/%/,%,$(dir $(p)))))
BOARDS     := $(if $(BOARD),$(BOARD),$(ALL_BOARDS))

SEVERITY := --severity-error $(if $(filter 1,$(STRICT)),--severity-warning)

.PHONY: help list new check erc drc fab export jlcpcb parts route test smoke clean
# Per-board targets (erc/<id>, fab/<id>, ...) are pattern rules and must NOT be .PHONY:
# make skips implicit-rule search for phony targets. The pattern contains a slash so the
# stem may contain slashes (nested board ids).

help:
	@sed -n '2,18p' $(MAKEFILE_LIST) | sed 's/^# \{0,1\}//'

list:
	@printf '%s\n' $(ALL_BOARDS)

new:
	@test -n "$(NAME)" || { echo 'usage: make new NAME=<id>  (e.g. blinky or chromatone/isolator)' >&2; exit 2; }
	@$(PYTHON) scripts/new-board.py "$(NAME)"

test:
	$(PYTHON) -m unittest discover -s boardtools/tests -t .

smoke:
	@scripts/smoke.sh

check:  $(addprefix check/,$(BOARDS))
erc:    $(addprefix erc/,$(BOARDS))
drc:    $(addprefix drc/,$(BOARDS))
fab:    $(addprefix fab/,$(BOARDS))
export: $(addprefix export/,$(BOARDS))
jlcpcb: $(addprefix jlcpcb/,$(BOARDS))
parts:  $(addprefix parts/,$(BOARDS))

check/%: erc/% drc/% ;

# fab = purge stale outputs, check, export. Recursive makes keep the order strict even
# under -j, and purging first means a failed check never leaves an old zip looking current.
fab/%:
	@rm -rf $(out)
	@$(MAKE) --no-print-directory check/$*
	@$(MAKE) --no-print-directory export/$*

# --- per-board rules --------------------------------------------------------
# $* is the board id; leaf is its last component; sources are boards/$*/<leaf>.kicad_{pro,sch,pcb}.
leaf = $(notdir $*)
dir  = boards/$*
pro  = $(dir)/$(leaf).kicad_pro
sch  = $(dir)/$(leaf).kicad_sch
pcb  = $(dir)/$(leaf).kicad_pcb
out  = $(dir)/out

# erc.rpt / drc.rpt hold the gating violations; *-warnings.rpt always lists warnings
# so they stay visible even when they do not fail the build. offgrid.rpt gates on
# off-grid connection points, which ERC only warns about (endpoint_off_grid) and
# reports once per symbol; the lint names every offending pin, wire end and label
# (child sheets included). Lint and ERC both always run, so every report is fresh,
# and the target fails if either failed.
erc/%:
	@test -f $(pro) || { echo "no board at $(dir) (expected $(pro))" >&2; exit 2; }
	@mkdir -p $(out)
	$(KICAD_CLI) sch erc --severity-warning -o $(out)/erc-warnings.rpt $(sch) >/dev/null
	@lint=0; $(PYTHON) -m boardtools offgrid $(sch) >$(out)/offgrid.rpt 2>&1 || { lint=1; cat $(out)/offgrid.rpt; }; \
	echo '$(KICAD_CLI) sch erc $(SEVERITY) --exit-code-violations -o $(out)/erc.rpt $(sch)'; \
	$(KICAD_CLI) sch erc $(SEVERITY) --exit-code-violations -o $(out)/erc.rpt $(sch); erc=$$?; \
	[ $$lint -eq 0 ] || echo "$*: off-grid connection points (see $(out)/offgrid.rpt)" >&2; \
	[ $$lint -eq 0 ] && [ $$erc -eq 0 ]

drc/%:
	@test -f $(pro) || { echo "no board at $(dir) (expected $(pro))" >&2; exit 2; }
	@mkdir -p $(out)
	$(KICAD_CLI) pcb drc --severity-warning --schematic-parity --refill-zones -o $(out)/drc-warnings.rpt $(pcb) >/dev/null
	$(KICAD_CLI) pcb drc $(SEVERITY) --exit-code-violations --schematic-parity --refill-zones -o $(out)/drc.rpt $(pcb)

# The jobset writes to ${KIPRJMOD}/out/ (see jobsets/fab.kicad_jobset), i.e. $(out).
# Stale jobset files are removed first (keeping the Makefile's *.rpt check reports).
export/%:
	@test -f $(pro) || { echo "no board at $(dir) (expected $(pro))" >&2; exit 2; }
	@mkdir -p $(out) && find $(out) -mindepth 1 -maxdepth 1 ! -name '*.rpt' -exec rm -rf {} +
	@$(KICAD_CLI) jobset run --stop-on-error --file $(JOBSET) $(pro) >$(out)/jobset.log 2>&1 \
	  || { cat $(out)/jobset.log; echo "jobset failed for $*" >&2; exit 1; }
	@grep -E 'jobs? succeeded' $(out)/jobset.log | sed 's/\x1b\[[0-9;]*m//g; s|^|$*: |'
	@test -s $(out)/$(leaf)-gerbers.zip || { echo "jobset produced no $(out)/$(leaf)-gerbers.zip" >&2; exit 1; }

jlcpcb/%: fab/%
	@mkdir -p $(out)/jlcpcb
	$(PYTHON) -m boardtools jlcpcb pos $(out)/$(leaf)-all-pos.csv $(out)/jlcpcb/$(leaf)-cpl.csv
	$(PYTHON) -m boardtools jlcpcb bom $(out)/$(leaf)-bom.csv $(out)/jlcpcb/$(leaf)-bom.csv

# A manual pre-order check, not a gate (it needs the network). It reads the BOM that fab
# or export left in $(out) rather than exporting one: a separate BOM-only jobset
# destination would write a BOM even when the full run's ERC/DRC failed, and gating it
# inside the jobset costs ~20 s of ERC+DRC per check. fab/export purge first and write no
# BOM when a check fails, so a BOM newer than all its inputs is current and passed.
# Inputs: every .kicad_sch under the board dir (sub-sheets), every .kicad_pro (text
# variables such as ${ORDER_PART} live there), and the jobset (fields, grouping). Symbol
# libraries and sym-lib-table are not inputs: the export uses the symbols embedded in the
# schematic (verified: identical BOM with every library removed).
bom = $(out)/$(leaf)-bom.csv
parts/%:
	@test -f $(pro) && test -f $(sch) || { echo "no board at $(dir) (expected $(pro) and $(sch))" >&2; exit 2; }
	@test -f $(bom) || { echo "no $(bom); run make fab BOARD=$* first" >&2; exit 2; }
	@test -f $(JOBSET) || { echo "no jobset at $(JOBSET)" >&2; exit 2; }
	@newer=$$(find $(dir) $(JOBSET) -path $(out) -prune -o -type f \( -name '*.kicad_sch' -o -name '*.kicad_pro' \
	    -o -name '*.kicad_jobset' \) -newer $(bom) -print) || { echo "cannot scan the inputs of $(bom)" >&2; exit 2; }; \
	  test -z "$$newer" || { echo "$(bom) is stale (changed since: $$(echo $$newer)); run make fab BOARD=$* first" >&2; exit 2; }
	@echo "== $*"
	@$(PYTHON) -m boardtools parts $(bom) $(if $(filter 1,$(STRICT)),--strict) $(PARTS_ARGS)

# Autorouting writes a NEW board (source untouched) and DRCs it; see scripts/route.py.
# ROUTE_ARGS=--strip reroutes from scratch; PASSES=n caps Freerouting passes (default 100).
route:
	@test -n "$(BOARD)" || { echo 'usage: make route BOARD=<id> [ROUTE_ARGS=--strip]' >&2; exit 2; }
	@$(MAKE) --no-print-directory route/$(BOARD)

route/%:
	@test -f $(pro) || { echo "no board at $(dir) (expected $(pro))" >&2; exit 2; }
	@# DRC below checks $(out)/route, so --default-outdir makes route.py refuse any -o in ROUTE_ARGS.
	$(PYTHON) scripts/route.py --default-outdir $(ROUTE_ARGS) $(pcb)
	$(KICAD_CLI) pcb drc $(SEVERITY) --exit-code-violations --schematic-parity --refill-zones --save-board \
	  -o $(out)/route/drc.rpt $(out)/route/$(leaf).kicad_pcb

clean:
	find boards -type d -name out -prune -exec rm -rf {} +

# KiCad board tooling. Every board lives in boards/<name>/<name>.kicad_{pro,sch,pcb}.
#
#   make new NAME=foo        scaffold boards/foo from templates/board
#   make check [BOARD=foo]   ERC + DRC (all boards, or one)
#   make fab   [BOARD=foo]   check, then gerbers/drill/pos/BOM/PDF/STEP -> out/<name>/
#   make export [BOARD=foo]  the fab exports without the checks
#   make smoke               scaffold a throwaway board in a temp dir and run check + fab on it
#   make list                boards found under boards/
#   make clean               remove out/
#
# STRICT=1 also fails on warnings (default: fail on errors only).

KICAD_CLI ?= kicad-cli
OUT       ?= out
STRICT    ?= 0

ALL_BOARDS := $(sort $(notdir $(patsubst %/,%,$(dir $(wildcard boards/*/*.kicad_pro)))))
BOARDS     := $(if $(BOARD),$(BOARD),$(ALL_BOARDS))

SEVERITY := --severity-error $(if $(filter 1,$(STRICT)),--severity-warning)

.PHONY: help list new check erc drc fab export gerbers drill pos bom pdf step smoke clean
# Per-board targets (erc-foo, fab-foo, ...) are pattern rules and must NOT be .PHONY:
# make skips implicit-rule search for phony targets.

help:
	@sed -n '2,12p' $(MAKEFILE_LIST) | sed 's/^# \{0,1\}//'

list:
	@printf '%s\n' $(ALL_BOARDS)

new:
	@test -n "$(NAME)" || { echo 'usage: make new NAME=<board>' >&2; exit 2; }
	@python3 scripts/new-board.py "$(NAME)"

smoke:
	@scripts/smoke.sh

check:   $(addprefix check-,$(BOARDS))
erc:     $(addprefix erc-,$(BOARDS))
drc:     $(addprefix drc-,$(BOARDS))
fab:     $(addprefix fab-,$(BOARDS))
export:  $(addprefix export-,$(BOARDS))
gerbers: $(addprefix gerbers-,$(BOARDS))
drill:   $(addprefix drill-,$(BOARDS))
pos:     $(addprefix pos-,$(BOARDS))
bom:     $(addprefix bom-,$(BOARDS))
pdf:     $(addprefix pdf-,$(BOARDS))
step:    $(addprefix step-,$(BOARDS))

check-%: erc-% drc-% ;

# fab = check, then export. The recursive make keeps the order strict even under -j.
fab-%: check-%
	@$(MAKE) --no-print-directory export-$*

export-%: gerbers-% drill-% pos-% bom-% pdf-% step-%
	@cd $(OUT)/$* && rm -f $*-gerbers.zip \
	  && zip -q -j $*-gerbers.zip gerbers/* drill/*.drl \
	  && echo "wrote $(OUT)/$*/$*-gerbers.zip"

# --- per-board rules --------------------------------------------------------
# $* is the board name; sources are boards/$*/$*.kicad_sch and .kicad_pcb.
sch = boards/$*/$*.kicad_sch
pcb = boards/$*/$*.kicad_pcb
out = $(OUT)/$*

# erc.rpt / drc.rpt hold the gating violations; *-warnings.rpt always lists warnings
# so they stay visible even when they do not fail the build.
erc-%:
	@mkdir -p $(out)
	$(KICAD_CLI) sch erc --severity-warning -o $(out)/erc-warnings.rpt $(sch) >/dev/null
	$(KICAD_CLI) sch erc $(SEVERITY) --exit-code-violations -o $(out)/erc.rpt $(sch)

drc-%:
	@mkdir -p $(out)
	$(KICAD_CLI) pcb drc --severity-warning --schematic-parity --refill-zones -o $(out)/drc-warnings.rpt $(pcb) >/dev/null
	$(KICAD_CLI) pcb drc $(SEVERITY) --exit-code-violations --schematic-parity --refill-zones -o $(out)/drc.rpt $(pcb)

# Copper layers come from the board's layer table (2..N layer stackups); the
# helper exits nonzero if it finds none, which aborts the recipe.
gerbers-%:
	@rm -rf $(out)/gerbers && mkdir -p $(out)/gerbers
	copper=$$(python3 scripts/copper_layers.py $(pcb)) && \
	$(KICAD_CLI) pcb export gerbers --no-x2 --subtract-soldermask --use-drill-file-origin --check-zones \
	  -l "$$copper,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
	  -o $(out)/gerbers/ $(pcb)

drill-%:
	@rm -rf $(out)/drill && mkdir -p $(out)/drill
	$(KICAD_CLI) pcb export drill --format excellon --drill-origin plot --excellon-separate-th \
	  --generate-map --map-format gerberx2 -o $(out)/drill/ $(pcb)

pos-%:
	@mkdir -p $(out)
	$(KICAD_CLI) pcb export pos --format csv --units mm --use-drill-file-origin --exclude-dnp \
	  -o $(out)/$*-pos.csv $(pcb)

bom-%:
	@mkdir -p $(out)
	$(KICAD_CLI) sch export bom --exclude-dnp --ref-range-delimiter '' \
	  --fields 'Reference,Value,Footprint,MPN,Manufacturer,LCSC,$${QUANTITY}' \
	  --labels 'Refs,Value,Footprint,MPN,Manufacturer,LCSC,Qty' \
	  --group-by 'Value,Footprint,MPN,LCSC' -o $(out)/$*-bom.csv $(sch)

pdf-%:
	@mkdir -p $(out)
	$(KICAD_CLI) sch export pdf --black-and-white -o $(out)/$*-schematic.pdf $(sch)

step-%:
	@mkdir -p $(out)
	$(KICAD_CLI) pcb export step --force --no-dnp --subst-models -o $(out)/$*.step $(pcb)

clean:
	rm -rf $(OUT)

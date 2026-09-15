# KiCad board tooling. Every board lives in boards/<name>/<name>.kicad_{pro,sch,pcb}.
#
#   make new NAME=foo        scaffold boards/foo from templates/board
#   make check [BOARD=foo]   ERC + DRC (all boards, or one)
#   make fab   [BOARD=foo]   gerbers, drill, pos, BOM, schematic PDF, STEP -> out/<name>/
#   make list                boards found under boards/
#   make clean               remove out/
#
# STRICT=1 also fails on warnings (default: fail on errors only).

KICAD_CLI ?= kicad-cli
OUT       ?= out
STRICT    ?= 0

ALL_BOARDS := $(sort $(notdir $(patsubst %/,%,$(dir $(wildcard boards/*/*.kicad_pro)))))
BOARDS     := $(if $(BOARD),$(BOARD),$(ALL_BOARDS))

SEVERITY := $(if $(filter 1,$(STRICT)),--severity-all,--severity-error)

.PHONY: help list new check erc drc fab gerbers drill pos bom pdf step clean
# Per-board targets (erc-foo, fab-foo, ...) are pattern rules and must NOT be .PHONY:
# make skips implicit-rule search for phony targets.

help:
	@sed -n '2,10p' $(MAKEFILE_LIST) | sed 's/^# \{0,1\}//'

list:
	@printf '%s\n' $(ALL_BOARDS)

new:
	@test -n "$(NAME)" || { echo 'usage: make new NAME=<board>' >&2; exit 2; }
	@python3 scripts/new-board.py "$(NAME)"

check:   $(addprefix check-,$(BOARDS))
erc:     $(addprefix erc-,$(BOARDS))
drc:     $(addprefix drc-,$(BOARDS))
fab:     $(addprefix fab-,$(BOARDS))
gerbers: $(addprefix gerbers-,$(BOARDS))
drill:   $(addprefix drill-,$(BOARDS))
pos:     $(addprefix pos-,$(BOARDS))
bom:     $(addprefix bom-,$(BOARDS))
pdf:     $(addprefix pdf-,$(BOARDS))
step:    $(addprefix step-,$(BOARDS))

check-%: erc-% drc-% ;
fab-%: gerbers-% drill-% pos-% bom-% pdf-% step-%
	@cd $(OUT)/$* && rm -f $*-gerbers.zip && zip -q -j $*-gerbers.zip gerbers/* drill/* && echo "wrote $(OUT)/$*/$*-gerbers.zip"

# --- per-board rules --------------------------------------------------------
# $* is the board name; sources are boards/$*/$*.kicad_sch and .kicad_pcb.
sch = boards/$*/$*.kicad_sch
pcb = boards/$*/$*.kicad_pcb
out = $(OUT)/$*

erc-%:
	@mkdir -p $(out)
	$(KICAD_CLI) sch erc $(SEVERITY) --exit-code-violations -o $(out)/erc.rpt $(sch)

drc-%:
	@mkdir -p $(out)
	$(KICAD_CLI) pcb drc $(SEVERITY) --exit-code-violations --schematic-parity -o $(out)/drc.rpt $(pcb)

# Copper layers present in the board file (handles 2..N layer stackups) plus the usual fab layers.
copper_layers = $$(grep -oE '"(F|B|In[0-9]+)\.Cu"' $(pcb) | tr -d '"' | sort -u | paste -sd,)
gerbers-%:
	@rm -rf $(out)/gerbers && mkdir -p $(out)/gerbers
	$(KICAD_CLI) pcb export gerbers --no-x2 --subtract-soldermask --use-drill-file-origin \
	  -l "$(copper_layers),F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
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
	$(KICAD_CLI) sch export bom --exclude-dnp \
	  --fields 'Reference,Value,Footprint,MPN,Manufacturer,$${QUANTITY}' \
	  --labels 'Refs,Value,Footprint,MPN,Manufacturer,Qty' \
	  --group-by 'Value,Footprint,MPN' -o $(out)/$*-bom.csv $(sch)

pdf-%:
	@mkdir -p $(out)
	$(KICAD_CLI) sch export pdf --black-and-white -o $(out)/$*-schematic.pdf $(sch)

step-%:
	@mkdir -p $(out)
	$(KICAD_CLI) pcb export step --force --no-dnp --subst-models -o $(out)/$*.step $(pcb)

clean:
	rm -rf $(OUT)

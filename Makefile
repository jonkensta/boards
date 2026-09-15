# KiCad board tooling. Every board lives in boards/<name>/<name>.kicad_{pro,sch,pcb}.
# Exports are defined once in jobsets/fab.kicad_jobset (runs from the KiCad GUI too).
#
#   make new NAME=foo        scaffold boards/foo from templates/board
#   make check  [BOARD=foo]  ERC + DRC (all boards, or one); STRICT=1 also fails on warnings
#   make fab    [BOARD=foo]  check, then run the fab jobset -> out/<name>/ (+ <name>-gerbers.zip)
#   make export [BOARD=foo]  the jobset without the Makefile checks
#   make jlcpcb [BOARD=foo]  fab, then JLCPCB-format BOM/CPL -> out/<name>/jlcpcb/
#   make test                boardtools unit tests
#   make smoke               scaffold throwaway boards in a temp dir and run the whole pipeline
#   make list                boards found under boards/
#   make clean               remove out/

KICAD_CLI ?= kicad-cli
PYTHON    ?= python3
STRICT    ?= 0
# Output root is fixed to out/ because the jobset's destinations hardcode
# ${KIPRJMOD}/../../out/${PROJECTNAME}; change both together if you ever move it.
override OUT := out
JOBSET    ?= jobsets/fab.kicad_jobset

ALL_BOARDS := $(sort $(notdir $(patsubst %/,%,$(dir $(wildcard boards/*/*.kicad_pro)))))
BOARDS     := $(if $(BOARD),$(BOARD),$(ALL_BOARDS))

SEVERITY := --severity-error $(if $(filter 1,$(STRICT)),--severity-warning)

.PHONY: help list new check erc drc fab export jlcpcb test smoke clean
# Per-board targets (erc-foo, fab-foo, ...) are pattern rules and must NOT be .PHONY:
# make skips implicit-rule search for phony targets.

help:
	@sed -n '2,13p' $(MAKEFILE_LIST) | sed 's/^# \{0,1\}//'

list:
	@printf '%s\n' $(ALL_BOARDS)

new:
	@test -n "$(NAME)" || { echo 'usage: make new NAME=<board>' >&2; exit 2; }
	@$(PYTHON) scripts/new-board.py "$(NAME)"

test:
	$(PYTHON) -m unittest discover -s boardtools/tests -t .

smoke:
	@scripts/smoke.sh

check:  $(addprefix check-,$(BOARDS))
erc:    $(addprefix erc-,$(BOARDS))
drc:    $(addprefix drc-,$(BOARDS))
fab:    $(addprefix fab-,$(BOARDS))
export: $(addprefix export-,$(BOARDS))
jlcpcb: $(addprefix jlcpcb-,$(BOARDS))

check-%: erc-% drc-% ;

# fab = purge stale outputs, check, export. Recursive makes keep the order strict even
# under -j, and purging first means a failed check never leaves an old zip looking current.
fab-%:
	@rm -rf $(out)
	@$(MAKE) --no-print-directory check-$*
	@$(MAKE) --no-print-directory export-$*

# --- per-board rules --------------------------------------------------------
# $* is the board name; sources are boards/$*/$*.kicad_{pro,sch,pcb}.
pro = boards/$*/$*.kicad_pro
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

# The jobset writes to ${KIPRJMOD}/../../out/${PROJECTNAME}/ (see jobsets/fab.kicad_jobset),
# i.e. $(OUT)/$*. Stale jobset files are removed first (keeping the Makefile's *.rpt
# check reports) so the folder only holds what this run produced.
export-%:
	@mkdir -p $(out) && find $(out) -mindepth 1 -maxdepth 1 ! -name '*.rpt' -exec rm -rf {} +
	@$(KICAD_CLI) jobset run --stop-on-error --file $(JOBSET) $(pro) >$(out)/jobset.log 2>&1 \
	  || { cat $(out)/jobset.log; echo "jobset failed for $*" >&2; exit 1; }
	@grep -E 'jobs? succeeded' $(out)/jobset.log | sed 's/\x1b\[[0-9;]*m//g; s/^/$*: /'
	@test -s $(out)/$*-gerbers.zip || { echo "jobset produced no $(out)/$*-gerbers.zip" >&2; exit 1; }

jlcpcb-%: fab-%
	@mkdir -p $(out)/jlcpcb
	$(PYTHON) -m boardtools jlcpcb pos $(out)/$*-all-pos.csv $(out)/jlcpcb/$*-cpl.csv
	$(PYTHON) -m boardtools jlcpcb bom $(out)/$*-bom.csv $(out)/jlcpcb/$*-bom.csv

clean:
	rm -rf $(OUT)

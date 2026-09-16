# KiCad board tooling. A board is any directory under boards/ holding <leaf>.kicad_{pro,sch,pcb}
# named after that directory, at any depth: boards/blinky/ or boards/chromatone/isolator/.
# The board id is the path relative to boards/ (e.g. chromatone/isolator).
# Exports are defined once in jobsets/fab.kicad_jobset (runs from the KiCad GUI too) and land
# in <board dir>/out/ (git-ignored).
#
#   make new NAME=id         scaffold boards/<id> from templates/board
#   make check  [BOARD=id]   ERC + DRC (all boards, or one); STRICT=1 also fails on warnings
#   make fab    [BOARD=id]   check, then run the fab jobset -> boards/<id>/out/ (+ <leaf>-gerbers.zip)
#   make export [BOARD=id]   the jobset without the Makefile checks
#   make jlcpcb [BOARD=id]   fab, then JLCPCB-format BOM/CPL -> boards/<id>/out/jlcpcb/
#   make test                boardtools unit tests
#   make smoke               scaffold throwaway boards in a temp dir and run the whole pipeline
#   make list                boards found under boards/
#   make clean               remove every boards/**/out/

KICAD_CLI ?= kicad-cli
PYTHON    ?= python3
STRICT    ?= 0
JOBSET    ?= jobsets/fab.kicad_jobset

# boards/<id>/<leaf>.kicad_pro where leaf = last path component of <id>
PRO_FILES  := $(shell find boards -name '*.kicad_pro' 2>/dev/null | sort)
ALL_BOARDS := $(foreach p,$(PRO_FILES),$(if $(filter $(notdir $(patsubst %/,%,$(dir $(p)))).kicad_pro,$(notdir $(p))),$(patsubst boards/%/,%,$(dir $(p)))))
BOARDS     := $(if $(BOARD),$(BOARD),$(ALL_BOARDS))

SEVERITY := --severity-error $(if $(filter 1,$(STRICT)),--severity-warning)

.PHONY: help list new check erc drc fab export jlcpcb test smoke clean
# Per-board targets (erc/<id>, fab/<id>, ...) are pattern rules and must NOT be .PHONY:
# make skips implicit-rule search for phony targets. The pattern contains a slash so the
# stem may contain slashes (nested board ids).

help:
	@sed -n '2,17p' $(MAKEFILE_LIST) | sed 's/^# \{0,1\}//'

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
# so they stay visible even when they do not fail the build.
erc/%:
	@test -f $(pro) || { echo "no board at $(dir) (expected $(pro))" >&2; exit 2; }
	@mkdir -p $(out)
	$(KICAD_CLI) sch erc --severity-warning -o $(out)/erc-warnings.rpt $(sch) >/dev/null
	$(KICAD_CLI) sch erc $(SEVERITY) --exit-code-violations -o $(out)/erc.rpt $(sch)

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

clean:
	find boards -type d -name out -prune -exec rm -rf {} +

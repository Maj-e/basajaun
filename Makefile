# Ulinautas — make data / make test / make serve
# Everything runs through uv (https://docs.astral.sh/uv/): `uv run` uses the
# .venv synced with uv.lock, no manual activation needed.
RUN  ?= uv run
PORT ?= 8000

# Episode to build (web/data/episodes.json); empty = the default episode.
#   make data EPISODE=los-angeles-2025-01
EPISODE ?=
export EPISODE

# Pipeline in order (README → Architecture). Scripts that don't exist yet
# are skipped with a notice, so `make data` works from Wave 0 on.
PIPELINE := \
	download_firms \
	export_hotspots \
	dedup \
	regions \
	fires \
	series \
	population \
	weather \
	terrain \
	spread \
	exposure \
	osm \
	make_manifest \
	validate

.PHONY: help install episode live data sample manifest validate contract-test e2e test serve clean

help:
	@echo "make install  - uv sync: create .venv and install uv.lock"
	@echo "make data     - run every script in order for the default episode (EPISODE=<id> for another; see web/data/episodes.json)"
	@echo "make episode  - show the selected episode (area, dates, folders)"
	@echo "make live     - fresh download of the last 48 h -> web/data/processed/live/ (not committed)"
	@echo "make sample   - generate sample data -> web/data/sample/"
	@echo "make manifest - rebuild web/data/manifest.json from the files present"
	@echo "make validate - check web/data/ against the contract (docs/schemas/)"
	@echo "make contract-test - prove the validator accepts good files and rejects broken ones"
	@echo "make e2e      - check the published site (URL=... to override)"
	@echo "make test     - pytest"
	@echo "make serve    - serve web/ at http://localhost:$(PORT)"

install:
	uv sync

episode:
	@$(RUN) scripts/config.py

# Live episode: always download again (download_firms.py reuses CSVs that already exist)
live:
	rm -rf data/raw/episodes/live
	$(MAKE) data EPISODE=live

data:
	@set -e; skip=" $$($(RUN) scripts/config.py skip) "; \
	$(RUN) scripts/config.py; \
	for s in $(PIPELINE); do \
		case "$$skip" in *" $$s "*) echo "-- $$s.py skipped for this episode"; continue;; esac; \
		if [ -f scripts/$$s.py ]; then \
			echo ">> $$s.py"; $(RUN) scripts/$$s.py; \
		else \
			echo "-- $$s.py not found yet, skipping"; \
		fi; \
	done

sample:
	$(RUN) scripts/make_sample.py

manifest:
	$(RUN) scripts/make_manifest.py

validate:
	$(RUN) scripts/validate.py

e2e:
	$(RUN) scripts/check_site.py $(if $(URL),--url $(URL))

contract-test:
	$(RUN) pytest scripts/tests/test_contract_fixtures.py -vv

test:
	$(RUN) pytest

serve:
	$(RUN) python -m http.server $(PORT) --directory web

clean:
	rm -rf .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

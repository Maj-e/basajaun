# Ulinautas — make data / make test / make serve
# Everything runs through uv (https://docs.astral.sh/uv/): `uv run` uses the
# .venv synced with uv.lock, no manual activation needed.
RUN  ?= uv run
PORT ?= 8000

# Pipeline in order (README → Architecture). Scripts that don't exist yet
# are skipped with a notice, so `make data` works from Wave 0 on.
PIPELINE := \
	download_firms \
	export_hotspots \
	dedup \
	fires \
	series \
	population \
	weather \
	exposure \
	osm \
	make_manifest \
	validate

.PHONY: help install data sample test serve clean

help:
	@echo "make install  - uv sync: create .venv and install uv.lock"
	@echo "make data     - run every script in order -> web/data/processed/"
	@echo "make sample   - generate sample data -> web/data/sample/"
	@echo "make test     - pytest"
	@echo "make serve    - serve web/ at http://localhost:$(PORT)"

install:
	uv sync

data:
	@set -e; for s in $(PIPELINE); do \
		if [ -f scripts/$$s.py ]; then \
			echo ">> $$s.py"; $(RUN) scripts/$$s.py; \
		else \
			echo "-- $$s.py not found yet, skipping"; \
		fi; \
	done

sample:
	$(RUN) scripts/make_sample.py

test:
	$(RUN) pytest

serve:
	$(RUN) python -m http.server $(PORT) --directory web

clean:
	rm -rf .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

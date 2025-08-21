PYTHON=python

install:
	$(PYTHON) -m pip install -r requirements.txt

format:
	ruff check . --fix || true

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q

scan:
	scripts/run_scan.sh

probe:
	scripts/run_probe.sh

simulate:
	scripts/run_sim.sh

# NEW: read-only discover (filters by edge; no swaps)
discover:
	python -m oldgold.exec.discover \
	  --chain bsc --base WBNB \
	  --tokens-file tokens.txt \
	  --min-edge-bps 400 \
	  --grid "1e3,1e4,1e5" \
	  --top 100

# NEW: dust probes on the shortlist + tax-aware sim
batch-probe:
	python -m oldgold.exec.batch_probe \
	  --chain bsc \
	  --infile out/discover_bsc_WBNB.json \
	  --top 15 \
	  --grid "1e3,5e3,1e4"

# NEW: quick human checklist
validate:
	@echo "1) Ensure RPC_BSC & PK set in .env"
	@echo "2) (optional) Wrap dust: python -m oldgold.exec.wrap --amount 0.001"
	@echo "3) Try: oldgold run-one --chain bsc --token 0x... --base WBNB --grid '1e3,5e3,1e4' --slip-bps 20"

docker-build:
	docker build -t oldgold .

docker-run:
	docker run --rm -it --env-file .env oldgold

.PHONY: install format test scan probe simulate discover batch-probe validate docker-build docker-run


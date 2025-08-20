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

discover:
	python -m oldgold.exec.discover --chain bsc --base WBNB --tokens-file tokens.txt --min-edge-bps 400 --grid "1e3,1e4,1e5" --top 100

batch-probe:
	python -m oldgold.exec.batch_probe --chain bsc --infile out/discover_bsc_WBNB.json --top 15 --grid "1e3,5e3,1e4"

docker-build:
	docker build -t oldgold .

docker-run:
	docker run --rm -it --env-file .env oldgold

.PHONY: install format test scan probe simulate discover batch-probe docker-build docker-run

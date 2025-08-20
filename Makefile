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

validate:
	@echo "1) Ensure RPC_BSC & PK set in .env"
	@echo "2) (optional) Wrap dust: python -m oldgold.exec.wrap --amount 0.001"
	@echo "3) Try: oldgold run-one --chain bsc --token 0x... --base WBNB --grid '1e3,5e3,1e4' --slip-bps 20"

docker-build:
	docker build -t oldgold .

docker-run:
	docker run --rm -it --env-file .env oldgold

.PHONY: install format test scan probe simulate validate docker-build docker-run

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

docker-build:
	docker build -t oldgold .

docker-run:
	docker run --rm -it --env-file .env oldgold

.PHONY: install format test scan probe simulate docker-build docker-run

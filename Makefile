.PHONY: setup morning serve test status calendar-auth gmail-auth install-service uninstall-service

PYTHON ?= $(if $(wildcard venv/bin/python),venv/bin/python,$(if $(wildcard .venv/bin/python3),.venv/bin/python3,python3))

setup:
	python3 -m venv venv
	venv/bin/python -m pip install -r requirements.txt

morning:
	PYTHONPATH=. $(PYTHON) scripts/morning.py

serve:
	PYTHONPATH=. $(PYTHON) server/app.py

test:
	MD_OFFLINE=1 PYTHONPATH=. $(PYTHON) -m unittest discover -s tests

status:
	PYTHONPATH=. $(PYTHON) scripts/status.py

calendar-auth:
	PYTHONPATH=. $(PYTHON) -m connectors.calendar_google --auth

gmail-auth:
	PYTHONPATH=. $(PYTHON) -m connectors.airbnb_gmail --auth

install-service:
	PYTHONPATH=. $(PYTHON) scripts/install_launchd.py

uninstall-service:
	PYTHONPATH=. $(PYTHON) scripts/install_launchd.py --uninstall

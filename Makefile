.PHONY: morning serve test

PYTHON ?= python3

morning:
	PYTHONPATH=. $(PYTHON) scripts/morning.py

serve:
	PYTHONPATH=. $(PYTHON) server/app.py

test:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests

PYTHON ?= python3

.PHONY: demo test parts check

demo:
	$(PYTHON) -m forgeworks.demo

test:
	$(PYTHON) -X dev -W error -m unittest discover -s tests -v

parts:
	$(PYTHON) -m series --check

check: test demo parts

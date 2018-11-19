.DEFAULT_GOAL := all
PYTHONPATH := ${pwd}

.PHONY: install
install:
	pip install -U setuptools pip
	pip install -U -r requirements.txt
	pip install -U -e .

.PHONY: format
format:
	isort -rc -w 120 aiohttptools tests
	black -S -l 120 --py36 aiohttptools tests

.PHONY: lint
lint:
	python setup.py check -rms
	flake8 aiohttptools/ tests/
	pytest aiohttptools -p no:sugar -q
	black -S -l 120 --py36 --check aiohttptools tests

.PHONY: test
test:
	pytest --cov=aiohttptools

.PHONY: testcov
testcov:
	pytest --cov=aiohttptools
	@echo "building coverage html"
	@coverage html

.PHONY: all
all: testcov lint

.PHONY: benchmark-all
benchmark-all:
	python benchmarks/run.py

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -rf .cache
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
	python setup.py clean
	make -C docs clean

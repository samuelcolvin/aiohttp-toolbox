.DEFAULT_GOAL := all

.PHONY: install-minimal
install-minimal:
	pip install -U setuptools pip
	pip install -U -r tests/requirements.txt
	pip install -U -e .

.PHONY: install
install:
	pip install -U setuptools pip
	pip install -U -r requirements.txt
	pip install -U -e .[all]

.PHONY: format
format:
	isort -rc -w 120 atoolbox tests
	black -S -l 120 --py36 atoolbox tests

.PHONY: lint
lint:
	python setup.py check -rms
	flake8 atoolbox/ tests/
	pytest atoolbox -p no:sugar -q -W ignore
	black -S -l 120 --py36 --check atoolbox tests

.PHONY: test
test:
	pytest --cov=atoolbox

.PHONY: test-minimal
test-minimal:
	pytest minimal_tests.py --cov=atoolbox

.PHONY: testcov
testcov:
	pytest --cov=atoolbox
	@echo "building coverage html"
	@coverage html

.PHONY: all
all: testcov lint

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -rf .cache
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
	python setup.py clean

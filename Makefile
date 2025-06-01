PYTEST_CMD=TESTING=true pytest tests -vv

SHELL := /bin/bash # Use bash syntax

# dev aliases format and lint
RUFF=ruff format server client tests
BLACK=black server client tests
MYPY=mypy server client tests

install: ## install poetry and pip + all deps for the project
	pip install -U uv
	uv pip install .

format: ## Reformat project code.
	${RUFF}
	${BLACK}

test: ## to run tests
	${PYTEST_CMD}

help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install lint format test help

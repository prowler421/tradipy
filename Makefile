# tradipy — developer commands.
# Every target runs through `uv`, so there is nothing to activate by hand.
# Run `make help` for the list.

.DEFAULT_GOAL := help
.PHONY: help install sync run test coverage lint format format-check check typecheck \
        clean docs precommit release

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Create the environment and install everything (incl. dev group + pre-commit)
	uv sync
	uv run pre-commit install

sync: ## Sync the environment to uv.lock
	uv sync

run: ## Run a package module, e.g. `make run ARGS="-m tradipy"`
	uv run python $(ARGS)

test: ## Run the test suite
	uv run pytest

coverage: ## Run tests with coverage and print a report
	uv run pytest --cov=tradipy --cov-report=term-missing --cov-report=xml

lint: ## Lint with Ruff
	uv run ruff check src tests scripts

format: ## Format with Ruff
	uv run ruff format src tests scripts

format-check: ## Verify formatting without rewriting (what CI runs)
	uv run ruff format --check src tests scripts

typecheck: ## Static type check with BasedPyright
	uv run basedpyright

check: lint format-check typecheck test ## Lint, format check, type check, test — what CI runs

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov dist build \
		src/*.egg-info **/__pycache__
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

docs: ## List the project documentation
	@echo "Docs live in docs/ and README.md:"
	@ls -1 docs

precommit: ## Run all pre-commit hooks against every file
	uv run pre-commit run --all-files

release: ## Print the release checklist (see docs/development.md)
	@echo "Release: bump version in pyproject.toml, update CHANGELOG.md, tag vX.Y.Z, push --tags."

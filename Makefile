.PHONY: help install install-python install-node setup test test-infra test-cov test-verbose clean deploy deploy-prod deploy-function plan plan-prod invoke logs logs-tail lint format venv venv-activate venv-deactivate remove

# Variables
PYTHON_VERSION := 3.9.20
PYTHON_MAJOR_MINOR := 3.9
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
NODE := node
NPM := npm
SERVERLESS := npx serverless
STAGE := dev
export NODE_OPTIONS := --no-deprecation

# Default target
help:
	@echo "Invictus Weightlifting WOD ETL - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              - Complete project setup (venv + dependencies)"
	@echo "  make install            - Install all dependencies (Python + Node)"
	@echo "  make install-python     - Install Python dependencies only"
	@echo "  make install-node      - Install Node.js dependencies only"
	@echo "  make venv              - Create Python virtual environment"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests"
	@echo "  make test-infra        - Run infrastructure tests only"
	@echo "  make test-cov          - Run tests with coverage report"
	@echo "  make test-verbose      - Run tests with verbose output"
	@echo ""
	@echo "Deployment:"
	@echo "  make plan              - Preview deployment changes (dry-run)"
	@echo "  make plan-prod         - Preview production deployment changes"
	@echo "  make deploy            - Deploy to dev stage"
	@echo "  make deploy-prod       - Deploy to prod stage"
	@echo "  make deploy-function   - Deploy single function (use FUNC=name)"
	@echo ""
	@echo "Local Development:"
	@echo "  make invoke            - Invoke function locally (use FUNC=name EVENT=path)"
	@echo "  make logs              - View function logs (use FUNC=name)"
	@echo "  make logs-tail         - Tail function logs (use FUNC=name)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run linting checks"
	@echo "  make format            - Format code with autopep8"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             - Remove build artifacts and caches"
	@echo "  make remove            - Remove virtual environment"

# Setup
setup: venv install
	@echo "✓ Setup complete!"

install: install-python install-node

install-python: venv
	@if [ ! -d "$(VENV)" ] || [ ! -f "$(PYTHON)" ]; then \
		echo "Error: Virtual environment not found. Run 'make venv' first."; \
		exit 1; \
	fi
	@echo "Installing Python dependencies..."
	@if command -v uv >/dev/null 2>&1; then \
		uv pip install -r requirements.txt --python $(PYTHON); \
	else \
		$(PIP) install -r requirements.txt; \
	fi
	@echo "✓ Python dependencies installed"

install-node:
	@echo "Installing Node.js dependencies..."
	@$(NPM) install
	@echo "✓ Node.js dependencies installed"

venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		if command -v uv >/dev/null 2>&1; then \
			if command -v pyenv >/dev/null 2>&1; then \
				PYTHON_CMD=$$(pyenv which python 2>/dev/null || echo ""); \
				if [ -n "$$PYTHON_CMD" ] && [ -f "$$PYTHON_CMD" ]; then \
					uv venv $(VENV) --python "$$PYTHON_CMD"; \
				else \
					uv venv $(VENV) --python $(PYTHON_MAJOR_MINOR); \
				fi; \
			else \
				uv venv $(VENV) --python $(PYTHON_MAJOR_MINOR); \
			fi; \
		else \
			PYTHON_CMD=""; \
			if command -v pyenv >/dev/null 2>&1; then \
				PYTHON_CMD=$$(pyenv which python 2>/dev/null || echo ""); \
				if [ -n "$$PYTHON_CMD" ] && [ -f "$$PYTHON_CMD" ]; then \
					$$PYTHON_CMD -m venv $(VENV); \
				elif command -v python3 >/dev/null 2>&1; then \
					python3 -m venv $(VENV); \
				else \
					echo "Error: Python not found via pyenv or python3"; \
					exit 1; \
				fi; \
			elif command -v python$(PYTHON_MAJOR_MINOR) >/dev/null 2>&1; then \
				python$(PYTHON_MAJOR_MINOR) -m venv $(VENV); \
			elif command -v python3 >/dev/null 2>&1; then \
				python3 -m venv $(VENV); \
			else \
				echo "Error: Python $(PYTHON_MAJOR_MINOR) or python3 not found"; \
				exit 1; \
			fi; \
		fi; \
		if [ ! -d "$(VENV)" ]; then \
			echo "Error: Failed to create virtual environment"; \
			exit 1; \
		fi; \
		echo "✓ Virtual environment created"; \
	else \
		echo "Virtual environment already exists"; \
	fi

venv-activate:
	@echo "To activate virtual environment, run:"
	@echo "  source $(VENV)/bin/activate"

venv-deactivate:
	@echo "To deactivate virtual environment, run:"
	@echo "  deactivate"

# Testing
test:
	@echo "Running tests..."
	@$(PYTHON) -m pytest

test-infra:
	@echo "Running infrastructure tests..."
	@$(PYTHON) -m pytest -m infrastructure

test-cov:
	@echo "Running tests with coverage..."
	@$(PYTHON) -m pytest --cov --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

test-verbose:
	@echo "Running tests with verbose output..."
	@$(PYTHON) -m pytest -vv

# Deployment
plan:
	@echo "=========================================="
	@echo "Deployment Plan (Dry Run) - $(STAGE) stage"
	@echo "=========================================="
	@echo ""
	@echo "1. Compiled Serverless Configuration:"
	@echo "--------------------------------------"
	@$(SERVERLESS) print --stage $(STAGE) 2>/dev/null || $(SERVERLESS) print --stage $(STAGE) --format json
	@echo ""
	@echo "2. Packaging service (without deploying)..."
	@echo "--------------------------------------"
	@-$(SERVERLESS) package --stage $(STAGE) --package .serverless/plan-package 2>&1 || echo "  (Note: Packaging failed - check environment variables in .env file)"
	@echo ""
	@echo "3. Deployment Summary:"
	@echo "--------------------------------------"
	@echo "Service: invictus-weightlifting"
	@echo "Stage: $(STAGE)"
	@echo "Region: us-east-1"
	@echo "Runtime: python3.9"
	@echo ""
	@echo "Functions to be deployed:"
	@sed -n '/^functions:/,/^[^ ]/p' serverless.yml | grep -E "^  [a-zA-Z_][a-zA-Z0-9_]*:" | sed 's/://g' | sed 's/^  /  - /' || echo "  (check serverless.yml for function definitions)"
	@echo ""
	@echo "4. CloudFormation Stack Changes:"
	@echo "--------------------------------------"
	@echo "To see detailed CloudFormation changes, run:"
	@echo "  aws cloudformation describe-stacks --stack-name invictus-weightlifting-$(STAGE) --region us-east-1"
	@echo ""
	@echo "✓ Plan complete. No resources were created or modified."
	@echo "  Run 'make deploy' to apply these changes."

plan-prod:
	@echo "=========================================="
	@echo "Deployment Plan (Dry Run) - prod stage"
	@echo "=========================================="
	@echo ""
	@echo "1. Compiled Serverless Configuration:"
	@echo "--------------------------------------"
	@$(SERVERLESS) print --stage prod 2>/dev/null || $(SERVERLESS) print --stage prod --format json
	@echo ""
	@echo "2. Packaging service (without deploying)..."
	@echo "--------------------------------------"
	@-$(SERVERLESS) package --stage prod --package .serverless/plan-package-prod 2>&1 || echo "  (Note: Packaging failed - check environment variables in .env file)"
	@echo ""
	@echo "3. Deployment Summary:"
	@echo "--------------------------------------"
	@echo "Service: invictus-weightlifting"
	@echo "Stage: prod"
	@echo "Region: us-east-1"
	@echo "Runtime: python3.9"
	@echo ""
	@echo "Functions to be deployed:"
	@sed -n '/^functions:/,/^[^ ]/p' serverless.yml | grep -E "^  [a-zA-Z_][a-zA-Z0-9_]*:" | sed 's/://g' | sed 's/^  /  - /' || echo "  (check serverless.yml for function definitions)"
	@echo ""
	@echo "4. CloudFormation Stack Changes:"
	@echo "--------------------------------------"
	@echo "To see detailed CloudFormation changes, run:"
	@echo "  aws cloudformation describe-stacks --stack-name invictus-weightlifting-prod --region us-east-1"
	@echo ""
	@echo "✓ Plan complete. No resources were created or modified."
	@echo "  Run 'make deploy-prod' to apply these changes."

deploy:
	@echo "Deploying to $(STAGE) stage..."
	@$(SERVERLESS) deploy --stage $(STAGE)

deploy-prod:
	@echo "Deploying to prod stage..."
	@$(SERVERLESS) deploy --stage prod

deploy-function:
	@if [ -z "$(FUNC)" ]; then \
		echo "Error: FUNC variable required. Usage: make deploy-function FUNC=function_name"; \
		exit 1; \
	fi
	@echo "Deploying function $(FUNC)..."
	@$(SERVERLESS) deploy function -f $(FUNC) --stage $(STAGE)

# Local invocation
invoke:
	@if [ -z "$(FUNC)" ]; then \
		echo "Error: FUNC variable required. Usage: make invoke FUNC=function_name EVENT=test_events/file.json"; \
		exit 1; \
	fi
	@if [ -z "$(EVENT)" ]; then \
		echo "Error: EVENT variable required. Usage: make invoke FUNC=function_name EVENT=test_events/file.json"; \
		exit 1; \
	fi
	@echo "Invoking $(FUNC) with $(EVENT)..."
	@$(SERVERLESS) invoke local -f $(FUNC) --path $(EVENT)

# Logs
logs:
	@if [ -z "$(FUNC)" ]; then \
		echo "Error: FUNC variable required. Usage: make logs FUNC=function_name"; \
		exit 1; \
	fi
	@echo "Fetching logs for $(FUNC)..."
	@$(SERVERLESS) logs -f $(FUNC) --stage $(STAGE)

logs-tail:
	@if [ -z "$(FUNC)" ]; then \
		echo "Error: FUNC variable required. Usage: make logs-tail FUNC=function_name"; \
		exit 1; \
	fi
	@echo "Tailing logs for $(FUNC)..."
	@$(SERVERLESS) logs -f $(FUNC) --tail --stage $(STAGE)

# Code Quality
lint:
	@echo "Running linting checks..."
	@$(PYTHON) -m pycodestyle --max-line-length=120 handler.py transforms.py tests/

format:
	@echo "Formatting code..."
	@$(PYTHON) -m autopep8 --in-place --aggressive --aggressive --max-line-length=120 handler.py transforms.py tests/

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf .serverless/
	@rm -rf .pytest_cache/
	@rm -rf __pycache__/
	@rm -rf tests/__pycache__/
	@rm -rf htmlcov/
	@rm -rf .coverage
	@rm -rf *.pyc
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Clean complete"

remove:
	@echo "Removing virtual environment..."
	@rm -rf $(VENV)
	@echo "✓ Virtual environment removed"


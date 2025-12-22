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
	@echo "  make invoke-direct     - Invoke function directly with Python (bypasses Serverless)"
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
	@echo "Cleaning previous build artifacts..."
	@rm -rf .serverless/plan-package
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
	@echo "Cleaning previous build artifacts..."
	@rm -rf .serverless/plan-package-prod
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
	@echo "Cleaning previous build artifacts..."
	@rm -rf .serverless/
	@echo "Deploying to $(STAGE) stage..."
	@$(SERVERLESS) deploy --stage $(STAGE)

deploy-prod:
	@echo "Cleaning previous build artifacts..."
	@rm -rf .serverless/
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
	@if [ ! -d "$(VENV)" ] || [ ! -f "$(PYTHON)" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ ! -f ".env" ]; then \
		echo "Warning: .env file not found. Some functions may require environment variables."; \
		echo "Create a .env file with INVICTUS_USER and INVICTUS_PASS if needed."; \
	fi
	@echo "Invoking $(FUNC) with $(EVENT)..."
	@echo "Using Python from: $(PYTHON)"
	@echo "Using virtual environment: $(VENV)"
	@PATH="$(VENV)/bin:$$PATH" \
	VIRTUAL_ENV="$(VENV)" \
	PYTHONPATH="$(VENV)/lib/python$(PYTHON_MAJOR_MINOR)/site-packages:$$PYTHONPATH" \
	$(SERVERLESS) invoke local -f $(FUNC) --path $(EVENT) --stage $(STAGE)

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

# Step Functions
sf-list-executions:
	@echo "Listing recent Step Functions executions..."
	@aws stepfunctions list-executions \
		--state-machine-arn "arn:aws:states:$${AWS_REGION:-us-east-1}:$${AWS_ACCOUNT_ID:-}:stateMachine:SemiStructureInvictusPostStateMachine-${STAGE}" \
		--max-results 10 \
		--query 'executions[*].[executionArn,name,status,startDate]' \
		--output table || echo "Error: Could not list executions. Check AWS credentials and region."

sf-get-execution:
	@if [ -z "$(EXECUTION_ARN)" ]; then \
		echo "Error: EXECUTION_ARN required. Usage: make sf-get-execution EXECUTION_ARN=arn:aws:states:..."; \
		echo "Or use: make sf-list-executions to see recent executions"; \
		exit 1; \
	fi
	@echo "Getting execution details for $(EXECUTION_ARN)..."
	@aws stepfunctions describe-execution \
		--execution-arn "$(EXECUTION_ARN)" \
		--query '{Status:status,StartDate:startDate,StopDate:stopDate,Input:input,Output:output}' \
		--output json | python3 -m json.tool || echo "Error: Could not get execution details."

sf-get-execution-history:
	@if [ -z "$(EXECUTION_ARN)" ]; then \
		echo "Error: EXECUTION_ARN required. Usage: make sf-get-execution-history EXECUTION_ARN=arn:aws:states:..."; \
		echo "Or use: make sf-list-executions to see recent executions"; \
		exit 1; \
	fi
	@echo "Getting execution history for $(EXECUTION_ARN)..."
	@aws stepfunctions get-execution-history \
		--execution-arn "$(EXECUTION_ARN)" \
		--query 'events[*].[id,type,timestamp,{State:stateEnteredEventDetails.stateMachine.name,Input:stateEnteredEventDetails.input,Output:stateExitedEventDetails.output,Error:executionFailedEventDetails.error}]' \
		--output table || echo "Error: Could not get execution history."

sf-logs:
	@if [ -z "$(EXECUTION_ARN)" ]; then \
		echo "Error: EXECUTION_ARN required. Usage: make sf-logs EXECUTION_ARN=arn:aws:states:..."; \
		echo "Or use: make sf-list-executions to see recent executions"; \
		exit 1; \
	fi
	@echo "Getting execution logs for $(EXECUTION_ARN)..."
	@aws stepfunctions get-execution-history \
		--execution-arn "$(EXECUTION_ARN)" \
		--reverse-order \
		--query 'events[*].[timestamp,type,{Details:stateEnteredEventDetails.stateMachine.name || executionFailedEventDetails.error || executionSucceededEventDetails.output}]' \
		--output table || echo "Error: Could not get execution logs."

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


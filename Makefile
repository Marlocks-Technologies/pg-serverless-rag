.PHONY: install test lint package-lambdas tf-init tf-plan tf-apply tf-destroy clean help

PYTHON := python3
PIP := pip3
ENV ?= dev
AWS_REGION ?= us-east-1

## help: Show this help message
help:
	@echo 'Usage:'
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'

## install: Install Python dependencies
install:
	$(PIP) install -e services/shared/
	$(PIP) install -r services/document_processor/requirements.txt
	$(PIP) install -r services/chat_handler/requirements.txt
	$(PIP) install pytest pytest-cov moto ruff mypy

## test: Run test suite
test:
	$(PYTHON) -m pytest services/ -v --tb=short --cov=services/shared/src --cov-report=term-missing

## lint: Run linters and type checkers
lint:
	$(PYTHON) -m ruff check services/
	$(PYTHON) -m mypy services/shared/src/ --ignore-missing-imports

## format: Auto-format code
format:
	$(PYTHON) -m ruff format services/

## package-lambdas: Package Lambda functions into deployment ZIP files
package-lambdas:
	@echo "Packaging Lambda functions..."
	@mkdir -p dist
	@# Package document processor
	cd services/document_processor && \
		rm -rf package && mkdir package && \
		$(PIP) install -r requirements.txt -t package/ && \
		cd package && zip -r ../../dist/document_processor.zip . && cd .. && \
		cd src && zip -g ../../dist/document_processor.zip *.py && cd ../..
	@# Package chat handler
	cd services/chat_handler && \
		rm -rf package && mkdir package && \
		$(PIP) install -r requirements.txt -t package/ && \
		cd package && zip -r ../../dist/chat_handler.zip . && cd .. && \
		cd src && zip -g ../../dist/chat_handler.zip *.py && cd ../..
	@# Package shared library as Lambda layer
	cd services/shared && \
		rm -rf python && mkdir -p python && \
		cp -r src/* python/ && \
		zip -r ../../dist/shared_layer.zip python && \
		rm -rf python
	@echo "Lambda packages created in dist/"

## tf-init: Initialize Terraform for specified environment
tf-init:
	cd infra/terraform/environments/$(ENV) && terraform init

## tf-plan: Run Terraform plan for specified environment
tf-plan:
	cd infra/terraform/environments/$(ENV) && terraform plan -var-file=terraform.tfvars

## tf-apply: Apply Terraform changes for specified environment
tf-apply:
	cd infra/terraform/environments/$(ENV) && terraform apply -var-file=terraform.tfvars

## tf-destroy: Destroy Terraform infrastructure for specified environment
tf-destroy:
	cd infra/terraform/environments/$(ENV) && terraform destroy -var-file=terraform.tfvars

## tf-output: Show Terraform outputs for specified environment
tf-output:
	cd infra/terraform/environments/$(ENV) && terraform output

## clean: Remove build artifacts and temporary files
clean:
	rm -rf dist/
	rm -rf services/*/package/
	rm -rf services/*/python/
	rm -rf services/*/.pytest_cache
	rm -rf services/*/__pycache__
	rm -rf services/shared/src/__pycache__
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete

## validate-schemas: Validate JSON schemas
validate-schemas:
	@echo "Validating JSON schemas..."
	@for schema in schemas/api/*.json schemas/metadata/*.json; do \
		echo "Validating $$schema"; \
		$(PYTHON) -c "import json; json.load(open('$$schema'))" || exit 1; \
	done
	@echo "All schemas valid"

## deploy-full: Full deployment - package, init, and apply
deploy-full: clean package-lambdas tf-init tf-plan
	@echo "Ready to deploy to $(ENV). Proceed with 'make tf-apply ENV=$(ENV)'"

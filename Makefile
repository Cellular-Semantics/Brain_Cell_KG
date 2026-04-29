# Brain Cell Knowledge Graph Build System
# Orchestrates ROBOT template processing and report generation

# Configuration
NEO4J_HOST ?= localhost
NEO4J_PORT ?= 7687
NEO4J_USER ?= neo4j
NEO4J_PASS ?= neo

# Directories
SRC_DIR = src
TEMPLATES_DIR = $(SRC_DIR)/templates
CYPHER_DIR = $(SRC_DIR)/cypher
CYPHER_UPDATES_DIR = $(SRC_DIR)/cypher_updates
UTILS_DIR = $(SRC_DIR)/utils
SOURCE_DATA_DIR = $(SRC_DIR)/source_data
REPORTS_DIR = reports
BUILD_DIR = build
OWL_DIR = owl

# Python environment
PYTHON = python3
VENV_DIR = .venv
VENV_PYTHON = $(VENV_DIR)/bin/python

# Default target
.PHONY: all
all: templates reports

# Check that virtual environment exists
$(VENV_PYTHON):
	@if [ ! -f $(VENV_PYTHON) ]; then \
		echo "Virtual environment not found. Please run: python3 -m venv .venv && .venv/bin/pip install -e ."; \
		exit 1; \
	fi

# Create necessary directories
$(BUILD_DIR):
	mkdir -p $@

$(REPORTS_DIR):
	mkdir -p $@

$(OWL_DIR):
	mkdir -p $@

# Template processing targets
# Generated template files (static list)
GENERATED_TEMPLATES = $(TEMPLATES_DIR)/scFAIR_WHB2WMB_template.tsv $(TEMPLATES_DIR)/BG2WMB_AT_map_template.tsv

# Corresponding OWL outputs
GENERATED_OWL = $(OWL_DIR)/scFAIR_WHB2WMB_template.owl $(OWL_DIR)/BG2WMB_AT_map_template.owl

# Static templates in src/templates (if any exist)
STATIC_TEMPLATE_FILES = $(wildcard $(TEMPLATES_DIR)/*.tsv)
STATIC_OWL = $(STATIC_TEMPLATE_FILES:$(TEMPLATES_DIR)/%.tsv=$(OWL_DIR)/%.owl)

# Generated templates in root templates/ (e.g. location mappings)
ROOT_TEMPLATES_DIR = templates
ROOT_TEMPLATE_FILES = $(wildcard $(ROOT_TEMPLATES_DIR)/*.tsv)
ROOT_OWL = $(ROOT_TEMPLATE_FILES:$(ROOT_TEMPLATES_DIR)/%.tsv=$(OWL_DIR)/%.owl)

# Generated OWL outputs from root templates that may not exist at parse time
# (must be listed explicitly because $(wildcard) is evaluated before recipes run)
ROOT_GENERATED_OWL = $(OWL_DIR)/wmb_total_cell_counts.owl

# All OWL outputs
ALL_OWL_OUTPUTS = $(GENERATED_OWL) $(STATIC_OWL) $(ROOT_OWL) $(ROOT_GENERATED_OWL)

# Generate scFAIR template from source data
$(TEMPLATES_DIR)/scFAIR_WHB2WMB_template.tsv: src/scripts/scFAIR_WHB_WMB/source_data/scFAIR_Siletti_AT_map.tsv $(VENV_PYTHON)
	$(VENV_PYTHON) src/scripts/scFAIR_WHB_WMB/scripts/scFAIR_Sillet_WMB_2_KG.py \
		--input $< \
		--output $@

# Fetch BG2WMB mappings from Google Sheets
src/scripts/BG_WMB_AT/source_data/MWB_consensus_homology.csv: $(VENV_PYTHON)
	$(VENV_PYTHON) src/scripts/BG_WMB_AT/scripts/fetch_bg2wmb_mappings.py \
		--output $@

# Generate BG2WMB template from source data
$(TEMPLATES_DIR)/BG2WMB_AT_map_template.tsv: src/scripts/BG_WMB_AT/source_data/MWB_consensus_homology.csv $(VENV_PYTHON)
	$(VENV_PYTHON) src/scripts/BG_WMB_AT/scripts/WMB_BG_AT_map.py \
		--input $< \
		--output $@

# Process ROBOT templates with prefixes
$(OWL_DIR)/%.owl: $(TEMPLATES_DIR)/%.tsv $(UTILS_DIR)/prefixes.json | $(OWL_DIR)
	robot template \
		--add-prefixes $(UTILS_DIR)/prefixes.json \
		--template $< \
		--output $@

$(OWL_DIR)/%.owl: $(ROOT_TEMPLATES_DIR)/%.tsv $(UTILS_DIR)/prefixes.json | $(OWL_DIR)
	robot template \
		--add-prefixes $(UTILS_DIR)/prefixes.json \
		--template $< \
		--output $@

# Mock build target for testing without ROBOT
.PHONY: mock-templates
mock-templates: $(VENV_PYTHON) | $(OWL_DIR)
	@echo "Mock processing templates (ROBOT not required)..."
	@for template in $(TEMPLATE_FILES); do \
		output=$$(echo $$template | sed 's|$(TEMPLATES_DIR)|$(OWL_DIR)|' | sed 's|\.tsv$$|.owl|'); \
		echo "Mock: $$template -> $$output"; \
		echo "# Mock OWL file generated from $$template" > $$output; \
		echo "# Prefixes would be applied from $(UTILS_DIR)/prefixes.json" >> $$output; \
		cat $(UTILS_DIR)/prefixes.json >> $$output; \
	done

.PHONY: templates owl
templates: $(GENERATED_TEMPLATES) $(ALL_OWL_OUTPUTS)
owl: $(GENERATED_TEMPLATES) $(ALL_OWL_OUTPUTS)

# Report generation from Cypher queries
CYPHER_FILES = $(wildcard $(CYPHER_DIR)/*.cypher)
REPORT_OUTPUTS = $(CYPHER_FILES:$(CYPHER_DIR)/%.cypher=$(REPORTS_DIR)/%.csv)

# Generate reports from Cypher queries
$(REPORTS_DIR)/%.csv: $(CYPHER_DIR)/%.cypher $(VENV_PYTHON) | $(REPORTS_DIR)
	$(VENV_PYTHON) $(UTILS_DIR)/generate_report.py \
		--query $< \
		--output $@ \
		--host $(NEO4J_HOST) \
		--port $(NEO4J_PORT) \
		--user $(NEO4J_USER) \
		--password $(NEO4J_PASS)

.PHONY: reports
reports: $(REPORT_OUTPUTS)

# Template generation from source data
.PHONY: generate-templates
generate-templates: hierarchical-location-templates wmb-total-cell-count-template $(VENV_PYTHON)
	@for source in $(wildcard $(SOURCE_DATA_DIR)/*/); do \
		if [ -f "$$source/code/generate.py" ]; then \
			echo "Processing $$source"; \
			cd "$$source/code" && ../../../../$(VENV_PYTHON) generate.py || echo "Error in $$source - continuing..."; \
		fi; \
	done
	@for source in $(wildcard $(SRC_DIR)/scripts/*/); do \
		if [ -f "$$source/scripts/generate.py" ]; then \
			echo "Processing $$source"; \
			cd "$$source/scripts" && ../../../../$(VENV_PYTHON) generate.py || echo "Error in $$source - continuing..."; \
		fi; \
	done

# WMB token mapping generation
.PHONY: wmb-token-mapping
wmb-token-mapping: $(VENV_PYTHON)
	@echo "Generating WMB token mapping reports..."
	cd $(SRC_DIR)/scripts/WMB_token_map/scripts && ../../../../$(VENV_PYTHON) generate.py

# WMB additional hierarchical reports
.PHONY: wmb-additional-reports
wmb-additional-reports: wmb-token-mapping update-kg $(VENV_PYTHON)
	@echo "Generating WMB additional hierarchical reports..."
	cd $(SRC_DIR)/scripts/WMB_token_map/scripts && ../../../../$(VENV_PYTHON) generate_additional_reports.py --output-dir ../reports

# WMB ROBOT template generation
.PHONY: wmb-robot-templates
wmb-robot-templates: wmb-additional-reports $(VENV_PYTHON)
	@echo "Generating ROBOT templates from WMB token mapping..."
	cd $(SRC_DIR)/scripts/WMB_token_map/scripts && ../../../../$(VENV_PYTHON) generate_robot_templates.py \
		--report-file ../reports/wmb_most_general_terms_report.csv \
		--output-dir ../../../../templates

# CURIE prefix management
.PHONY: update-neo4j-prefixes
update-neo4j-prefixes: $(VENV_PYTHON)
	@echo "Updating Neo4j CURIE prefixes from prefixes.json..."
	$(VENV_PYTHON) -c "import json, yaml; prefixes = json.load(open('$(UTILS_DIR)/prefixes.json'))['@context']; prefixes.pop('@version', None); config = yaml.safe_load(open('config/dumps/neo4j2owl-config.yaml')); config['curie_map'] = prefixes; yaml.dump(config, open('config/dumps/neo4j2owl-config.yaml', 'w'), default_flow_style=False, sort_keys=False)"
	@echo "Neo4j CURIE prefixes updated from $(UTILS_DIR)/prefixes.json"

# Namespace detection and resolution
.PHONY: detect-missing-namespaces
detect-missing-namespaces: $(VENV_PYTHON) | $(REPORTS_DIR)
	@echo "Detecting missing CURIE namespaces in knowledge graph..."
	$(VENV_PYTHON) $(UTILS_DIR)/namespace_detective.py \
		--output $(REPORTS_DIR)/missing_namespaces_report.csv \
		--host $(NEO4J_HOST) --port $(NEO4J_PORT) \
		--user $(NEO4J_USER) --password $(NEO4J_PASS)

.PHONY: suggest-missing-prefixes
suggest-missing-prefixes: detect-missing-namespaces $(VENV_PYTHON)
	@echo "Generating prefix suggestions from namespace analysis..."
	$(VENV_PYTHON) $(UTILS_DIR)/namespace_detective.py \
		--output $(REPORTS_DIR)/missing_namespaces_report.csv \
		--host $(NEO4J_HOST) --port $(NEO4J_PORT) \
		--user $(NEO4J_USER) --password $(NEO4J_PASS) \
		--suggest

# Knowledge graph updates from Cypher statements
.PHONY: update-kg
update-kg: $(VENV_PYTHON)
	$(VENV_PYTHON) $(UTILS_DIR)/update_kg.py \
		--updates-dir $(CYPHER_UPDATES_DIR) \
		--host $(NEO4J_HOST) \
		--port $(NEO4J_PORT) \
		--user $(NEO4J_USER) \
		--password $(NEO4J_PASS) \
		--log-file kg_updates.log

# Dry run for knowledge graph updates (shows what would be executed)
.PHONY: update-kg-dry-run
update-kg-dry-run: $(VENV_PYTHON)
	$(VENV_PYTHON) $(UTILS_DIR)/update_kg.py \
		--updates-dir $(CYPHER_UPDATES_DIR) \
		--host $(NEO4J_HOST) \
		--port $(NEO4J_PORT) \
		--user $(NEO4J_USER) \
		--password $(NEO4J_PASS) \
		--dry-run

# Continue executing updates even if some fail
.PHONY: update-kg-continue
update-kg-continue: $(VENV_PYTHON)
	$(VENV_PYTHON) $(UTILS_DIR)/update_kg.py \
		--updates-dir $(CYPHER_UPDATES_DIR) \
		--host $(NEO4J_HOST) \
		--port $(NEO4J_PORT) \
		--user $(NEO4J_USER) \
		--password $(NEO4J_PASS) \
		--continue-on-error

# Cell count and proportion analysis
.PHONY: cell-count-analysis
cell-count-analysis: $(VENV_PYTHON)
	@echo "Generating cell count and proportion reports from CCF data..."
	cd $(SRC_DIR)/scripts/cell_counts/scripts && ../../../../$(VENV_PYTHON) generate_cell_proportion_reports.py

# Generate taxonomy × region matrices
.PHONY: taxonomy-matrices
taxonomy-matrices: $(VENV_PYTHON)
	@echo "Generating complete taxonomy × brain region matrices..."
	cd $(SRC_DIR)/scripts/cell_counts/scripts && ../../../../$(VENV_PYTHON) generate_full_matrices.py

# Generate hierarchical location mapping templates
.PHONY: hierarchical-location-templates
hierarchical-location-templates: taxonomy-matrices $(VENV_PYTHON)
	@echo "Generating hierarchical location mapping ROBOT templates..."
	$(VENV_PYTHON) $(SRC_DIR)/scripts/cell_counts/generate_hierarchical_location_templates.py \
		--input-dir $(SRC_DIR)/scripts/cell_counts/reports/taxonomy_by_region_matrices \
		--output-dir templates \
		--cutoff 0.05

# Total cell count template (per WMB cell type, region-agnostic).
# File-target rule so 'make owl' triggers regeneration if CSV inputs change.
# Depends on the CSV file directly (NOT cell-count-analysis) so it does not
# trigger the MERFISH dataset download. Run 'make cell-count-analysis' once
# beforehand if cell_counts_by_taxonomy.csv is missing.
$(ROOT_TEMPLATES_DIR)/wmb_total_cell_counts.tsv: \
		$(SRC_DIR)/scripts/cell_counts/reports/cell_counts_and_proportions/cell_counts_by_taxonomy.csv \
		$(REPORTS_DIR)/cell_set_map.csv \
		$(SRC_DIR)/scripts/cell_counts/generate_total_cell_count_template.py \
		$(VENV_PYTHON)
	@echo "Generating WMB total cell count ROBOT template..."
	$(VENV_PYTHON) $(SRC_DIR)/scripts/cell_counts/generate_total_cell_count_template.py \
		--counts $< \
		--cell-set-map $(REPORTS_DIR)/cell_set_map.csv \
		--output $@

.PHONY: wmb-total-cell-count-template
wmb-total-cell-count-template: $(ROOT_TEMPLATES_DIR)/wmb_total_cell_counts.tsv

# Clean build artifacts
.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(REPORTS_DIR)
	rm -rf $(OWL_DIR)

# Clean everything including venv
.PHONY: distclean
distclean: clean
	rm -rf $(VENV_DIR)

# Test Neo4j connection
.PHONY: test-neo4j
test-neo4j: $(VENV_PYTHON)
	$(VENV_PYTHON) -c "from $(UTILS_DIR).neo4j_bolt_wrapper import Neo4jBoltQueryWrapper; \
		wrapper = Neo4jBoltQueryWrapper('bolt://$(NEO4J_HOST):$(NEO4J_PORT)', '$(NEO4J_USER)', '$(NEO4J_PASS)'); \
		print('Neo4j connection:', 'OK' if wrapper.test_connection() else 'FAILED')"

# Help target
.PHONY: help
help:
	@echo "Brain Cell Knowledge Graph Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all              - Build templates and generate reports"
	@echo "  owl              - Process ROBOT templates to OWL (requires ROBOT)"
	@echo "  templates        - Same as owl (legacy alias)"
	@echo "  mock-templates   - Mock template processing for testing"
	@echo "  reports          - Generate CSV reports from Cypher queries"
	@echo "  generate-templates - Generate templates from source data"
	@echo "  wmb-token-mapping - Generate WMB cell cluster token mapping reports"
	@echo "  wmb-additional-reports - Generate WMB hierarchical analysis reports"
	@echo "  wmb-robot-templates - Generate ROBOT templates from WMB mapping results"
	@echo "  cell-count-analysis - Generate cell count and proportion reports from CCF data"
	@echo "  taxonomy-matrices - Generate complete taxonomy × brain region matrices"
	@echo "  hierarchical-location-templates - Generate hierarchical location mapping ROBOT templates"
	@echo "  wmb-total-cell-count-template - Generate ROBOT template attaching total cell counts to WMB cell types"
	@echo "  detect-missing-namespaces - Find missing CURIE prefixes (ns{n}: patterns)"
	@echo "  suggest-missing-prefixes - Generate prefix suggestions via prefix commons"
	@echo "  update-neo4j-prefixes - Update Neo4j config from prefixes.json"
	@echo "  update-kg        - Execute knowledge graph update statements"
	@echo "  update-kg-dry-run - Show what KG updates would be executed"
	@echo "  test-neo4j       - Test Neo4j database connection"
	@echo "  clean            - Remove build artifacts"
	@echo "  distclean        - Remove all generated files including venv"
	@echo "  help             - Show this help message"
	@echo ""
	@echo "Configuration (override with make VAR=value):"
	@echo "  NEO4J_HOST=$(NEO4J_HOST)"
	@echo "  NEO4J_PORT=$(NEO4J_PORT)"
	@echo "  NEO4J_USER=$(NEO4J_USER)"
	@echo "  NEO4J_PASS=$(NEO4J_PASS)"
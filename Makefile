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
ZHUANG_LOCATION_OWL = \
	$(OWL_DIR)/cluster_location_mappings_zhuang.owl \
	$(OWL_DIR)/supertype_location_mappings_zhuang.owl \
	$(OWL_DIR)/subclass_location_mappings_zhuang.owl \
	$(OWL_DIR)/class_location_mappings_zhuang.owl \
	$(OWL_DIR)/neurotransmitter_location_mappings_zhuang.owl

ROOT_GENERATED_OWL = $(OWL_DIR)/wmb_total_cell_counts.owl $(ZHUANG_LOCATION_OWL) $(CCF_SPATIAL_OWL)

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

# Process ROBOT templates with prefixes. Output is OWL Functional Syntax (OFN)
# rather than ROBOT's default RDF/XML: same semantics, ~50% smaller on disk so
# templates with hundreds of thousands of edges (e.g. cluster_proximity) stay
# under GitHub's 100 MB per-file limit. The OWL API auto-detects serialization
# by content, so we keep the .owl extension and downstream loaders are
# unaffected.
$(OWL_DIR)/%.owl: $(TEMPLATES_DIR)/%.tsv $(UTILS_DIR)/prefixes.json | $(OWL_DIR)
	robot template \
		--add-prefixes $(UTILS_DIR)/prefixes.json \
		--template $< \
	      convert --format ofn --output $@

$(OWL_DIR)/%.owl: $(ROOT_TEMPLATES_DIR)/%.tsv $(UTILS_DIR)/prefixes.json | $(OWL_DIR)
	robot template \
		--add-prefixes $(UTILS_DIR)/prefixes.json \
		--template $< \
	      convert --format ofn --output $@

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
generate-templates: yao-location-templates zhuang-location-templates wmb-total-cell-count-template $(VENV_PYTHON)
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

# Source DOIs (informational; the unified-location script picks the right DOI
# from --dataset, so the recipes do not pass these directly).
YAO_DOI = doi:10.1038/s41586-023-06812-z
ZHUANG_DOI = doi:10.1038/s41586-023-06808-9

# Zhuang per-taxonomy matrices feed downstream reports (separate from the
# unified location templates, which read raw coordinates directly).
ZHUANG_MATRICES_DIR = $(SRC_DIR)/scripts/cell_counts/reports/zhuang_taxonomy_by_region_matrices

$(ZHUANG_MATRICES_DIR)/matrix_metadata.json: \
		$(SRC_DIR)/scripts/cell_counts/scripts/generate_zhuang_matrices.py \
		$(VENV_PYTHON)
	@echo "Generating Zhuang taxonomy × brain region matrices..."
	$(VENV_PYTHON) $(SRC_DIR)/scripts/cell_counts/scripts/generate_zhuang_matrices.py

.PHONY: zhuang-matrices
zhuang-matrices: $(ZHUANG_MATRICES_DIR)/matrix_metadata.json

# Per-taxonomy-node cell counts from the WMB-10X reference dataset
# (~4M cells, defines the WMB taxonomy). Sibling to cell_counts_by_taxonomy.csv
# (which is MERFISH-derived, ~2.4M spatially-resolved cells).
WMB_10X_COUNTS_CSV = $(SRC_DIR)/scripts/cell_counts/reports/cell_counts_and_proportions/cell_counts_by_taxonomy_10x.csv

$(WMB_10X_COUNTS_CSV): \
		$(SRC_DIR)/scripts/cell_counts/scripts/generate_10x_cell_count_csv.py \
		$(VENV_PYTHON)
	@echo "Generating WMB-10X cell counts (downloads ~1.4 GB on first run)..."
	$(VENV_PYTHON) $< --output $@

.PHONY: wmb-10x-cell-counts
wmb-10x-cell-counts: $(WMB_10X_COUNTS_CSV)

# Total cell count template (per WMB cell type, region-agnostic), sourced
# from the WMB-10X reference dataset. File-target rule so 'make owl'
# triggers regeneration if CSV inputs change.
$(ROOT_TEMPLATES_DIR)/wmb_total_cell_counts.tsv: \
		$(WMB_10X_COUNTS_CSV) \
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

# ---- CCF spatial proximity (MBA) ---------------------------------------------
# Region<->region adjacency from the painted Allen-CCF-2020 parcellation, and
# per-type "located near" stats from registered MERFISH coordinates. See
# src/scripts/ccf_spatial/ and the n2o: measure annotations in templates.

CCF_ATLAS           = n2o:CCF2020
CCF_ABA_CACHE       = $(SRC_DIR)/scripts/cell_counts/resources/aba_cache
CCF_ANNOTATION      = $(CCF_ABA_CACHE)/image_volumes/Allen-CCF-2020/20250331/annotation_25.nii.gz
CCF_MEMBERSHIP      = $(CCF_ABA_CACHE)/metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv
CCF_SPATIAL_SCRIPTS = $(SRC_DIR)/scripts/ccf_spatial/scripts
CCF_BRIDGE          = $(UTILS_DIR)/ccf_parcellation.py

# Yao WMB MERFISH per-cell metadata (used by both matrix and proximity pipelines).
# Path matches what generate_full_matrices.py expects; this rule provides an
# explicit dependency target so the proximity step doesn't silently use a stale
# or absent cache.
YAO_CCF_CSV = $(CCF_ABA_CACHE)/metadata/MERFISH-C57BL6J-638850-CCF/20231215/views/cell_metadata_with_parcellation_annotation.csv

$(CCF_ANNOTATION):
	@echo "Downloading Allen-CCF-2020 annotation_25.nii.gz (~3.6 MB)..."
	mkdir -p $(@D)
	curl -L -o $@ "https://allen-brain-cell-atlas.s3.us-west-2.amazonaws.com/image_volumes/Allen-CCF-2020/20250331/annotation_25.nii.gz"

$(CCF_MEMBERSHIP):
	@echo "Downloading Allen-CCF-2020 parcellation membership table..."
	mkdir -p $(@D)
	curl -L -o $@ "https://allen-brain-cell-atlas.s3.us-west-2.amazonaws.com/metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv"

$(YAO_CCF_CSV):
	@echo "Downloading Yao WMB cell metadata (large, multi-GB)..."
	mkdir -p $(@D)
	curl -L -o $@ "https://allen-brain-cell-atlas.s3.us-west-2.amazonaws.com/metadata/MERFISH-C57BL6J-638850-CCF/20231215/views/cell_metadata_with_parcellation_annotation.csv"

# Region adjacency: one script run produces division/structure/substructure
# together. Substructure tsv is the canonical target; the others depend on it.
CCF_ADJACENCY_TEMPLATES = \
	$(ROOT_TEMPLATES_DIR)/region_adjacency_substructure.tsv \
	$(ROOT_TEMPLATES_DIR)/region_adjacency_structure.tsv \
	$(ROOT_TEMPLATES_DIR)/region_adjacency_division.tsv

$(ROOT_TEMPLATES_DIR)/region_adjacency_substructure.tsv: \
		$(CCF_ANNOTATION) \
		$(CCF_MEMBERSHIP) \
		$(REPORTS_DIR)/mba_symbol_map.csv \
		$(CCF_SPATIAL_SCRIPTS)/compute_region_adjacency.py \
		$(CCF_BRIDGE) \
		$(VENV_PYTHON)
	@echo "Computing CCF region adjacency (all three levels)..."
	$(VENV_PYTHON) $(CCF_SPATIAL_SCRIPTS)/compute_region_adjacency.py \
		--annotation $(CCF_ANNOTATION) \
		--membership $(CCF_MEMBERSHIP) \
		--mba-map $(REPORTS_DIR)/mba_symbol_map.csv \
		--reports-dir $(REPORTS_DIR) \
		--templates-dir $(ROOT_TEMPLATES_DIR) \
		--atlas-curie $(CCF_ATLAS)

$(ROOT_TEMPLATES_DIR)/region_adjacency_structure.tsv \
$(ROOT_TEMPLATES_DIR)/region_adjacency_division.tsv: \
		$(ROOT_TEMPLATES_DIR)/region_adjacency_substructure.tsv

.PHONY: ccf-region-adjacency
ccf-region-adjacency: $(CCF_ADJACENCY_TEMPLATES)

# Unified location templates: one PCL:0010063 "has soma location" edge per
# (cell type, region) carrying cell_count, cell_ratio, and an in_or_near_100
# axiom annotation (counts cells inside the region OR within 100 um of its
# painted surface). All five taxonomy-level TSVs come out of a single script
# run per dataset; the cluster TSV is the canonical target and the other four
# empty-depend on it. The script picks the dataset DOI from --dataset.

YAO_LOCATION_TEMPLATES = \
	$(ROOT_TEMPLATES_DIR)/cluster_location_mappings.tsv \
	$(ROOT_TEMPLATES_DIR)/supertype_location_mappings.tsv \
	$(ROOT_TEMPLATES_DIR)/subclass_location_mappings.tsv \
	$(ROOT_TEMPLATES_DIR)/class_location_mappings.tsv \
	$(ROOT_TEMPLATES_DIR)/neurotransmitter_location_mappings.tsv

$(ROOT_TEMPLATES_DIR)/cluster_location_mappings.tsv: \
		$(CCF_ANNOTATION) \
		$(CCF_MEMBERSHIP) \
		$(REPORTS_DIR)/mba_symbol_map.csv \
		$(REPORTS_DIR)/cell_set_map.csv \
		$(REPORTS_DIR)/mba_ccf_membership.csv \
		$(YAO_CCF_CSV) \
		$(CCF_SPATIAL_SCRIPTS)/compute_unified_location_templates.py \
		$(CCF_BRIDGE) \
		$(VENV_PYTHON)
	@echo "Generating Yao unified location templates (all five taxonomy levels)..."
	$(VENV_PYTHON) $(CCF_SPATIAL_SCRIPTS)/compute_unified_location_templates.py \
		--dataset yao \
		--annotation $(CCF_ANNOTATION) \
		--membership $(CCF_MEMBERSHIP) \
		--mba-map $(REPORTS_DIR)/mba_symbol_map.csv \
		--cell-set-map $(REPORTS_DIR)/cell_set_map.csv \
		--yao-csv $(YAO_CCF_CSV) \
		--reports-dir $(REPORTS_DIR) \
		--templates-dir $(ROOT_TEMPLATES_DIR) \
		--atlas-curie $(CCF_ATLAS) \
		--mba-membership-csv $(REPORTS_DIR)/mba_ccf_membership.csv

$(ROOT_TEMPLATES_DIR)/supertype_location_mappings.tsv \
$(ROOT_TEMPLATES_DIR)/subclass_location_mappings.tsv \
$(ROOT_TEMPLATES_DIR)/class_location_mappings.tsv \
$(ROOT_TEMPLATES_DIR)/neurotransmitter_location_mappings.tsv: \
		$(ROOT_TEMPLATES_DIR)/cluster_location_mappings.tsv

.PHONY: yao-location-templates
yao-location-templates: $(YAO_LOCATION_TEMPLATES)

ZHUANG_LOCATION_TEMPLATES = \
	$(ROOT_TEMPLATES_DIR)/cluster_location_mappings_zhuang.tsv \
	$(ROOT_TEMPLATES_DIR)/supertype_location_mappings_zhuang.tsv \
	$(ROOT_TEMPLATES_DIR)/subclass_location_mappings_zhuang.tsv \
	$(ROOT_TEMPLATES_DIR)/class_location_mappings_zhuang.tsv \
	$(ROOT_TEMPLATES_DIR)/neurotransmitter_location_mappings_zhuang.tsv

$(ROOT_TEMPLATES_DIR)/cluster_location_mappings_zhuang.tsv: \
		$(CCF_ANNOTATION) \
		$(CCF_MEMBERSHIP) \
		$(REPORTS_DIR)/mba_symbol_map.csv \
		$(REPORTS_DIR)/cell_set_map.csv \
		$(REPORTS_DIR)/mba_ccf_membership.csv \
		$(CCF_SPATIAL_SCRIPTS)/compute_unified_location_templates.py \
		$(CCF_BRIDGE) \
		$(VENV_PYTHON)
	@echo "Generating Zhuang unified location templates (all five taxonomy levels)..."
	$(VENV_PYTHON) $(CCF_SPATIAL_SCRIPTS)/compute_unified_location_templates.py \
		--dataset zhuang \
		--annotation $(CCF_ANNOTATION) \
		--membership $(CCF_MEMBERSHIP) \
		--mba-map $(REPORTS_DIR)/mba_symbol_map.csv \
		--cell-set-map $(REPORTS_DIR)/cell_set_map.csv \
		--aba-cache $(CCF_ABA_CACHE) \
		--reports-dir $(REPORTS_DIR) \
		--templates-dir $(ROOT_TEMPLATES_DIR) \
		--atlas-curie $(CCF_ATLAS) \
		--mba-membership-csv $(REPORTS_DIR)/mba_ccf_membership.csv

$(ROOT_TEMPLATES_DIR)/supertype_location_mappings_zhuang.tsv \
$(ROOT_TEMPLATES_DIR)/subclass_location_mappings_zhuang.tsv \
$(ROOT_TEMPLATES_DIR)/class_location_mappings_zhuang.tsv \
$(ROOT_TEMPLATES_DIR)/neurotransmitter_location_mappings_zhuang.tsv: \
		$(ROOT_TEMPLATES_DIR)/cluster_location_mappings_zhuang.tsv

.PHONY: zhuang-location-templates
zhuang-location-templates: $(ZHUANG_LOCATION_TEMPLATES)

# Per-MBA-term atlas-membership templates declaring which MBA terms are
# directly painted in CCF 2020 (with level), have descendants painted
# (with coverage), or have no CCF representation at all. Drives the
# downstream agent's three-way "read directly / sum descendants / no
# signal" decision.
MBA_ATLAS_MEMBERSHIP_TEMPLATES = \
	$(ROOT_TEMPLATES_DIR)/mba_painted_in_ccf2020.tsv \
	$(ROOT_TEMPLATES_DIR)/mba_descendants_painted_in_ccf2020.tsv \
	$(ROOT_TEMPLATES_DIR)/mba_not_represented_in_ccf2020.tsv

$(ROOT_TEMPLATES_DIR)/mba_painted_in_ccf2020.tsv: \
		$(REPORTS_DIR)/mba_ccf_membership.csv \
		$(CCF_SPATIAL_SCRIPTS)/generate_anatomy_atlas_membership_templates.py \
		$(VENV_PYTHON)
	@echo "Generating MBA atlas-membership templates (painted / descendants_painted / not_represented)..."
	$(VENV_PYTHON) $(CCF_SPATIAL_SCRIPTS)/generate_anatomy_atlas_membership_templates.py \
		--membership-csv $(REPORTS_DIR)/mba_ccf_membership.csv \
		--atlas-curie $(CCF_ATLAS) \
		--ontology-prefix mba \
		--atlas-prefix ccf2020 \
		--templates-dir $(ROOT_TEMPLATES_DIR)

$(ROOT_TEMPLATES_DIR)/mba_descendants_painted_in_ccf2020.tsv \
$(ROOT_TEMPLATES_DIR)/mba_not_represented_in_ccf2020.tsv: \
		$(ROOT_TEMPLATES_DIR)/mba_painted_in_ccf2020.tsv

.PHONY: mba-atlas-membership-templates
mba-atlas-membership-templates: $(MBA_ATLAS_MEMBERSHIP_TEMPLATES)

.PHONY: ccf-spatial
ccf-spatial: ccf-region-adjacency yao-location-templates zhuang-location-templates \
	mba-atlas-membership-templates $(ROOT_TEMPLATES_DIR)/atlases.tsv

# CCF spatial OWL outputs (built from templates above via the existing
# $(OWL_DIR)/%.owl: $(ROOT_TEMPLATES_DIR)/%.tsv robot template rule).
CCF_SPATIAL_OWL = \
	$(OWL_DIR)/region_adjacency_division.owl \
	$(OWL_DIR)/region_adjacency_structure.owl \
	$(OWL_DIR)/region_adjacency_substructure.owl \
	$(OWL_DIR)/atlases.owl \
	$(OWL_DIR)/mba_painted_in_ccf2020.owl \
	$(OWL_DIR)/mba_descendants_painted_in_ccf2020.owl \
	$(OWL_DIR)/mba_not_represented_in_ccf2020.owl

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
	@echo "  yao-location-templates - Generate Yao unified location templates (PCL:0010063 with in_or_near_100)"
	@echo "  zhuang-matrices - Generate Zhuang taxonomy x region matrices (downloads ~3.5 GB on first run)"
	@echo "  zhuang-location-templates - Generate Zhuang unified location templates (PCL:0010063 with in_or_near_100)"
	@echo "  ccf-region-adjacency - Generate CCF region adjacency templates (all three levels)"
	@echo "  ccf-spatial - Generate adjacency + unified location templates (yao + zhuang)"
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
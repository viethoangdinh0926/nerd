INPUT_DIR ?= .

# Output directory
ROOT_OUTPUT_DIR ?= ./graph_output

# Script name
SCRIPT = ../graph_visualizer/kg_generator.py

# Root node name
ROOT_NODE_NAME = "Linux Kernel Init"

# Default target
.PHONY: graph
graph:
	@echo "Generating knowledge graph..."
	python3 -m venv .venv
	.venv/bin/python -m pip install networkx
	.venv/bin/python $(SCRIPT) $(INPUT_DIR) --root $(ROOT_NODE_NAME) --output-dir $(ROOT_OUTPUT_DIR) --depth 0
	@echo "Done. Open $(ROOT_OUTPUT_DIR)/graph.html"

# Clean output
.PHONY: clean
clean:
	@echo "Cleaning output..."
	rm -rf $(ROOT_OUTPUT_DIR)

# Rebuild graph (clean + generate)
.PHONY: rebuild
rebuild: clean graph

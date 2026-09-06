INPUT_DIR ?= .

# Output directory
ROOT_OUTPUT_DIR ?= ./graph_output

# Script name
SCRIPT = ../graph_visualizer/kg_generator.py

# Root node name
ROOT_NODE_NAME = "Nguyen Van Vinh & Vu Thi Hien"

# Default target
.PHONY: graph
graph:
	@echo "Generating knowledge graph..."
	uv run --native-tls --with networkx $(SCRIPT) $(INPUT_DIR) --root $(ROOT_NODE_NAME) --output-dir $(ROOT_OUTPUT_DIR) --depth 0
	@echo "Done. Open $(ROOT_OUTPUT_DIR)/graph.html"

# Start the FastAPI server
.PHONY: server
server:
	@echo "Starting FastAPI server..."
	uv run --native-tls server.py

# Generate graph and start server
.PHONY: run
run: graph server

# Clean output
.PHONY: clean
clean:
	@echo "Cleaning output..."
	rm -rf $(ROOT_OUTPUT_DIR)

# Rebuild graph (clean + generate)
.PHONY: rebuild
rebuild: clean graph

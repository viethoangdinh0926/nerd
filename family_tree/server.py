#!/usr/bin/env python3
"""
FastAPI server for family tree graph visualization.
Serves the graph_output folder and handles graph.graphml updates.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from pathlib import Path
import os

app = FastAPI(title="Family Tree Graph Server")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the graph_output directory
graph_output_dir = Path(__file__).parent / "graph_output"
if not graph_output_dir.exists():
    graph_output_dir.mkdir(parents=True, exist_ok=True)

# Mount the graph_output directory as static files
app.mount("/static", StaticFiles(directory=str(graph_output_dir)), name="static")

@app.get("/")
async def read_index():
    """Serve the index.html file."""
    index_file = graph_output_dir / "graph.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "graph.html not found"}

@app.put("/graph.graphml")
async def save_graphml(content: str = Body(..., media_type="text/plain")):
    """
    Handle PUT requests to save graph.graphml file.
    This allows the web interface to save changes directly to the file.
    """
    graphml_file = graph_output_dir / "graph.graphml"
    
    try:
        # Write the content to the graph.graphml file
        with open(graphml_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "message": "graph.graphml saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save graph.graphml: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "graph_output_dir": str(graph_output_dir)}

def main():
    import uvicorn
    
    print(f"Starting Family Tree Graph Server...")
    print(f"Serving files from: {graph_output_dir}")
    print(f"Open your browser to: http://localhost:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()

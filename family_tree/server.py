#!/usr/bin/env python3
"""
FastAPI server for family tree graph visualization.
Serves the graph_output folder and handles graph.graphml updates.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from pathlib import Path
from typing import Optional
import asyncio
import hashlib
import os
import shutil

app = FastAPI(title="Family Tree Graph Server")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)

# Get the graph_output directory
graph_output_dir = Path(__file__).parent / "graph_output"
if not graph_output_dir.exists():
    graph_output_dir.mkdir(parents=True, exist_ok=True)

# Mount the graph_output directory as static files with cache control
app.mount("/static", StaticFiles(directory=str(graph_output_dir)), name="static")

# Ensure images directory exists
images_dir = graph_output_dir / "images"
if not images_dir.exists():
    images_dir.mkdir(parents=True, exist_ok=True)

@app.get("/")
async def read_index():
    """Serve the index.html file."""
    index_file = graph_output_dir / "graph.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "graph.html not found"}

# Serializes the read-compare-write cycle on graph.graphml so two concurrent
# writers can never both pass the version check.
graphml_lock = asyncio.Lock()


def graphml_etag(graphml_file: Path) -> str:
    """Content hash of graph.graphml, used as its optimistic-locking version."""
    if not graphml_file.exists():
        return '"empty"'
    digest = hashlib.sha256(graphml_file.read_bytes()).hexdigest()
    return f'"{digest[:32]}"'


@app.get("/graph.graphml")
async def read_graphml():
    """Serve the graph.graphml file along with its current version (ETag)."""
    graphml_file = graph_output_dir / "graph.graphml"
    if not graphml_file.exists():
        return {"error": "graph.graphml not found"}
    async with graphml_lock:
        content = graphml_file.read_bytes()
        etag = graphml_etag(graphml_file)
    return Response(
        content=content,
        media_type="application/xml",
        headers={"ETag": etag, "Cache-Control": "no-store"},
    )

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    Handle image uploads for node metadata.
    Accepts JPEG or PNG files up to 10MB.
    """
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed")
    
    # Validate file size (10MB = 10 * 1024 * 1024 bytes)
    MAX_SIZE = 10 * 1024 * 1024
    file_content = await file.read()
    if len(file_content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    
    # Generate unique filename
    import uuid
    file_extension = ".jpg" if file.content_type == "image/jpeg" else ".png"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = images_dir / unique_filename
    
    # Save the file
    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return {
            "status": "success",
            "filename": unique_filename,
            "url": f"/static/images/{unique_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

@app.delete("/delete-image")
async def delete_image(image_url: str = Body(..., embed=True)):
    """
    Delete an image file from the images directory.
    """
    try:
        # Extract filename from URL
        # URL format: /static/images/filename.jpg
        if not image_url.startswith("/static/images/"):
            raise HTTPException(status_code=400, detail="Invalid image URL format")
        
        filename = image_url.split("/")[-1]
        file_path = images_dir / filename
        
        if file_path.exists():
            file_path.unlink()
            return {"status": "success", "message": f"Deleted {filename}"}
        else:
            return {"status": "success", "message": f"File {filename} not found, nothing to delete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete image: {str(e)}")

@app.put("/graph.graphml")
async def save_graphml(
    content: str = Body(..., media_type="text/plain"),
    if_match: Optional[str] = Header(None),
):
    """
    Handle PUT requests to save graph.graphml file.

    Uses optimistic locking: the client echoes back the ETag it last read via
    If-Match. If the file changed in the meantime the write is rejected with
    409 so the client can reload or deliberately overwrite. `If-Match: *`
    forces an unconditional write.
    """
    graphml_file = graph_output_dir / "graph.graphml"

    async with graphml_lock:
        current_etag = graphml_etag(graphml_file)

        if if_match and if_match != "*" and if_match != current_etag:
            print(f"Version conflict: client={if_match}, server={current_etag}")
            raise HTTPException(
                status_code=409,
                detail="graph.graphml was modified by someone else since you loaded it.",
                headers={"ETag": current_etag},
            )

        try:
            # Write to a temp file and rename so readers never see a partial file.
            temp_file = graphml_file.with_suffix(".graphml.tmp")
            temp_file.write_text(content, encoding="utf-8")
            os.replace(temp_file, graphml_file)
            new_etag = graphml_etag(graphml_file)
        except Exception as e:
            print(f"Error saving graph.graphml: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save graph.graphml: {str(e)}")

    print(f"Successfully saved graph.graphml ({len(content)} bytes, etag {new_etag})")
    return Response(
        content='{"status": "success", "message": "graph.graphml saved successfully"}',
        media_type="application/json",
        headers={"ETag": new_etag},
    )

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

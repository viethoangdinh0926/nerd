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
import zipfile
import io

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

# Get the graph directory
graph_output_dir = Path(__file__).parent / "graph"
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


def parse_name_parts(name: str, summary: str = "") -> tuple:
    """
    Parse a full name into (last_name, middle_name, first_name).
    If summary is provided, try to extract name details from it first.
    """
    if summary:
        last, middle, first = parse_name_from_summary(summary)
        if last and first:
            return (last, middle, first)

    # Fallback to parsing the name string
    parts = name.strip().split()
    if len(parts) == 0:
        return ("", "", "")
    elif len(parts) == 1:
        return (parts[0], "", "")
    elif len(parts) == 2:
        return (parts[0], "", parts[1])
    else:
        return (parts[0], " ".join(parts[1:-1]), parts[-1])


def parse_name_from_summary(summary_text: str) -> tuple:
    """
    Parse last name, middle name, and first name from summary content.
    Expected format in summary:
    - **Last Name:** value
    - **Middle Name:** value
    - **First Name:** value
    """
    import re

    last_name = ""
    middle_name = ""
    first_name = ""

    # Parse Last Name
    last_match = re.search(r'\*\*Last Name:\*\*\s*(.+?)(?:\n|$)', summary_text)
    if last_match:
        last_name = last_match.group(1).strip()

    # Parse Middle Name
    middle_match = re.search(r'\*\*Middle Name:\*\*\s*(.+?)(?:\n|$)', summary_text)
    if middle_match:
        middle_name = middle_match.group(1).strip()

    # Parse First Name
    first_match = re.search(r'\*\*First Name:\*\*\s*(.+?)(?:\n|$)', summary_text)
    if first_match:
        first_name = first_match.group(1).strip()

    return last_name, middle_name, first_name


def create_graph_zip() -> tuple:
    """
    Create a zip file containing both graph.html and graph.graphml files.
    
    Returns a tuple of (zip_content, error_message).
    If error_message is not None, zip_content will be None.
    """
    html_file = graph_output_dir / "graph.html"
    graphml_file = graph_output_dir / "graph.graphml"
    
    # Check if both files exist
    if not html_file.exists():
        return None, f"graph.html not found in {graph_output_dir}"
    if not graphml_file.exists():
        return None, f"graph.graphml not found in {graph_output_dir}"
    
    try:
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add graph.html to the zip
            zipf.write(html_file, 'graph.html')
            
            # Add graph.graphml to the zip
            zipf.write(graphml_file, 'graph.graphml')
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue(), None
        
    except Exception as e:
        return None, f"Failed to create zip file: {str(e)}"


@app.get("/export.zip")
async def export_zip():
    """
    Export the current graph files as a zip archive containing both graph.html and graph.graphml.
    """
    try:
        zip_content, error_message = create_graph_zip()
        if error_message:
            # Return error as plain text for display in browser
            return Response(
                content=error_message,
                media_type="text/plain",
                status_code=400
            )
        print(f"Zip export: {len(zip_content)} bytes")
        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=family_tree.zip"},
        )
    except Exception as e:
        import traceback
        print(f"Error exporting zip: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to export zip: {str(e)}")

def main():
    import uvicorn
    
    print(f"Starting Family Tree Graph Server...")
    print(f"Serving files from: {graph_output_dir}")
    print(f"Open your browser to: http://localhost:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()

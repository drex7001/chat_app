from fastapi import APIRouter, File, UploadFile, HTTPException
import shutil
import os
import uuid
from typing import List

router = APIRouter()

UPLOAD_DIR = "app/static/uploads"

@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file and get a URL back.
    For local dev, returns http://localhost:8000/static/uploads/...
    """
    try:
        # Create dir if not exists (safety check)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # Generate safe filename
        ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
        filename = f"{uuid.uuid4()}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return URL (Hardcoded localhost for dev, should be config driven)
        # TODO: Use Request.base_url to make it dynamic
        url = f"http://localhost:8000/static/uploads/{filename}"
        
        return {"url": url, "filename": filename, "content_type": file.content_type}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

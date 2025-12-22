from fastapi import APIRouter, File, UploadFile, HTTPException
import shutil
import os
import uuid
from typing import List
import io

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


@router.post("/policy-document")
async def upload_policy_document(file: UploadFile = File(...)):
    """
    Upload a policy document file and extract text content.
    Supports: .txt, .md, .pdf, .docx
    Returns: {name, content, original_filename}
    """
    try:
        # Get file extension
        filename = file.filename or "document"
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        
        # Read file content
        content_bytes = await file.read()
        
        # Extract text based on file type
        if ext in ["txt", "md"]:
            # Plain text or markdown - direct read
            text_content = content_bytes.decode("utf-8", errors="ignore")
            
        elif ext == "pdf":
            # PDF extraction
            try:
                from PyPDF2 import PdfReader
                pdf_file = io.BytesIO(content_bytes)
                reader = PdfReader(pdf_file)
                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
                text_content = "\n".join(text_parts)
            except Exception as pdf_error:
                raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(pdf_error)}")
                
        elif ext in ["docx", "doc"]:
            # Word document extraction
            try:
                from docx import Document
                doc_file = io.BytesIO(content_bytes)
                doc = Document(doc_file)
                text_parts = [paragraph.text for paragraph in doc.paragraphs]
                text_content = "\n".join(text_parts)
            except Exception as docx_error:
                raise HTTPException(status_code=400, detail=f"Failed to parse Word document: {str(docx_error)}")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}. Supported: .txt, .md, .pdf, .docx")
        
        # Clean up the filename for display
        display_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        
        return {
            "name": display_name,
            "content": text_content.strip(),
            "original_filename": filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio file using OpenAI Whisper.
    Returns: { "text": "transcribed text", "language": "english" }
    """
    try:
        from openai import OpenAI
        client = OpenAI() # Uses OPENAI_API_KEY from env
        
        # 1. Create temp file
        ext = file.filename.split(".")[-1] if "." in file.filename else "mp3"
        temp_filename = f"temp_{uuid.uuid4()}.{ext}"
        
        # 2. Write content
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        try:
            # 3. Transcribe
            with open(temp_filename, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format="json"
                )
            
            return {"text": transcript.text}
            
        finally:
            # 4. Cleanup
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
    except Exception as e:
        print(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

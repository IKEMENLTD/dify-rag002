from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List
import os
import shutil
from pathlib import Path
from services.data_ingestion import data_ingestion_service
from core.config import settings
from database.connection import supabase
import uuid
from datetime import datetime

router = APIRouter()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True)

@router.post("/files")
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Upload and process files"""
    try:
        results = []
        
        for file in files:
            # Validate file size
            if file.size and file.size > settings.max_file_size:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "message": f"File too large. Max size: {settings.max_file_size} bytes"
                })
                continue
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_extension = Path(file.filename).suffix
            unique_filename = f"{file_id}{file_extension}"
            file_path = os.path.join(settings.upload_dir, unique_filename)
            
            try:
                # Save file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # Record file upload
                upload_record = {
                    "filename": unique_filename,
                    "original_filename": file.filename,
                    "file_type": file.content_type,
                    "file_size": file.size or 0,
                    "status": "pending"
                }
                
                supabase.table("file_uploads").insert(upload_record).execute()
                
                # Process file in background
                background_tasks.add_task(
                    process_file_background,
                    {
                        "file_path": file_path,
                        "filename": unique_filename,
                        "file_type": file.content_type,
                        "file_size": file.size or 0
                    }
                )
                
                results.append({
                    "filename": file.filename,
                    "file_id": unique_filename,
                    "status": "uploaded",
                    "message": "File uploaded and processing started"
                })
                
            except Exception as file_error:
                # Clean up file if processing failed
                if os.path.exists(file_path):
                    os.unlink(file_path)
                
                results.append({
                    "filename": file.filename,
                    "status": "error", 
                    "message": f"Upload failed: {str(file_error)}"
                })
        
        return {"results": results}
        
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@router.get("/files")
async def list_uploaded_files(limit: int = 50):
    """List uploaded files with their processing status"""
    try:
        response = supabase.table("file_uploads").select(
            "filename, original_filename, file_type, file_size, status, created_at, updated_at"
        ).order("created_at", desc=True).limit(limit).execute()
        
        return response.data
        
    except Exception as e:
        print(f"List files error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")

@router.get("/files/{file_id}/status")
async def get_file_status(file_id: str):
    """Get processing status of a specific file"""
    try:
        response = supabase.table("file_uploads").select("*").eq("filename", file_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="File not found")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get file status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file status")

@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete an uploaded file and associated document"""
    try:
        # Get file info
        file_response = supabase.table("file_uploads").select("*").eq("filename", file_id).execute()
        
        if not file_response.data:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_info = file_response.data[0]
        
        # Delete document if exists
        if file_info.get("document_id"):
            supabase.table("documents").delete().eq("id", file_info["document_id"]).execute()
        
        # Delete file record
        supabase.table("file_uploads").delete().eq("filename", file_id).execute()
        
        # Delete physical file
        file_path = os.path.join(settings.upload_dir, file_id)
        if os.path.exists(file_path):
            os.unlink(file_path)
        
        return {"message": "File deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete file error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")

async def process_file_background(file_data: dict):
    """Background task to process uploaded file"""
    try:
        # Update status to processing
        supabase.table("file_uploads").update({
            "status": "processing",
            "updated_at": datetime.now().isoformat()
        }).eq("filename", file_data["filename"]).execute()
        
        # Process file
        success = await data_ingestion_service.process_uploaded_file(file_data)
        
        # Update final status
        if success:
            supabase.table("file_uploads").update({
                "status": "completed",
                "updated_at": datetime.now().isoformat()
            }).eq("filename", file_data["filename"]).execute()
        else:
            supabase.table("file_uploads").update({
                "status": "failed",
                "updated_at": datetime.now().isoformat()
            }).eq("filename", file_data["filename"]).execute()
            
    except Exception as e:
        print(f"Background file processing error: {e}")
        # Update status to failed
        try:
            supabase.table("file_uploads").update({
                "status": "failed",
                "updated_at": datetime.now().isoformat()
            }).eq("filename", file_data["filename"]).execute()
        except:
            pass
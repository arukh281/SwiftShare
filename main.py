from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime, timedelta, timezone
import random
import string
import io
import zipfile
from io import BytesIO
from s3_utils import s3_manager
from encryption_utils import encryption_manager
import base64

app = FastAPI()

# Mount the static directory to serve CSS and JavaScript files
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory database for file metadata
files_db = {}

def generate_id(prefix: str = "", length: int = 4) -> str:
    """Generate a unique ID with a prefix and a random string."""
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{random_part}"

def upload_to_s3(file: UploadFile, expiration: int) -> dict:
    """Upload a file to S3 and return its metadata."""
    file_id = generate_id(prefix="S3-", length=6)
    file_key = f"{file_id}/{file.filename}"

    # Read file content
    file_content = file.file.read()
    
    # Encrypt the file content
    encrypted_data, iv, tag = encryption_manager.encrypt_data(file_content)
    
    # Combine encrypted data, IV, and tag
    combined_data = iv + tag + encrypted_data
    
    # Upload encrypted file to S3 with metadata
    metadata = {
        "expiration": str(expiration),
        "original_filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "encryption_iv": base64.b64encode(iv).decode(),
        "encryption_tag": base64.b64encode(tag).decode()
    }
    s3_manager.upload_file(combined_data, file_key, metadata)

    # Store metadata in the in-memory database with timezone-aware datetime
    expiration_time = datetime.now(timezone.utc) + timedelta(seconds=expiration)
    files_db[file_id] = {
        "key": file_key,
        "filename": file.filename,
        "expires_at": expiration_time,
    }

    return {"file_id": file_id, "message": "File uploaded successfully!"}

@app.post("/upload/")
async def upload(
    files: list[UploadFile] = File(default=[]),  # Changed from File(...)
    expiration_policy: str = Form("delete_after_first_download"),
    text_content: str = Form(None),
):
    """Handle file uploads with expiration policies."""
    uploads = []
    expiration = 0

    # Determine expiration time based on policy
    if expiration_policy == "delete_after_first_download":
        expiration = 300  # 5 minutes
    elif expiration_policy == "store_1_hour":
        expiration = 3600  # 1 hour
    elif expiration_policy == "store_1_day":
        expiration = 86400  # 1 day
    else:
        raise HTTPException(status_code=400, detail="Invalid expiration policy")

    # Case 1: Only text content
    if text_content and (not files or (len(files) == 1 and not files[0].filename)):
        # Create text file in memory
        text_file = UploadFile(
            filename="shared-text.txt",
            file=BytesIO(text_content.encode()),
        )
        uploads.append(upload_to_s3(text_file, expiration))

    # Case 2: Single file, no text
    elif len(files) == 1 and files[0].filename and not text_content:
        file = files[0]
        uploads.append(upload_to_s3(file, expiration))

    # Case 3 & 4: Multiple files or files with text
    elif len(files) > 0:
        # Create a ZIP file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            # Add text content if present
            if text_content:
                zipf.writestr("shared-text.txt", text_content)
            
            # Add all files
            for file in files:
                if file.filename:  # Skip empty files
                    file_content = await file.read()
                    zipf.writestr(file.filename, file_content)
                    await file.seek(0)
        
        zip_buffer.seek(0)

        # Upload the ZIP file to S3
        file_id = generate_id(prefix="ZIP-", length=6)
        zip_file_key = f"{file_id}/uploaded_files.zip"
        
        # Get ZIP content
        zip_content = zip_buffer.getvalue()
        
        # Encrypt the ZIP content
        encrypted_data, iv, tag = encryption_manager.encrypt_data(zip_content)
        
        # Combine encrypted data, IV, and tag
        combined_data = iv + tag + encrypted_data
        
        # Upload encrypted ZIP file with metadata
        metadata = {
            "expiration": str(expiration),
            "original_filename": "uploaded_files.zip",
            "content_type": "application/zip",
            "encryption_iv": base64.b64encode(iv).decode(),
            "encryption_tag": base64.b64encode(tag).decode()
        }
        s3_manager.upload_file(combined_data, zip_file_key, metadata)

        # Store metadata for the ZIP file
        expiration_time = datetime.now(timezone.utc) + timedelta(seconds=expiration)
        files_db[file_id] = {
            "key": zip_file_key,
            "filename": "uploaded_files.zip",
            "expires_at": expiration_time,
        }
        uploads.append({"file_id": file_id, "message": "ZIP file uploaded successfully!"})

    return {"uploads": uploads}

@app.get("/download/{file_id}")
async def download(file_id: str):
    """Download a file with proper decryption and content type handling."""
    try:
        print(f"Attempting to download file with ID: {file_id}")
        file_data = files_db.get(file_id)
        if not file_data:
            print(f"File ID {file_id} not found in files_db")
            return JSONResponse(
                status_code=404,
                content={"error": "File not found"},
                headers={"Content-Type": "application/json"}
            )

        # Check if the file has expired
        current_time = datetime.now(timezone.utc)
        if current_time > file_data["expires_at"]:
            print(f"File {file_id} has expired")
            try:
                s3_manager.delete_file(file_data["key"])
                del files_db[file_id]
            except Exception as e:
                print(f"Error deleting expired file: {str(e)}")
            return JSONResponse(
                status_code=410,
                content={"error": "File has expired"},
                headers={"Content-Type": "application/json"}
            )

        print(f"Downloading file from S3 with key: {file_data['key']}")
        # Get file from S3
        encrypted_data = s3_manager.download_file(file_data["key"])
        print("Successfully downloaded encrypted data from S3")
        
        # Get encryption metadata
        print("Retrieving file metadata")
        metadata = s3_manager.get_file_metadata(file_data["key"])
        iv = base64.b64decode(metadata["encryption_iv"])
        tag = base64.b64decode(metadata["encryption_tag"])
        
        # Extract the encrypted data (after IV and tag)
        encrypted_content = encrypted_data[28:]  # 12 bytes IV + 16 bytes tag
        
        # Decrypt the file content
        print("Decrypting file content")
        file_content = encryption_manager.decrypt_data(encrypted_content, iv, tag)
        print("Successfully decrypted file content")
        
        file_name = file_data["filename"]
        print(f"Processing file: {file_name}")

        # Handle different file types
        if file_name == "shared-text.txt":
            # Text content preview
            content = file_content.decode('utf-8')
            # Only delete if expiration is within 5 minutes (delete_after_first_download policy)
            if (file_data["expires_at"] - current_time) <= timedelta(seconds=300):
                try:
                    s3_manager.delete_file(file_data["key"])
                    del files_db[file_id]
                except Exception as e:
                    print(f"Error deleting file after download: {str(e)}")
            return JSONResponse(
                content={
                    "type": "text",
                    "content": content,
                    "filename": file_name
                },
                headers={"Content-Type": "application/json"}
            )
        elif file_name == "uploaded_files.zip":
            # Handle ZIP file
            zip_buffer = BytesIO(file_content)
            with zipfile.ZipFile(zip_buffer, "r") as zipf:
                # List files in ZIP
                file_list = zipf.namelist()
                if len(file_list) == 1 and file_list[0] == "shared-text.txt":
                    # If only text file in ZIP, return its content
                    content = zipf.read(file_list[0]).decode('utf-8')
                    if (file_data["expires_at"] - current_time) <= timedelta(seconds=300):
                        try:
                            s3_manager.delete_file(file_data["key"])
                            del files_db[file_id]
                        except Exception as e:
                            print(f"Error deleting file after download: {str(e)}")
                    return JSONResponse(
                        content={"content": content},
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    # Return ZIP file for download
                    if (file_data["expires_at"] - current_time) <= timedelta(seconds=300):
                        try:
                            s3_manager.delete_file(file_data["key"])
                            del files_db[file_id]
                        except Exception as e:
                            print(f"Error deleting file after download: {str(e)}")
                    return StreamingResponse(
                        BytesIO(file_content),
                        media_type="application/zip",
                        headers={
                            "Content-Disposition": f'attachment; filename="{file_name}"',
                            "Content-Type": "application/zip"
                        }
                    )
        else:
            # Handle regular file download
            content_type = metadata.get("content_type", "application/octet-stream")
            if (file_data["expires_at"] - current_time) <= timedelta(seconds=300):
                try:
                    s3_manager.delete_file(file_data["key"])
                    del files_db[file_id]
                except Exception as e:
                    print(f"Error deleting file after download: {str(e)}")
            return StreamingResponse(
                BytesIO(file_content),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{file_name}"',
                    "Content-Type": content_type
                }
            )

    except Exception as e:
        print(f"Error in download endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error downloading file: {str(e)}"},
            headers={"Content-Type": "application/json"}
        )

@app.get("/")
async def homepage():
    """Serve the homepage."""
    return FileResponse(Path(__file__).parent / "index.html")


from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv
import boto3
import os
from datetime import datetime, timedelta, timezone
import random
import string
import io
import zipfile
from io import BytesIO

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

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

    # Upload file to S3
    s3_client.upload_fileobj(file.file, S3_BUCKET_NAME, file_key)

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
        s3_client.upload_fileobj(zip_buffer, S3_BUCKET_NAME, zip_file_key)

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
    """Return the file directly instead of a pre-signed URL."""
    try:
        file_data = files_db.get(file_id)
        if not file_data:
            return JSONResponse(
                status_code=404,
                content={"error": "File not found"},
                headers={"Content-Type": "application/json"}
            )

        # Check if the file has expired
        current_time = datetime.now(timezone.utc)
        if current_time > file_data["expires_at"]:
            try:
                s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=file_data["key"])
                del files_db[file_id]
            except:
                pass
            return JSONResponse(
                status_code=410,
                content={"error": "File has expired"},
                headers={"Content-Type": "application/json"}
            )

        # Get file from S3
        s3_response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=file_data["key"])
        file_stream = s3_response["Body"]
        file_name = file_data["filename"]

        # If it's a text file, return content for preview
        if file_name == "shared-text.txt":
            content = file_stream.read().decode('utf-8')
            # Only delete if expiration is within 5 minutes (delete_after_first_download policy)
            if (file_data["expires_at"] - current_time) <= timedelta(seconds=300):
                try:
                    s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=file_data["key"])
                    del files_db[file_id]
                except:
                    pass
            return JSONResponse(
                content={
                    "type": "text",
                    "content": content,
                    "filename": file_name
                }
            )

        # For non-text files, check if it should be deleted after download
        if (file_data["expires_at"] - current_time) <= timedelta(seconds=300):
            try:
                s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=file_data["key"])
                del files_db[file_id]
            except:
                pass

        return StreamingResponse(
            file_stream,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Content-Type": "application/octet-stream",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        print(f"Download error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Error downloading file"},
            headers={"Content-Type": "application/json"}
        )

@app.get("/")
async def homepage():
    """Serve the homepage."""
    return FileResponse(Path(__file__).parent / "index.html")


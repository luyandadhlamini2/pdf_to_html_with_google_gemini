import os
import tempfile
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI, UploadFile, File, HTTPException, status, Depends, Response, Header, Security, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from jose import JWTError, jwt
from passlib.context import CryptContext

# Security constants
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"  # Change in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Global Gemini model
GEMINI_MODEL_NAME = 'gemini-2.0-flash'

app = FastAPI()

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Password context for hashing API keys (not actually needed but using for token structure)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer security scheme
security = HTTPBearer()

# Auth token model
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    api_key: Optional[str] = None

# Updated response model for the consolidated endpoint
class ConsolidatedResponse(BaseModel):
    message: str
    filenames: List[str]
    html: Optional[List[str]] = None
    file_uris: Optional[List[str]] = None

class FileResponse(BaseModel):
    file_uri: str
    file_name: str
    state: str

# Functions for authentication
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        api_key: str = payload.get("sub")
        if api_key is None:
            raise credentials_exception
        token_data = TokenData(api_key=api_key)
    except JWTError:
        raise credentials_exception
    return token_data.api_key

# Token endpoint
@app.post("/token", response_model=Token)
async def get_access_token(api_key: str):
    """
    Get an access token using your Gemini API key.
    
    - **api_key**: Your Gemini API key
    """
    # Validate the API key with Gemini
    try:
        genai.configure(api_key=api_key)
        # Try a simple operation to validate the API key
        models = genai.list_models()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": api_key}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Helper function to shorten filenames to max 40 characters while preserving extension
def shorten_filename(filename: str, max_length: int = 40) -> str:
    """
    Shortens a filename to a maximum length while preserving the file extension.
    
    Args:
        filename: The original filename
        max_length: Maximum length of the shortened filename (default: 40)
        
    Returns:
        Shortened filename with original extension
    """
    if len(filename) <= max_length:
        return filename
        
    name, ext = os.path.splitext(filename)
    # Calculate how many characters we can keep from the name
    # We need to account for the length of the extension including the dot
    max_name_length = max_length - len(ext)
    if max_name_length <= 0:
        # If extension is too long, truncate it too
        return filename[:max_length]
    
    # Truncate the name and add the extension back
    return name[:max_name_length] + ext

# Helper function to check if a file already exists in the File API
async def file_exists_in_api(display_name: str, api_key: str) -> bool:
    """
    Checks if a file with the given display name already exists in the File API.
    
    Args:
        display_name: The display name to check
        api_key: The API key to use for authentication
        
    Returns:
        True if a file with the given display name exists, False otherwise
    """
    try:
        # Configure Gemini with the provided API key
        genai.configure(api_key=api_key)
        
        # List files from the File API
        files_list = genai.list_files()
        
        # Check if any file has the given display name
        for file in files_list:
            if file.display_name == display_name:
                return True
        
        return False
    except Exception:
        # If there's an error, assume the file doesn't exist
        return False

# Helper function to generate content with retry for RECITATION errors
async def generate_with_retry(model, content, prompt, max_retries=3):
    """
    Attempts to generate content with retries for RECITATION errors.
    
    Args:
        model: The Gemini model to use
        content: The content to process (file or text)
        prompt: The original prompt
        max_retries: Maximum number of retry attempts
        
    Returns:
        The model response
    
    Raises:
        HTTPException: If all retries fail
    """
    # Try with original prompt first
    try:
        response = model.generate_content([content, prompt])
        return response
    except Exception as e:
        error_str = str(e)
        
        # Check if it's a RECITATION error
        if "RECITATION" in error_str or ("finish_reason" in error_str and "4" in error_str):
            # Try alternative approaches
            for attempt in range(max_retries):
                try:
                    # Increase temperature with each retry
                    temperature = 0.4 + (attempt * 0.2)  # 0.4, 0.6, 0.8
                    
                    # Use increasingly aggressive alternative prompts
                    if attempt == 0:
                        alternative_prompt = """
                        Convert this PDF to clean HTML. Rather than copying the content verbatim:
                        - Reformat and restructure the content while preserving the meaning
                        - Maintain heading hierarchies and overall document structure
                        - Convert tables to HTML table format but adjust formatting slightly
                        - Focus on preserving the information hierarchy rather than exact reproduction
                        - Use your own words where appropriate while maintaining the document's integrity
                        - Completely ignore and omit all images - do not include any img tags or image references
                        """
                    elif attempt == 1:
                        alternative_prompt = """
                        Extract and organize the key information from this document.
                        Create an HTML summary that captures the main points, structure, and data,
                        without reproducing the exact text. Implement proper HTML tables for any tabular data.
                        Do not include any images, image tags, or image references in the output.
                        """
                    else:
                        alternative_prompt = """
                        Create an HTML representation of this document that preserves 
                        the structure and information, but rephrases and restructures content
                        to avoid direct reproduction while maintaining accuracy.
                        Exclude all images and image references from the HTML output.
                        """
                    
                    # Try with alternative prompt and higher temperature
                    response = model.generate_content(
                        [content, alternative_prompt],
                        generation_config={"temperature": temperature}
                    )
                    return response
                    
                except Exception as retry_e:
                    # If this is the last attempt, raise a helpful error
                    if attempt == max_retries - 1:
                        raise HTTPException(
                            status_code=422, 
                            detail=f"Content flagged as potentially copyrighted. Try using a different file or customizing the prompt. Original error: {error_str}"
                        )
                    # Otherwise wait briefly before retrying
                    await asyncio.sleep(1)
        
        # For other errors, just raise them normally
        raise e

@app.get("/")
async def root():
    """Root endpoint that returns API information."""
    return {
        "message": "PDF to HTML Conversion API using Google Gemini 2.0",
        "model": GEMINI_MODEL_NAME,
        "authentication": "POST /token with api_key=YOUR_API_KEY to get a bearer token",
        "usage": "POST /convert/ with PDF files and your bearer token, set background=true for async processing",
        "file_management": "Use /list_files/ to view all stored files (files are retained for 48 hours)",
        "docs": "/docs for interactive API documentation"
    }

@app.post("/convert/", response_model=ConsolidatedResponse)
async def convert_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...), 
    prompt: str = "", 
    background: bool = False,
    return_html: bool = True,
    api_key: str = Depends(get_current_api_key)
):
    """
    Unified endpoint for PDF to HTML conversion.
    
    - **files**: List of PDF files to convert
    - **prompt**: Optional custom prompt for Gemini
    - **background**: If true, processes files asynchronously (default: false)
    - **return_html**: If true, returns HTML content in response (default: true)
                      Only applies when background=false
    
    All converted files are stored in the File API and can be accessed via /list_files/.
    Background processing returns immediately with just filenames.
    Synchronous processing returns HTML content and file URIs.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    
    # Create a list of filenames
    filenames = []
    temp_file_paths = []
    
    for file in files:
        try:
            # Get filename
            original_filename = file.filename
            shortened_filename = shorten_filename(original_filename, 40)
            filenames.append(shortened_filename)
            
            # Check if file already exists in the File API
            if await file_exists_in_api(shortened_filename, api_key):
                raise HTTPException(
                    status_code=400, 
                    detail=f"A file with name '{shortened_filename}' already exists in the File API. Please use a different filename."
                )
            
            # Read and save file content to a temporary file
            contents = await file.read()
            temp_file_path = f"temp_{uuid.uuid4()}_{shortened_filename}"
            with open(temp_file_path, "wb") as f:
                f.write(contents)
            
            temp_file_paths.append(temp_file_path)
            
        except Exception as e:
            # Clean up any temporary files created so far
            for path in temp_file_paths:
                if os.path.exists(path):
                    os.remove(path)
            raise HTTPException(status_code=500, detail=f"Error processing {file.filename}: {str(e)}")
    
    # Handle background vs synchronous processing
    if background:
        # Start background processing with the saved file paths
        background_tasks.add_task(
            process_pdf_from_paths,
            temp_file_paths=temp_file_paths,
            filenames=filenames,
            prompt=prompt,
            api_key=api_key,
            store_files=True
        )
        
        return {
            "message": "Files submitted for background processing. HTML files will be available in the File API once processing is complete. Use /list_files/ to view all stored files.",
            "filenames": filenames
        }
    else:
        # Process files synchronously
        # Configure Gemini with the provided API key
        genai.configure(api_key=api_key)

        # Initialize the Gemini model
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)

        html_results = []
        file_uris = []

        for i, temp_file_path in enumerate(temp_file_paths):
            try:
                shortened_filename = filenames[i]
                
                # Upload file to Gemini with explicit MIME type
                sample_file = genai.upload_file(
                    path=temp_file_path, 
                    display_name=shortened_filename,
                    mime_type="application/pdf"  # Explicitly set MIME type for PDF
                )
                
                # Create effective prompt for the PDF to HTML conversion
                effective_prompt = prompt if prompt else "Convert this PDF document to well-formatted HTML. Preserve headers, lists, tables, and other formatting. Ignore page numbers, footers, and all images. Do not convert or include images in the HTML output - omit all img tags and image references. Ensure tables are properly structured with <table>, <tr>, <th>, and <td> tags."
                
                # Generate content using uploaded document with retry mechanism
                response = await generate_with_retry(model, sample_file, effective_prompt)
                html_content = response.text
                
                if return_html:
                    html_results.append(html_content)
                
                # Store the HTML content using File API
                html_filename = f"{os.path.splitext(shortened_filename)[0]}.html"
                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as html_temp_file:
                    html_temp_path = html_temp_file.name
                    html_temp_file.write(html_content.encode('utf-8'))
                
                # Upload HTML file to File API with explicit MIME type
                html_file = genai.upload_file(
                    path=html_temp_path, 
                    display_name=html_filename,
                    mime_type="text/html"  # Explicitly set MIME type for HTML
                )
                
                file_uris.append(html_file.uri)
                
                # Clean up HTML temp file
                os.remove(html_temp_path)
                
            except HTTPException as he:
                # Re-raise HTTP exceptions
                raise he
            except Exception as e:
                # Clean up temp files if they exist
                raise HTTPException(status_code=500, detail=f"Error processing {shortened_filename}: {str(e)}")
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        return {
            "message": "Files processed successfully. HTML files are available in the File API.",
            "filenames": filenames,
            "html": html_results if return_html else None,
            "file_uris": file_uris
        }

# Background processing function for file paths
async def process_pdf_from_paths(
    temp_file_paths: List[str],
    filenames: List[str],
    prompt: str,
    api_key: str,
    store_files: bool = False
):
    """
    Process PDF files in the background from temporary file paths.
    No status tracking - files will be accessible via the file list API.
    
    Args:
        temp_file_paths: List of paths to temporary PDF files
        filenames: List of original filenames
        prompt: Custom prompt for Gemini
        api_key: API key for Gemini
        store_files: Whether to store the generated HTML using the File API
    """
    # Configure Gemini with the provided API key
    genai.configure(api_key=api_key)

    # Initialize the Gemini model
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    
    # Process each file
    for i, temp_file_path in enumerate(temp_file_paths):
        try:
            shortened_filename = filenames[i]
            
            # Upload file to Gemini with explicit MIME type
            sample_file = genai.upload_file(
                path=temp_file_path, 
                display_name=shortened_filename,
                mime_type="application/pdf"  # Explicitly set MIME type for PDF
            )
            
            # Create effective prompt for the PDF to HTML conversion
            effective_prompt = prompt if prompt else "Convert this PDF document to well-formatted HTML. Preserve headers, lists, tables, and other formatting. Ignore page numbers, footers, and all images. Do not convert or include images in the HTML output - omit all img tags and image references. Ensure tables are properly structured with <table>, <tr>, <th>, and <td> tags."
            
            # Generate content using uploaded document with retry mechanism
            response = await generate_with_retry(model, sample_file, effective_prompt)
            html_content = response.text
            
            # Store the HTML content using File API
            html_filename = f"{os.path.splitext(shortened_filename)[0]}.html"
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as html_temp_file:
                html_temp_path = html_temp_file.name
                html_temp_file.write(html_content.encode('utf-8'))
            
            # Upload HTML file to File API with explicit MIME type
            html_file = genai.upload_file(
                path=html_temp_path, 
                display_name=html_filename,
                mime_type="text/html"  # Explicitly set MIME type for HTML
            )
            
            # Clean up HTML temp file
            os.remove(html_temp_path)
            
        except Exception as e:
            # Log error but continue with other files
            print(f"Error processing file {shortened_filename}: {str(e)}")
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

@app.get("/fetch_html/", response_class=Response)
async def fetch_html(
    file_uri: str,
    api_key: str = Depends(get_current_api_key)
):
    """
    Fetches HTML content from a File API URI.
    
    - **file_uri**: The URI of the HTML file from the File API
    """
    try:
        # Configure Gemini with the provided API key
        genai.configure(api_key=api_key)
        
        # Initialize the Gemini model
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        
        # Create a prompt to request the content of the file
        prompt = "Please return the exact content of this file without any modifications or additional comments."
        
        # Create a file_data object from the URI
        file_data = {"file_data": {"file_uri": file_uri, "mime_type": "text/html"}}
        
        # Generate content using the file URI
        response = model.generate_content([prompt, file_data])
        
        return Response(content=response.text, media_type="text/html")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching HTML: {str(e)}")

@app.get("/file_info/")
async def get_file_info(
    file_name: str,
    api_key: str = Depends(get_current_api_key)
):
    """
    Gets information about a file stored in the File API.
    
    - **file_name**: The name of the file from the File API
    """
    try:
        # Configure Gemini with the provided API key
        genai.configure(api_key=api_key)
        
        # Get file information from the File API
        file_info = genai.get_file(file_name)
        
        return {
            "name": file_info.name,
            "uri": file_info.uri,
            "display_name": file_info.display_name,
            "state": file_info.state,
            "mime_type": file_info.mime_type,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching file info: {str(e)}")

@app.delete("/delete_file/")
async def delete_file(
    file_name: str,
    api_key: str = Depends(get_current_api_key)
):
    """
    Deletes a file stored in the File API.
    
    - **file_name**: The name of the file from the File API
    """
    try:
        # Configure Gemini with the provided API key
        genai.configure(api_key=api_key)
        
        # Delete the file from the File API
        genai.delete_file(file_name)
        
        return {"message": f"File {file_name} deleted successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@app.get("/list_files/")
async def list_files(
    page_size: int = 100,
    api_key: str = Depends(get_current_api_key)
):
    """
    Lists all files stored in the File API.
    Files are retained for 48 hours after creation.
    
    - **page_size**: Maximum number of files to return (default: 100)
    """
    try:
        # Configure Gemini with the provided API key
        genai.configure(api_key=api_key)
        
        # List files from the File API
        # The response is a generator, so we need to iterate through it
        files_list = genai.list_files(page_size=page_size)
        
        # Extract file information
        files = []
        for file in files_list:
            files.append({
                "name": file.name,
                "uri": file.uri,
                "display_name": file.display_name,
                "state": file.state,
                "mime_type": file.mime_type,
                "create_time": file.create_time,
                "update_time": file.update_time,
                "expiration_time": file.expiration_time if hasattr(file, 'expiration_time') else None,
            })
        
        # Return files
        result = {
            "files": files,
            "total_size": len(files)
        }
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


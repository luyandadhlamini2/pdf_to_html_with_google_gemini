# PDF to HTML Converter with Gemini AI

This FastAPI application converts PDF documents to HTML format using Google's Gemini 2.0 AI. It provides a simple API endpoint that accepts PDF file uploads, processes them with Gemini, and returns the HTML representation with full table support.

## Features

- Upload multiple PDF files simultaneously
- Convert PDFs to well-formatted HTML using Gemini 2.0's advanced document understanding
- Excellent support for complex tables with proper HTML table structures
- Background processing for large documents
- Simple API key authentication with bearer tokens
- Store generated HTML in Gemini's File API for persistent access
- Retrieve stored HTML files using File URIs
- Customize conversion with custom prompts
- Automatic filename shortening to 40 characters maximum
- Duplicate file detection to prevent overwriting existing files
- Easy to use API with Swagger documentation
- Cross-origin request support (CORS enabled)

## Prerequisites

- Python 3.9 or higher
- Docker (for containerized deployment)
- A Gemini API key from [Google AI Studio](https://ai.google.dev/)
- Google Cloud account (for cloud deployment)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/pdf_to_html_with_google_gemini.git
   cd pdf_to_html_with_google_gemini
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   ```

3. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

## Local Development

### Running Directly with Python

To run the application locally without Docker:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running with Docker

To build and run the application locally with Docker:

1. Build the Docker image:
   ```bash
   docker build -t pdf-to-html .
   ```

2. Run the container:
   ```bash
   docker run -it -p 8000:8080 pdf-to-html
   ```

The application will be accessible at http://localhost:8000, and the API documentation at http://localhost:8000/docs.

## Using the API

1. Open your browser and navigate to http://localhost:8000/docs to access the Swagger UI.

2. First, authenticate using your Gemini API key:
   - Go to the `/token` endpoint
   - Click "Try it out"
   - Enter your Gemini API key in the `api_key` field
   - Click "Execute"
   - Copy the access token from the response

3. Use the `/convert/` endpoint to upload PDF files:
   - Click on "Authorize" at the top of the Swagger UI and paste your access token
   - Go to the `/convert/` endpoint
   - Click "Try it out"
   - Upload one or more PDF files
   - (Optional) Enter a custom prompt to guide the conversion
   - (Optional) Set `background` to true for asynchronous processing
   - (Optional) Set `return_html` to false to exclude HTML content from the response
   - Click "Execute"

4. The API will return a JSON response with the filenames, HTML content (if requested), and file URIs.

## API Endpoints

### POST /token

Authenticate with your Gemini API key to receive a bearer token.

**Parameters**:
- `api_key`: Your Gemini API key (required)

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### POST /convert/

Unified endpoint for PDF to HTML conversion with options for synchronous or background processing.
All converted files are stored in the File API for persistent access.

**Parameters**:
- `files`: List of PDF files to convert (required)
- `prompt`: Custom instructions for the conversion (optional)
- `background`: If true, processes files asynchronously (default: false)
- `return_html`: If true, returns HTML content in response (default: true, only applies when background=false)

**Authorization**: Bearer token required

**Response (synchronous mode)**:
```json
{
  "message": "Files processed successfully. HTML files are available in the File API.",
  "filenames": ["example.pdf"],
  "html": ["<!DOCTYPE html><html><head>...</head><body>...</body></html>"],
  "file_uris": ["generativelanguage://files/FILE_IDENTIFIER"]
}
```

**Response (background mode)**:
```json
{
  "message": "Files submitted for background processing. HTML files will be available in the File API once processing is complete. Use /list_files/ to view all stored files.",
  "filenames": ["example.pdf"]
}
```

### GET /fetch_html/

Fetches a HTML file using its File API URI.

**Parameters**:
- `file_uri`: The URI of the HTML file from the File API (required)

**Authorization**: Bearer token required

**Response**: Raw HTML content with `text/html` content type

### GET /file_info/

Gets information about a file stored in the File API.

**Parameters**:
- `file_name`: The name of the file from the File API (required)

**Authorization**: Bearer token required

**Response**:
```json
{
  "name": "files/FILE_NAME",
  "uri": "generativelanguage://files/FILE_IDENTIFIER",
  "display_name": "example.html",
  "state": "ACTIVE",
  "mime_type": "text/html"
}
```

### DELETE /delete_file/

Deletes a file from the File API.

**Parameters**:
- `file_name`: The name of the file from the File API (required)

**Authorization**: Bearer token required

**Response**:
```json
{
  "message": "File files/FILE_NAME deleted successfully"
}
```

### GET /list_files/

Lists all files stored in the File API.

**Parameters**:
- `page_size`: Maximum number of files to return (default: 100)

**Authorization**: Bearer token required

**Response**:
```json
{
  "files": [
    {
      "name": "files/FILE_NAME_1",
      "uri": "generativelanguage://files/FILE_IDENTIFIER_1",
      "display_name": "example1.html",
      "state": "ACTIVE",
      "mime_type": "text/html",
      "create_time": "2023-09-01T12:00:00Z",
      "update_time": "2023-09-01T12:00:00Z",
      "expiration_time": "2023-09-03T12:00:00Z"
    },
    {
      "name": "files/FILE_NAME_2",
      "uri": "generativelanguage://files/FILE_IDENTIFIER_2",
      "display_name": "example2.html",
      "state": "ACTIVE",
      "mime_type": "text/html",
      "create_time": "2023-09-01T13:00:00Z",
      "update_time": "2023-09-01T13:00:00Z",
      "expiration_time": "2023-09-03T13:00:00Z"
    }
  ],
  "total_size": 2
}
```

### GET /

Returns basic information about the API.

## Processing Modes

### Synchronous Processing

By default, the `/convert/` endpoint processes files synchronously, meaning:
- The API will wait until all files are processed before responding
- The response will include the HTML content (if return_html=true)
- This is suitable for smaller files or when you need the HTML content immediately

Example:
```bash
curl -X 'POST' \
  'http://localhost:8000/convert/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'files=@example.pdf' \
  -F 'prompt=Convert to well-formatted HTML'
```

### Background Processing

For larger documents or when you don't need immediate results, use background processing:
- Set `background=true` in your request
- The API will return immediately with a list of submitted files
- Processing continues in the background
- Once complete, files are available through the File API
- Check processing status by listing files with `/list_files/`

Example:
```bash
curl -X 'POST' \
  'http://localhost:8000/convert/?background=true' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'files=@large_document.pdf'
```

## Using Custom Prompts

You can customize the conversion by providing a prompt in the API request. For example:

- "Convert this PDF to HTML with a focus on preserving tables and formatting"
- "Extract only the headings and bullet points from this document"
- "Convert to HTML and organize the content by section"

If no prompt is provided, a default prompt will be used that focuses on preserving the document structure, tables, and formatting.

## Model Information

This application uses the `gemini-2.0-flash` model, which offers:

- Faster processing times compared to previous versions
- Improved handling of complex document structures
- Better table recognition and conversion
- Enhanced ability to follow custom prompts
- Improved handling of copyrighted content

The model is configured globally in the application for consistent performance across all endpoints.

## Security Considerations

- This API uses bearer token authentication for improved security
- Bearer tokens are valid for 30 minutes by default
- The `SECRET_KEY` in the code should be changed for production use
- For production, consider using environment variables for sensitive values
- The `--allow-unauthenticated` flag in the deployment script allows public access to your API
- Remove this flag for production applications that require authentication

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Make sure you're using a valid Gemini API key and including the bearer token in your requests
2. **Docker Build Fails**: Ensure Docker is running and you have sufficient permissions
3. **Deployment Fails**: Verify that you have the correct permissions on your Google Cloud project
4. **PDF Processing Errors**: Ensure your PDFs are valid and not corrupted
5. **Table Formatting Issues**: For complex tables, try providing a more specific prompt
6. **Duplicate File Errors**: If you receive an error stating that a file already exists, either:
   - Use a different filename for your PDF
   - Delete the existing file using the `/delete_file/` endpoint before uploading
7. **Content Moderation Errors**: If you receive an error about "Invalid operation" mentioning "response.text", this may indicate that the content was flagged by Gemini's content moderation system. Try with a different PDF file.
8. **RECITATION Errors**: If you receive an error with finish_reason 4 (RECITATION), see the section below on handling copyright-protected content.

## Handling Copyright-Protected Content

### RECITATION Error

Google Gemini has protective measures that prevent it from reproducing copyrighted content. When the model detects that it may be reproducing such content, it returns a RECITATION finish_reason (code 4).

The API includes built-in retry mechanisms that attempt to process such documents by:
1. Using alternative prompts that encourage paraphrasing rather than direct reproduction
2. Adjusting the temperature setting to introduce more variation
3. Focusing on information extraction rather than verbatim conversion

### Strategies for Working with Protected Content

If you encounter RECITATION errors when processing PDFs:

1. **Use a custom prompt**: Provide your own prompt that instructs the model to paraphrase or restructure content
2. **Process smaller sections**: Break large documents into smaller parts
3. **Remove copyright notices**: If possible, preprocess PDFs to remove copyright notices or other elements that might trigger the protection
4. **Try different files**: Some documents may be more heavily protected than others
5. **Use the extraction approach**: Focus on extracting key information rather than converting the entire document

Example custom prompt:
```
Convert this PDF to HTML, but paraphrase the content while preserving the structure, 
headings, and tables. Focus on maintaining the information and organization 
without reproducing exact text that might be copyrighted.
```

Note that persistently attempting to circumvent these protections for actually copyrighted material may violate Google's terms of service.

## File API Features

This application leverages the Gemini File API to provide additional functionality:

### File Storage

- Generated HTML files are stored in the Gemini File API
- Each file receives a unique URI that can be used for later retrieval
- Files can be managed (retrieved, queried, and deleted) via dedicated endpoints

### File Persistence

- Files stored in the Gemini File API are automatically deleted after 48 hours
- For critical data, implement a backup strategy to download and store files locally
- Use the `/list_files/` endpoint to monitor file expiration times

### File Access

- To access a stored HTML file, you need:
  1. The file URI (returned when uploading via `/convert/`)
  2. Your authentication token
- Files can be fetched in raw HTML format for easy rendering in browsers 
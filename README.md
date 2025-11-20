# OPEN LPR - A License Plate Reader App

A Django-based web application that uses Qwen3-VL AI model to detect and recognize license plates in images with OCR capabilities.

## Features

- **AI-Powered Detection**: Uses qwen3-vl-4b-instruct vision-language model for accurate license plate recognition
- **OCR Integration**: Extracts text from detected license plates with confidence scores
- **Bounding Box Visualization**: Draws colored boxes around detected plates and OCR text
- **Drag & Drop Upload**: Modern, user-friendly file upload interface
- **Permanent Storage**: All uploaded and processed images are saved permanently
- **Side-by-Side Comparison**: View original and processed images together
- **Search & Filter**: Browse and search through processing history
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Technology Stack

- **Backend**: Django 4.2.7 with Python
- **AI Model**: Qwen3-VL via OpenAI-compatible API
- **Image Processing**: Pillow (PIL) for image manipulation
- **Frontend**: Bootstrap 5 with custom CSS
- **Database**: SQLite (default), configurable for PostgreSQL
- **File Storage**: Django's media storage system

## Quick Start

### Prerequisites

- Python 3.8+
- pip package manager
- Qwen3-VL API access

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd open-lpr
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Set up database**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   Open http://127.0.0.1:8000 in your browser

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Qwen3-VL API Configuration
QWEN_API_KEY=your-qwen-api-key
QWEN_BASE_URL=https://your-open-api-compatible-endpoint.com/v1
QWEN_MODEL=qwen3-vl-4b-instruct

# File Upload Settings
UPLOAD_FILE_MAX_SIZE=10485760  # 10MB
MAX_BATCH_SIZE=10
```

### API Configuration

The application connects to the Qwen3-VL API at:
- **Endpoint**: `https://your-open-api-compatible-endpoint.com/v1`
- **Authentication**: Bearer token (API key)
- **Model**: `qwen3-vl-4b-instruct` (configurable)

## Usage

### Uploading Images

1. **Drag & Drop**: Simply drag an image file onto the upload area
2. **Click to Browse**: Click the upload area to select a file
3. **File Validation**:
   - Supported formats: JPEG, PNG, BMP
   - Maximum size: 10MB
4. **Processing**: Click "Analyze License Plates" to start detection

### Viewing Results

After processing, you'll see:

- **Detection Summary**: Number of plates and OCR texts found
- **Image Comparison**: Side-by-side view of original and processed images
- **Detection Details**: 
  - License plate coordinates and confidence
  - OCR text results with confidence scores
  - Bounding box coordinates for all detections
- **Download Options**: Download both original and processed images

### Browsing History

Access the "History" page to:
- **Search**: Filter by filename
- **Date Range**: Filter by upload date
- **Status Filter**: View by processing status
- **Pagination**: Navigate through large numbers of uploads

## API Endpoints

### Web Endpoints

- `GET /` - Home page with upload form
- `POST /upload/` - Upload and process image
- `GET /result/<int:image_id>/` - View processing results for a specific image
- `GET /images/` - Browse image history with search and filtering
- `GET /image/<int:image_id>/` - View detailed information about a specific image
- `POST /progress/` - Check processing status (AJAX endpoint)
- `GET /download/<int:image_id>/<str:image_type>/` - Download original or processed images
- `GET /health/` - API health check endpoint

### REST API Endpoints

- `POST /api/v1/ocr/` - Upload an image and receive OCR results synchronously

### Response Format

#### Web Interface Response Format

The web interface returns JSON responses for AJAX requests:

```json
{
    "success": true,
    "image_id": 123,
    "message": "Image processed successfully",
    "redirect_url": "/result/123/"
}
```

#### REST API Response Format

The LPR REST API returns JSON in this format:

```json
{
    "success": true,
    "image_id": 123,
    "filename": "example.jpg",
    "processing_time_ms": 2450,
    "results": {
        "detections": [
            {
                "plate_id": "plate1",
                "plate": {
                    "confidence": 0.85,
                    "coordinates": {
                        "x1": 100,
                        "y1": 200,
                        "x2": 250,
                        "y2": 250
                    }
                },
                "ocr": [
                    {
                        "text": "ABC123",
                        "confidence": 0.92,
                        "coordinates": {
                            "x1": 105,
                            "y1": 210,
                            "x2": 245,
                            "y2": 240
                        }
                    }
                ]
            }
        ]
    },
    "summary": {
        "total_plates": 1,
        "total_ocr_texts": 1
    },
    "processing_timestamp": "2023-12-07T15:30:45.123456"
}
```

#### Error Response Format

```json
{
    "success": false,
    "error": "No image file provided",
    "error_code": "MISSING_IMAGE"
}
```

## File Structure

```
open-lpr/
├── manage.py                    # Django management script
├── requirements.txt              # Python dependencies
├── .env.example                # Environment variables template
├── .env                         # Environment variables (create from .env.example)
├── .gitignore                   # Git ignore file
├── .dockerignore               # Docker ignore file
├── API_DOCUMENTATION.md        # Detailed REST API documentation
├── README_API.md               # REST API implementation summary
├── test_api.py                 # API testing script
├── test_setup.py               # Test setup utilities
├── lpr_project/               # Django project settings
│   ├── __init__.py
│   ├── settings.py             # Django configuration
│   ├── urls.py                 # Project URL patterns
│   └── wsgi.py                 # WSGI configuration
├── lpr_app/                   # Main application
│   ├── __init__.py
│   ├── admin.py                # Django admin configuration
│   ├── apps.py                 # Django app configuration
│   ├── models.py               # Database models
│   ├── views.py                # View functions and API endpoints
│   ├── urls.py                 # App URL patterns
│   ├── forms.py                # Django forms
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── qwen_client.py      # Qwen3-VL API client
│   │   ├── image_processor.py  # Image processing utilities
│   │   └── bbox_visualizer.py  # Bounding box visualization
│   ├── management/             # Django management commands
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── setup_project.py
│   └── migrations/            # Database migrations
│       ├── __init__.py
│       └── 0001_initial.py
├── media/                     # Uploaded images
│   ├── uploads/               # Original images
│   └── processed/             # Processed images
├── templates/                 # HTML templates
│   ├── base.html              # Base template
│   └── lpr_app/               # App-specific templates
│       ├── base.html
│       ├── image_detail.html
│       ├── image_list.html
│       ├── results.html
│       └── upload.html
└── .github/                  # GitHub workflows
    └── workflows/             # CI/CD configurations
```

## REST API

The application provides a REST API for programmatic license plate recognition.

### Base URL

```
http://localhost:8000/api/v1/
```

### Authentication

Currently, the API does not require authentication. For production use, consider implementing API keys or token-based authentication.

### Endpoints

#### OCR Processing

**POST** `/api/v1/ocr/`

Upload an image and receive OCR results for license plate detection and text recognition.

**Request:**
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Body**: Image file with form field name `image`

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| image | File | Yes | Image file (JPEG, PNG, or BMP) |

**File Requirements:**
- **Supported formats**: JPEG, JPG, PNG, BMP
- **Maximum file size**: 10MB
- **Recommended resolution**: 1920x1080 or higher for best results

**Response:**
See the Response Format section above for detailed response structure.

#### Health Check

**GET** `/health/`

Check the health status of the API and its dependencies.

**Response:**
```json
{
    "status": "healthy",
    "api_healthy": true,
    "database_healthy": true,
    "timestamp": "2023-12-07T15:30:45.123456"
}
```

### Usage Examples

#### Python Example

```python
import requests

# API endpoint
url = "http://localhost:8000/api/v1/ocr/"

# Image file to upload
image_path = "license_plate.jpg"

# Read and upload the image
with open(image_path, 'rb') as f:
    files = {'image': f}
    response = requests.post(url, files=files)

# Check response
if response.status_code == 200:
    result = response.json()
    if result['success']:
        print(f"Found {result['summary']['total_plates']} license plates")
        for detection in result['results']['detections']:
            for ocr in detection['ocr']:
                print(f"License plate text: {ocr['text']} (confidence: {ocr['confidence']:.2f})")
    else:
        print(f"Processing failed: {result['error']}")
else:
    print(f"HTTP Error: {response.status_code}")
    print(response.text)
```

#### cURL Example

```bash
# Upload image and get OCR results
curl -X POST \
  -F "image=@license_plate.jpg" \
  http://localhost:8000/api/v1/ocr/
```

#### JavaScript Example

```javascript
// Using fetch API
async function processImage(imageFile) {
    const formData = new FormData();
    formData.append('image', imageFile);
    
    try {
        const response = await fetch('http://localhost:8000/api/v1/ocr/', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            console.log(`Found ${result.summary.total_plates} license plates`);
            result.results.detections.forEach(detection => {
                detection.ocr.forEach(ocr => {
                    console.log(`License plate: ${ocr.text} (${ocr.confidence})`);
                });
            });
        } else {
            console.error('Processing failed:', result.error);
        }
    } catch (error) {
        console.error('Request failed:', error);
    }
}

// Usage with file input
document.getElementById('imageInput').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        processImage(file);
    }
});
```

### Error Codes

| Error Code | Description |
|------------|-------------|
| MISSING_IMAGE | No image file provided in the request |
| INVALID_FILE_TYPE | Uploaded file is not a supported image format |
| FILE_TOO_LARGE | Uploaded file exceeds the 10MB size limit |
| PROCESSING_FAILED | Image processing failed (various causes) |
| INTERNAL_ERROR | Internal server error during processing |

### Testing

Use the provided test script to verify API functionality:

```bash
# Test with default image locations
python test_api.py

# Test with specific image
python test_api.py /path/to/your/image.jpg
```

### Security Considerations

1. **File Validation**: The API validates file types and sizes to prevent malicious uploads
2. **Error Information**: Error responses avoid exposing sensitive system information
3. **CSRF Protection**: The endpoint is exempt from CSRF protection for API usage
4. **No Authentication**: Currently, the API does not require authentication. Consider implementing API keys or other authentication mechanisms for production use.

### Performance Considerations

- **Processing Time**: OCR processing typically takes 1-5 seconds depending on image size and complexity
- **Memory Usage**: Large images may require significant memory during processing
- **Concurrent Requests**: Django's development server handles requests sequentially. Use a production server (like Gunicorn) for concurrent request handling.

## Development

### Running Tests

```bash
# Run Django tests
python manage.py test

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

### Database Migrations

```bash
# Create new migrations
python manage.py makemigrations lpr_app

# Apply migrations
python manage.py migrate
```

### Static Files

```bash
# Collect static files for production
python manage.py collectstatic --noinput
```

## Deployment

### Production Settings

1. **Set DEBUG=False** in `.env`
2. **Configure ALLOWED_HOSTS** with your domain
3. **Set up production database** (PostgreSQL recommended)
4. **Configure static file serving** (nginx/AWS S3)
5. **Set up media file serving** (nginx/AWS S3)
6. **Use HTTPS** with SSL certificate

### Docker Deployment

The project includes automated Docker image building and publishing to GitHub Container Registry (ghcr.io).

#### Using the Pre-built Docker Image

The Docker image is automatically built and published to GitHub Container Registry when code is pushed to the main branch or when tags are created.

```bash
# Pull the latest image
docker pull ghcr.io/faisalthaheem/open-lpr:latest

# Pull a specific version
docker pull ghcr.io/faisalthaheem/open-lpr:v1.0.0
```

#### Docker Compose Deployment

Use the provided `docker-compose.yml` file for easy deployment:

```bash
# Clone the repository
git clone https://github.com/faisalthaheem/open-lpr.git
cd open-lpr

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start the application
docker-compose up -d

# Check logs
docker-compose logs -f
```

#### Building Locally

If you need to build the image locally:

```dockerfile
# Multi-stage Dockerfile for Open LPR Application
# Stage 1: Base stage with Python dependencies
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Verify gunicorn is installed
RUN which gunicorn || (echo "Gunicorn not found in PATH" && exit 1)

# Stage 2: Build stage for application code
FROM base AS builder

# Set work directory
WORKDIR /app

# Copy application code
COPY . .

# Create directories for volumes
RUN mkdir -p /app/data /app/media /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput

# Stage 3: Production stage
FROM base AS production

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Set work directory
WORKDIR /app

# Create directories with proper permissions
RUN mkdir -p /app/data /app/media /app/staticfiles && \
    chown -R django:django /app && \
    chmod -R 755 /app/data /app/media /app/staticfiles

# Copy application from builder stage
COPY --from=builder --chown=django:django /app /app

# Ensure PATH is set correctly for the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python manage.py check || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "lpr_project.wsgi:application"]
```

#### CI/CD Workflow

The project includes a GitHub Actions workflow (`.github/workflows/docker-publish.yml`) that:

1. **Triggers** on:
   - Push to main/master branch
   - Creation of version tags (v*)
   - Pull requests to main/master

2. **Builds** the Docker image for multiple architectures:
   - linux/amd64
   - linux/arm64

3. **Publishes** to GitHub Container Registry with tags:
   - Branch name (e.g., `main`)
   - Semantic version tags (e.g., `v1.0.0`, `v1.0`, `v1`)
   - `latest` tag for the main branch

4. **Generates** SBOM (Software Bill of Materials) for security scanning

The workflow uses GitHub's built-in `GITHUB_TOKEN` for authentication, so no additional secrets need to be configured for basic usage.

### Environment-Specific Settings

- **Development**: SQLite database, DEBUG=True
- **Staging**: PostgreSQL, DEBUG=False, limited hosts
- **Production**: PostgreSQL, DEBUG=False, HTTPS required

## Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Check QWEN_API_KEY in `.env`
   - Verify QWEN_BASE_URL is accessible
   - Check network connectivity

2. **Image Upload Failed**
   - Verify file format (JPEG/PNG/BMP only)
   - Check file size (< 10MB)
   - Ensure media directory permissions

3. **Processing Errors**
   - Check Django logs: `tail -f django.log`
   - Verify API response format
   - Check image processing dependencies

4. **Static Files Not Loading**
   - Run `python manage.py collectstatic`
   - Check STATIC_URL in settings
   - Verify web server static file configuration

### Logging

Application logs are written to:
- **Development**: Console and `django.log`
- **Production**: Configured logging destination

Log levels:
- `INFO`: General application flow
- `ERROR`: API failures and processing errors
- `DEBUG`: Detailed debugging information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section
- Review application logs
- Create an issue with detailed information
- Include error messages and steps to reproduce
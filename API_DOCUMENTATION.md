# LPR OCR REST API Documentation

## Overview

The License Plate Recognition (LPR) OCR API provides a simple REST endpoint for uploading images and receiving OCR results for license plate detection and text recognition. The API processes images synchronously and returns structured JSON responses with detected license plates and their corresponding text.

## Base URL

```
http://localhost:8000/api/v1/
```

## Endpoints

### OCR Processing

**POST** `/api/v1/ocr/`

Upload an image and receive OCR results for license plate detection and text recognition.

#### Request

- **Method**: POST
- **Content-Type**: multipart/form-data
- **Body**: Image file with form field name `image`

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| image | File | Yes | Image file (JPEG, PNG, or BMP) |

#### File Requirements

- **Supported formats**: JPEG, JPG, PNG, BMP
- **Maximum file size**: 10MB
- **Recommended resolution**: 1920x1080 or higher for best results

#### Response Format

##### Success Response (200 OK)

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

##### Error Responses

**400 Bad Request** - Validation errors

```json
{
    "success": false,
    "error": "No image file provided",
    "error_code": "MISSING_IMAGE"
}
```

```json
{
    "success": false,
    "error": "Unsupported file type: application/pdf",
    "error_code": "INVALID_FILE_TYPE"
}
```

```json
{
    "success": false,
    "error": "File too large. Maximum size is 10MB",
    "error_code": "FILE_TOO_LARGE"
}
```

**500 Internal Server Error** - Processing errors

```json
{
    "success": false,
    "error": "Failed to prepare image for API",
    "error_code": "PROCESSING_FAILED",
    "image_id": 123,
    "processing_time_ms": 1500
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Indicates if the request was successful |
| image_id | integer | Database ID of the uploaded image |
| filename | string | Original filename of the uploaded image |
| processing_time_ms | integer | Time taken to process the image in milliseconds |
| results | object | Contains detection results |
| results.detections | array | Array of detected license plates |
| detections[].plate_id | string | Unique identifier for the plate detection |
| detections[].plate | object | License plate bounding box and confidence |
| detections[].plate.confidence | float | Confidence score (0.0 to 1.0) |
| detections[].plate.coordinates | object | Bounding box coordinates (x1, y1, x2, y2) |
| detections[].ocr | array | Array of OCR text detections |
| ocr[].text | string | Recognized text from the license plate |
| ocr[].confidence | float | OCR confidence score (0.0 to 1.0) |
| ocr[].coordinates | object | Text bounding box coordinates (x1, y1, x2, y2) |
| summary | object | Summary statistics |
| summary.total_plates | integer | Total number of license plates detected |
| summary.total_ocr_texts | integer | Total number of OCR text detections |
| processing_timestamp | string | ISO 8601 timestamp of processing completion |

## Usage Examples

### Python Example

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

### cURL Example

```bash
# Upload image and get OCR results
curl -X POST \
  -F "image=@license_plate.jpg" \
  http://localhost:8000/api/v1/ocr/
```

### JavaScript Example

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

## Error Codes

| Error Code | Description |
|------------|-------------|
| MISSING_IMAGE | No image file provided in the request |
| INVALID_FILE_TYPE | Uploaded file is not a supported image format |
| FILE_TOO_LARGE | Uploaded file exceeds the 10MB size limit |
| PROCESSING_FAILED | Image processing failed (various causes) |
| INTERNAL_ERROR | Internal server error during processing |

## Health Check

Use the health check endpoint to verify API availability:

**GET** `/health/`

```json
{
    "status": "healthy",
    "api_healthy": true,
    "database_healthy": true,
    "timestamp": "2023-12-07T15:30:45.123456"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. Consider implementing rate limiting for production use to prevent abuse.

## Security Considerations

1. **File Validation**: The API validates file types and sizes to prevent malicious uploads
2. **Error Information**: Error responses avoid exposing sensitive system information
3. **CSRF Protection**: The endpoint is exempt from CSRF protection for API usage
4. **No Authentication**: Currently, the API does not require authentication. Consider implementing API keys or other authentication mechanisms for production use.

## Performance Considerations

- **Processing Time**: OCR processing typically takes 1-5 seconds depending on image size and complexity
- **Memory Usage**: Large images may require significant memory during processing
- **Concurrent Requests**: Django's development server handles requests sequentially. Use a production server (like Gunicorn) for concurrent request handling.

## Troubleshooting

### Common Issues

1. **Server Not Running**: Ensure the Django development server is running:
   ```bash
   python manage.py runserver
   ```

2. **Invalid Image Format**: Ensure the image is in JPEG, PNG, or BMP format

3. **Large File Size**: Reduce image size if it exceeds 10MB

4. **Processing Failures**: Check server logs for detailed error information:
   ```bash
   tail -f django.log
   ```

### Testing

Use the provided test script to verify API functionality:

```bash
# Test with default image locations
python test_api.py

# Test with specific image
python test_api.py /path/to/your/image.jpg
```

## Integration Notes

- The API stores processed images and results in the database for potential future reference
- Each processed image gets a unique `image_id` that can be used for tracking
- The API is synchronous - the client waits for the complete processing before receiving a response
- Consider implementing asynchronous processing for long-running tasks or high-volume usage
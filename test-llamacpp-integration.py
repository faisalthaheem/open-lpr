#!/usr/bin/env python3
"""
Test script for OpenLPR + LlamaCpp integration
Tests the connection between OpenLPR and LlamaCpp services
"""

import os
import sys
import time
import requests
import json
import base64
from pathlib import Path

# Configuration
OPENLPR_URL = "http://localhost:8000"
LLAMACPP_URL = "http://localhost:8001"
API_TIMEOUT = 30

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def log_info(message):
    print(f"{BLUE}[INFO]{NC} {message}")

def log_success(message):
    print(f"{GREEN}[SUCCESS]{NC} {message}")

def log_warning(message):
    print(f"{YELLOW}[WARNING]{NC} {message}")

def log_error(message):
    print(f"{RED}[ERROR]{NC} {message}")

def test_service_health(url, service_name):
    """Test if a service is healthy"""
    try:
        response = requests.get(f"{url}/health/", timeout=API_TIMEOUT)
        if response.status_code == 200:
            log_success(f"{service_name} is healthy")
            return True
        else:
            log_error(f"{service_name} returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log_error(f"{service_name} health check failed: {e}")
        return False

def test_llamacpp_api():
    """Test LlamaCpp OpenAI-compatible API"""
    try:
        # Test models endpoint
        response = requests.get(f"{LLAMACPP_URL}/v1/models", timeout=API_TIMEOUT)
        if response.status_code == 200:
            models = response.json()
            log_success("LlamaCpp models endpoint working")
            log_info(f"Available models: {[m['id'] for m in models.get('data', [])]}")
        else:
            log_error(f"LlamaCpp models endpoint failed: {response.status_code}")
            return False

        # Test chat completion
        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, please respond with 'OK' to confirm you're working."
                }
            ],
            "max_tokens": 10
        }
        
        response = requests.post(
            f"{LLAMACPP_URL}/v1/chat/completions",
            json=payload,
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            log_success(f"LlamaCpp chat completion working: '{message}'")
            return True
        else:
            log_error(f"LlamaCpp chat completion failed: {response.status_code}")
            log_error(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        log_error(f"LlamaCpp API test failed: {e}")
        return False

def test_openlpr_api():
    """Test OpenLPR API endpoints"""
    try:
        # Test main endpoint
        response = requests.get(OPENLPR_URL, timeout=API_TIMEOUT)
        if response.status_code == 200:
            log_success("OpenLPR main endpoint working")
        else:
            log_error(f"OpenLPR main endpoint failed: {response.status_code}")
            return False

        # Test API health
        response = requests.get(f"{OPENLPR_URL}/health/", timeout=API_TIMEOUT)
        if response.status_code == 200:
            health = response.json()
            log_success("OpenLPR health endpoint working")
            log_info(f"API healthy: {health.get('api_healthy', False)}")
        else:
            log_error(f"OpenLPR health endpoint failed: {response.status_code}")
            return False

        return True
        
    except requests.exceptions.RequestException as e:
        log_error(f"OpenLPR API test failed: {e}")
        return False

def create_test_image():
    """Create a simple test image for testing"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Create a simple test image with text
        img = Image.new('RGB', (400, 200))
        draw = ImageDraw.Draw(img)
        
        # Draw a rectangle resembling a license plate
        draw.rectangle([50, 80, 350, 120], outline=0, width=3)
        
        # Add text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        draw.text((180, 90), "TEST123", fill=0, font=font)
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        log_success("Test image created")
        return img_str
        
    except ImportError:
        log_warning("PIL not available, using fallback test")
        return None
    except Exception as e:
        log_error(f"Failed to create test image: {e}")
        return None

def test_openlpr_ocr():
    """Test OpenLPR OCR endpoint"""
    try:
        # Try to find a test image
        test_images = [
            "test_images/license_plate.jpg",
            "test_images/car.jpg",
            "container-media/uploads/test.jpg"
        ]
        
        test_image_path = None
        for path in test_images:
            if os.path.exists(path):
                test_image_path = path
                break
        
        if not test_image_path:
            log_warning("No test image found, skipping OCR test")
            log_info("To test OCR, place an image at test_images/license_plate.jpg")
            return True
        
        # Test OCR endpoint
        with open(test_image_path, 'rb') as f:
            files = {'image': f}
            response = requests.post(
                f"{OPENLPR_URL}/api/v1/ocr/",
                files=files,
                timeout=60  # Longer timeout for processing
            )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                log_success("OpenLPR OCR test passed")
                detections = result.get('results', {}).get('detections', [])
                log_info(f"Found {len(detections)} license plate(s)")
                for detection in detections:
                    ocr_texts = detection.get('ocr', [])
                    for ocr in ocr_texts:
                        if isinstance(ocr, dict):
                            text = ocr.get('text', 'N/A')
                            confidence = ocr.get('confidence', 0)
                            log_info(f"  - Text: {text} (confidence: {confidence:.2f})")
                        else:
                            log_info(f"  - OCR result: {ocr}")
                return True
            else:
                log_error(f"OpenLPR OCR failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            log_error(f"OpenLPR OCR request failed: {response.status_code}")
            log_error(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        log_error(f"OpenLPR OCR test failed: {e}")
        return False

def test_docker_services():
    """Test if Docker services are running"""
    try:
        import subprocess
        result = subprocess.run(
            ["docker-compose", "-f", "docker-compose-llamacpp-cpu.yml", "ps"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 2:  # Header + separator + services
                log_success("Docker services are running")
                for line in lines[2:]:  # Skip header and separator
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            service_name = parts[0]
                            status = parts[1]
                            log_info(f"  - {service_name}: {status}")
                return True
            else:
                log_warning("No Docker services found")
                return False
        else:
            log_error("Failed to check Docker services")
            return False
            
    except FileNotFoundError:
        log_error("docker-compose not found")
        return False
    except Exception as e:
        log_error(f"Error checking Docker services: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("🧪 OpenLPR + LlamaCpp Integration Test")
    print("=" * 60)
    
    tests = [
        ("Docker Services", test_docker_services),
        ("LlamaCpp Health", lambda: test_service_health(LLAMACPP_URL, "LlamaCpp")),
        ("OpenLPR Health", lambda: test_service_health(OPENLPR_URL, "OpenLPR")),
        ("LlamaCpp API", test_llamacpp_api),
        ("OpenLPR API", test_openlpr_api),
        ("OpenLPR OCR", test_openlpr_ocr),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            log_error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
        
        # Small delay between tests
        time.sleep(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        log_success("🎉 All tests passed! Integration is working correctly.")
        return 0
    else:
        log_error(f"💥 {total - passed} test(s) failed. Check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
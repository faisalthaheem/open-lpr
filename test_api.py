#!/usr/bin/env python3
"""
Test script for the LPR OCR API endpoint
"""

import requests
import json
import os
import sys
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{API_BASE_URL}/api/v1/ocr/"

def test_api_with_image(image_path):
    """Test the API endpoint with a sample image"""
    
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        return False
    
    print(f"Testing API with image: {image_path}")
    
    try:
        # Prepare the file for upload
        with open(image_path, 'rb') as f:
            files = {'image': f}
            
            print(f"Sending POST request to: {API_ENDPOINT}")
            
            # Make the API call
            response = requests.post(API_ENDPOINT, files=files, timeout=60)
            
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            # Try to parse JSON response
            try:
                response_data = response.json()
                print(f"Response JSON: {json.dumps(response_data, indent=2)}")
            except json.JSONDecodeError:
                print(f"Response Text: {response.text}")
            
            # Check if request was successful
            if response.status_code == 200:
                print("✅ API call successful!")
                return True
            else:
                print(f"❌ API call failed with status code: {response.status_code}")
                return False
                
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def test_error_cases():
    """Test various error cases"""
    
    print("\n" + "="*50)
    print("Testing Error Cases")
    print("="*50)
    
    # Test 1: No image provided
    print("\n1. Testing with no image...")
    try:
        response = requests.post(API_ENDPOINT, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test 2: Invalid file type
    print("\n2. Testing with invalid file type...")
    try:
        # Create a temporary text file
        with open('temp_test.txt', 'w') as f:
            f.write('This is not an image')
        
        with open('temp_test.txt', 'rb') as f:
            files = {'image': f}
            response = requests.post(API_ENDPOINT, files=files, timeout=10)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
        
        # Clean up
        os.remove('temp_test.txt')
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    """Main test function"""
    
    print("LPR OCR API Test Script")
    print("="*50)
    
    # Check if Django server is running
    try:
        response = requests.get(f"{API_BASE_URL}/health/", timeout=5)
        if response.status_code == 200:
            print("✅ Django server is running and healthy")
        else:
            print("⚠️  Django server responded but may not be healthy")
    except requests.exceptions.RequestException:
        print("❌ Django server is not running or not accessible")
        print("Please start the Django development server first:")
        print("  python manage.py runserver")
        sys.exit(1)
    
    # Look for test images in common locations
    test_image_paths = [
        "test_image.jpg",
        "test_image.png",
        "sample.jpg",
        "sample.png",
        "media/test_image.jpg",
        "media/test_image.png"
    ]
    
    test_image = None
    for path in test_image_paths:
        if os.path.exists(path):
            test_image = path
            break
    
    if not test_image:
        print("\n❌ No test image found!")
        print("Please place a test image (JPG or PNG) in one of these locations:")
        for path in test_image_paths:
            print(f"  - {path}")
        print("\nOr specify an image path as an argument:")
        print("  python test_api.py /path/to/your/image.jpg")
        sys.exit(1)
    
    # Test with the found image
    success = test_api_with_image(test_image)
    
    # Test error cases
    test_error_cases()
    
    if success:
        print("\n✅ API test completed successfully!")
    else:
        print("\n❌ API test failed!")
        sys.exit(1)

if __name__ == "__main__":
    # Allow passing image path as command line argument
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        if os.path.exists(image_path):
            test_api_with_image(image_path)
        else:
            print(f"Error: Image file not found: {image_path}")
            sys.exit(1)
    else:
        main()
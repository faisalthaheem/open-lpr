#!/usr/bin/env python3
"""
Canary script for LPR API monitoring
Posts jeep.jpg to LPR API every 5 seconds and reports results to Prometheus
"""

import os
import time
import json
import logging
import requests
from datetime import datetime
from prometheus_client import start_http_server, Counter, Histogram, REGISTRY
import base64

# Configuration
LPR_API_URL = os.getenv('LPR_API_URL', 'http://lpr-app:8000/api/v1/ocr/')
CANARY_HEADER_NAME = os.getenv('CANARY_HEADER_NAME', 'X-Canary-Request')
CANARY_HEADER_VALUE = os.getenv('CANARY_HEADER_VALUE', 'true')
CANARY_INTERVAL = int(os.getenv('CANARY_INTERVAL', '5'))  # 5 seconds in seconds
JEEP_IMAGE_PATH = '/app/jeep.jpg'
PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', '9100'))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Prometheus metrics
CANARY_REQUESTS_TOTAL = Counter(
    'lpr_canary_script_requests_total',
    'Total number of canary script requests',
    ['status'],  # success, failed, error
    registry=REGISTRY
)

CANARY_PROCESSING_DURATION = Histogram(
    'lpr_canary_script_duration_seconds',
    'Time spent processing canary requests',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, float('inf')],
    registry=REGISTRY
)

def load_image_as_base64(image_path):
    """Load image file and convert to base64"""
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
            return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to load image: {e}")
        return None

def run_canary_check():
    """Run a single canary check against the LPR API"""
    start_time = time.time()
    
    try:
        # Prepare request
        headers = {
            CANARY_HEADER_NAME: CANARY_HEADER_VALUE
        }
        
        # Prepare multipart form data - separate files and data
        files = {
            'image': open(JEEP_IMAGE_PATH, 'rb')
        }
        data = {
            'save_image': 'false'  # This saves space!
        }
        
        logger.info(f"Running canary check against {LPR_API_URL}")
        
        # Make request
        response = requests.post(
            LPR_API_URL,
            files=files,
            data=data,
            headers=headers,
            timeout=120
        )
        
        # Close files
        files['image'].close()
        
        duration = time.time() - start_time
        
        # Check response
        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get('success'):
                    logger.info(f"Canary check successful - Duration: {duration:.2f}s")
                    CANARY_REQUESTS_TOTAL.labels(status='success').inc()
                    CANARY_PROCESSING_DURATION.observe(duration)
                    
                    # Log some details
                    if 'results' in response_data:
                        plates = response_data['results'].get('detections', [])
                        logger.info(f"Detected {len(plates)} license plates")
                else:
                    logger.warning(f"Canary check failed - API returned success=false: {response_data}")
                    CANARY_REQUESTS_TOTAL.labels(status='failed').inc()
            except json.JSONDecodeError:
                logger.error(f"Canary check failed - Invalid JSON response: {response.text}")
                CANARY_REQUESTS_TOTAL.labels(status='failed').inc()
        else:
            logger.error(f"Canary check failed - HTTP {response.status_code}: {response.text}")
            CANARY_REQUESTS_TOTAL.labels(status='failed').inc()
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Canary check error - {e} (Duration: {duration:.2f}s)")
        CANARY_REQUESTS_TOTAL.labels(status='error').inc()
        CANARY_PROCESSING_DURATION.observe(duration)

def main():
    """Main canary loop"""
    logger.info("Starting LPR Canary Service")
    logger.info(f"Target API: {LPR_API_URL}")
    logger.info(f"Canary Header: {CANARY_HEADER_NAME}: {CANARY_HEADER_VALUE}")
    logger.info(f"Check Interval: {CANARY_INTERVAL} seconds")
    logger.info(f"Prometheus Port: {PROMETHEUS_PORT}")
    
    # Check if jeep image exists
    if not os.path.exists(JEEP_IMAGE_PATH):
        logger.error(f"Jeep image not found at {JEEP_IMAGE_PATH}")
        return
    
    # Start Prometheus metrics server
    start_http_server(PROMETHEUS_PORT, registry=REGISTRY)
    logger.info(f"Prometheus metrics server started on port {PROMETHEUS_PORT}")
    
    # Run first check immediately
    run_canary_check()
    
    # Then run on schedule
    while True:
        time.sleep(CANARY_INTERVAL)
        run_canary_check()

if __name__ == '__main__':
    main()

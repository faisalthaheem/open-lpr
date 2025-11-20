#!/usr/bin/env python
"""
Simple test script to verify Django LPR project setup
"""

import os
import sys
import django
from django.conf import settings
from django.core.management import execute_from_command_line

def main():
    """Test Django project setup"""
    print("Testing Django LPR Project Setup...")
    
    # Set up Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lpr_project.settings')
    
    try:
        django.setup()
        print("✓ Django setup successful")
        
        # Test database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                print("✓ Database connection successful")
            else:
                print("✗ Database connection failed")
                return False
        
        # Test models
        try:
            from lpr_app.models import UploadedImage
            print("✓ Models imported successfully")
        except ImportError as e:
            print(f"✗ Model import failed: {e}")
            return False
        
        # Test services
        try:
            from lpr_app.services.qwen_client import get_qwen_client
            print("✓ Services imported successfully")
        except ImportError as e:
            print(f"✗ Service import failed: {e}")
            return False
        
        # Test forms
        try:
            from lpr_app.forms import ImageUploadForm
            print("✓ Forms imported successfully")
        except ImportError as e:
            print(f"✗ Form import failed: {e}")
            return False
        
        # Test views
        try:
            from lpr_app.views import home
            print("✓ Views imported successfully")
        except ImportError as e:
            print(f"✗ View import failed: {e}")
            return False
        
        print("\n✓ All core components working correctly!")
        print("\nNext steps:")
        print("1. Run: python manage.py makemigrations")
        print("2. Run: python manage.py migrate")
        print("3. Run: python manage.py runserver")
        print("4. Visit: http://127.0.0.1:8000")
        
        return True
        
    except Exception as e:
        print(f"✗ Setup test failed: {e}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
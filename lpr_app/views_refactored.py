"""
Refactored views module for LPR application.

This file demonstrates the new structure after refactoring the large views.py file.
The original views.py is kept for backward compatibility during migration.

New Structure:
- views/
  - __init__.py (backward compatibility imports)
  - web_views.py (web UI views)
  - api_views.py (API endpoints)
  - file_views.py (file operations)

Services:
- services/
  - image_processing_service.py (core processing logic)
  - api_service.py (API-specific logic)
  - file_service.py (file operations)

Utils:
- utils/
  - validators.py (validation functions)
  - response_helpers.py (response formatting)
  - metrics_helpers.py (metrics tracking)

Benefits:
1. **Separation of Concerns**: Each module has a single responsibility
2. **Maintainability**: Smaller, focused files are easier to understand and modify
3. **Testability**: Isolated business logic is easier to unit test
4. **Reusability**: Services can be used across different view types
5. **Scalability**: Easier to add new features without modifying large files

Migration Strategy:
1. New code uses the refactored modules
2. Original views.py remains for backward compatibility
3. Gradual migration of existing functionality
4. Remove old views.py once migration is complete

Example Usage:
```python
# Old way (still works)
from lpr_app.views import home, upload_image

# New way (recommended)
from lpr_app.views.web_views import home, upload_image
from lpr_app.views.api_views import api_ocr_upload
from lpr_app.views.file_views import download_image
```

File Size Comparison:
- Original views.py: ~600 lines
- web_views.py: ~280 lines
- api_views.py: ~180 lines  
- file_views.py: ~60 lines
- Plus reusable services and utilities

This refactoring reduces complexity while maintaining all existing functionality.
"""

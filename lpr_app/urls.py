from django.urls import path
from . import views

# Import views from their respective modules
from .views.web_views import (
    home, upload_image, result_view, image_list, 
    image_detail, upload_progress
)
from .views.api_views import (
    api_health_check, api_ocr_upload, metrics_view
)
from .views.file_views import download_image

app_name = 'lpr_app'

urlpatterns = [
    # Home page with upload form
    path('', home, name='home'),
    
    # Image upload and processing
    path('upload/', upload_image, name='upload'),
    
    # Processing results
    path('result/<int:image_id>/', result_view, name='result'),
    
    # Image list with search and filtering
    path('images/', image_list, name='image_list'),
    
    # Image details
    path('image/<int:image_id>/', image_detail, name='image_detail'),
    
    # Upload progress (AJAX)
    path('progress/', upload_progress, name='upload_progress'),
    
    # Download images
    path('download/<int:image_id>/<str:image_type>/', download_image, name='download_image'),
    
    # API health check
    path('health/', api_health_check, name='health_check'),
    
    # REST API endpoints
    path('api/v1/ocr/', api_ocr_upload, name='api_ocr_upload'),
    
    # Prometheus metrics endpoint
    path('metrics/', metrics_view, name='metrics'),
]

from django.urls import path
from . import views

# Import views from their respective modules
from .views.web_views import (
    home, upload_image, result_redirect, image_list, 
    image_detail, upload_progress
)
from .views.api_views import (
    api_health_check, api_ocr_upload, metrics_view,
    api_image_list, api_image_detail, api_download_image,
    api_config
)
from .views.file_views import download_image

app_name = 'lpr_app'

urlpatterns = [
    # Home page with upload form
    path('', home, name='home'),
    
    # Image upload and processing
    path('upload/', upload_image, name='upload'),
    
    # Processing results (redirects to image detail)
    path('result/<int:image_id>/', result_redirect, name='result'),
    
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
    path('api/v1/images/', api_image_list, name='api_image_list'),
    path('api/v1/images/<int:image_id>/', api_image_detail, name='api_image_detail'),
    path('api/v1/download/<int:image_id>/<str:image_type>/', api_download_image, name='api_download_image'),
    path('api/v1/config/', api_config, name='api_config'),
    
    # Prometheus metrics endpoint
    path('metrics/', metrics_view, name='metrics'),
]

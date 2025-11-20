from django.urls import path
from . import views

app_name = 'lpr_app'

urlpatterns = [
    # Home page with upload form
    path('', views.home, name='home'),
    
    # Image upload and processing
    path('upload/', views.upload_image, name='upload'),
    
    # Processing results
    path('result/<int:image_id>/', views.result_view, name='result'),
    
    # Image list with search and filtering
    path('images/', views.image_list, name='image_list'),
    
    # Image details
    path('image/<int:image_id>/', views.image_detail, name='image_detail'),
    
    # Upload progress (AJAX)
    path('progress/', views.upload_progress, name='upload_progress'),
    
    # Download images
    path('download/<int:image_id>/<str:image_type>/', views.download_image, name='download_image'),
    
    # API health check
    path('health/', views.api_health_check, name='health_check'),
    
    # REST API endpoints
    path('api/v1/ocr/', views.api_ocr_upload, name='api_ocr_upload'),
]
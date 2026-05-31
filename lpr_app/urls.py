from django.urls import path
from .views.api_views import (
    api_health_check, api_ocr_upload, metrics_view,
    api_image_list, api_image_detail, api_download_image,
    api_config, api_health_light, api_availability
)
from .views.file_views import download_image

app_name = 'lpr_app'

urlpatterns = [
    path('download/<int:image_id>/<str:image_type>/', download_image, name='download_image'),
    path('health/', api_health_check, name='health_check'),
    path('api/v1/ocr/', api_ocr_upload, name='api_ocr_upload'),
    path('api/v1/images/', api_image_list, name='api_image_list'),
    path('api/v1/images/<int:image_id>/', api_image_detail, name='api_image_detail'),
    path('api/v1/download/<int:image_id>/<str:image_type>/', api_download_image, name='api_download_image'),
    path('api/v1/config/', api_config, name='api_config'),
    path('api/v1/health-light/', api_health_light, name='api_health_light'),
    path('api/v1/availability/', api_availability, name='api_availability'),
    path('metrics/', metrics_view, name='metrics'),
]

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import UploadedImage, ProcessingLog


@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    """
    Admin interface for UploadedImage model
    """
    list_display = (
        'filename',
        'file_size_mb',
        'processing_status',
        'plate_count',
        'upload_timestamp',
        'processing_timestamp',
    )
    list_filter = (
        'processing_status',
        'upload_timestamp',
        'processing_timestamp',
    )
    search_fields = ('filename',)
    readonly_fields = (
        'filename',
        'file_size',
        'upload_timestamp',
        'processing_timestamp',
        'api_response',
    )
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'original_image',
                'processed_image',
                'filename',
                'file_size',
            )
        }),
        ('Processing Information', {
            'fields': (
                'processing_status',
                'processing_timestamp',
                'error_message',
            )
        }),
        ('API Response', {
            'fields': ('api_response',),
            'classes': ('collapse',),
            'description': 'Raw API response from Qwen3-VL model'
        }),
    )
    ordering = ('-upload_timestamp',)
    date_hierarchy = 'upload_timestamp'
    
    def get_queryset(self, request):
        """
        Optimize queryset for admin interface
        """
        qs = super().get_queryset(request)
        return qs.select_related().prefetch_related('processing_logs')
    
    def file_size_mb(self, obj):
        """
        Display file size in MB
        """
        if obj.file_size_mb:
            return f"{obj.file_size_mb} MB"
        return "N/A"
    file_size_mb.short_description = 'File Size (MB)'
    
    def plate_count(self, obj):
        """
        Display number of plates detected
        """
        count = obj.get_plate_count()
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>',
                count
            )
        return "0"
    plate_count.short_description = 'Plates Detected'
    
    def original_image_thumbnail(self, obj):
        """
        Display thumbnail of original image
        """
        if obj.original_image:
            return format_html(
                '<img src="{}" width="100" height="50" style="object-fit: cover;" />',
                obj.original_image.url
            )
        return "No image"
    original_image_thumbnail.short_description = 'Original Image'
    
    def processed_image_thumbnail(self, obj):
        """
        Display thumbnail of processed image
        """
        if obj.processed_image:
            return format_html(
                '<img src="{}" width="100" height="50" style="object-fit: cover;" />',
                obj.processed_image.url
            )
        return "No processed image"
    processed_image_thumbnail.short_description = 'Processed Image'
    
    def view_results_link(self, obj):
        """
        Link to view results page
        """
        if obj.processing_status == 'completed':
            url = reverse('lpr_app:result', kwargs={'image_id': obj.id})
            return format_html(
                '<a href="{}" class="button" target="_blank">View Results</a>',
                url
            )
        return "N/A"
    view_results_link.short_description = 'View Results'
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make fields readonly after processing is complete
        """
        readonly_fields = list(self.readonly_fields)
        if obj and obj.processing_status in ['completed', 'processing']:
            readonly_fields.extend(['original_image', 'filename'])
        return readonly_fields


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    """
    Admin interface for ProcessingLog model
    """
    list_display = (
        'uploaded_image',
        'status',
        'message',
        'duration_ms',
        'timestamp',
    )
    list_filter = (
        'status',
        'timestamp',
        'uploaded_image',
    )
    search_fields = ('message',)
    readonly_fields = (
        'uploaded_image',
        'status',
        'message',
        'duration_ms',
        'timestamp',
    )
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        """
        Optimize queryset for admin interface
        """
        qs = super().get_queryset(request)
        return qs.select_related('uploaded_image')
    
    def uploaded_image_link(self, obj):
        """
        Link to the uploaded image
        """
        if obj.uploaded_image:
            url = reverse('admin:lpr_app_uploadedImage_change', 
                        kwargs={'object_id': obj.uploaded_image.id})
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.uploaded_image.filename
            )
        return "N/A"
    uploaded_image_link.short_description = 'Uploaded Image'
    
    def duration_display(self, obj):
        """
        Format duration for display
        """
        if obj.duration_ms:
            if obj.duration_ms < 1000:
                return f"{obj.duration_ms}ms"
            else:
                return f"{obj.duration_ms/1000:.2f}s"
        return "N/A"
    duration_display.short_description = 'Duration'
    
    def status_badge(self, obj):
        """
        Display status as colored badge
        """
        status_colors = {
            'started': 'orange',
            'api_call': 'blue',
            'success': 'green',
            'error': 'red',
        }
        
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


# Customize admin site header and title
admin.site.site_header = 'License Plate Recognition Admin'
admin.site.site_title = 'LPR Administration'
admin.site.index_title = 'LPR Admin Panel'
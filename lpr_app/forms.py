import logging
from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings
from .services.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class ImageUploadForm(forms.Form):
    """
    Form for uploading images for LPR processing
    """
    
    image = forms.ImageField(
        label='Select Image',
        widget=forms.FileInput(
            attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'image-upload'
            }
        ),
        help_text='Upload an image containing license plates (JPEG, PNG, WEBP formats supported)'
    )
    
    def clean_image(self):
        """
        Validate the uploaded image
        
        Returns:
            Cleaned image data or raises ValidationError
        """
        image = self.cleaned_data.get('image')
        
        if not image:
            raise forms.ValidationError('Please select an image to upload.')
        
        # Validate image using ImageProcessor
        is_valid, error_message = ImageProcessor.validate_image(image)
        
        if not is_valid:
            raise forms.ValidationError(error_message)
        
        return image
    
    def __init__(self, *args, **kwargs):
        """
        Initialize form with additional attributes
        """
        super().__init__(*args, **kwargs)
        
        # Add CSS classes and attributes
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})


class ImageSearchForm(forms.Form):
    """
    Form for searching uploaded images
    """
    
    query = forms.CharField(
        label='Search',
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Search by filename...',
                'autocomplete': 'off'
            }
        )
    )
    
    date_from = forms.DateField(
        label='From Date',
        required=False,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date'
            }
        )
    )
    
    date_to = forms.DateField(
        label='To Date',
        required=False,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date'
            }
        )
    )
    
    processing_status = forms.ChoiceField(
        label='Processing Status',
        required=False,
        choices=[
            ('', 'All'),
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            widget = self.fields[field_name].widget
            if isinstance(widget, forms.Select):
                widget.attrs.update({'class': 'form-select'})
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({'class': 'form-check-input'})
            else:
                widget.attrs.update({'class': 'form-control'})
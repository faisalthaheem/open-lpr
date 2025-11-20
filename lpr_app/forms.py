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



class LPRSettingsForm(forms.Form):
    """
    Form for configuring LPR processing settings
    """
    
    CONFIDENCE_THRESHOLD_CHOICES = [
        (0.5, 'Low (0.5)'),
        (0.7, 'Medium (0.7)'),
        (0.8, 'High (0.8)'),
        (0.9, 'Very High (0.9)'),
    ]
    
    confidence_threshold = forms.ChoiceField(
        label='Confidence Threshold',
        choices=CONFIDENCE_THRESHOLD_CHOICES,
        initial=0.7,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Minimum confidence level for detections'
    )
    
    include_ocr = forms.BooleanField(
        label='Include OCR Results',
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Include OCR text detection along with license plate detection'
    )
    
    create_comparison = forms.BooleanField(
        label='Create Comparison Image',
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Create side-by-side comparison of original and processed images'
    )
    
    output_format = forms.ChoiceField(
        label='Output Format',
        choices=[
            ('jpeg', 'JPEG'),
            ('png', 'PNG'),
        ],
        initial='jpeg',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text='Format for processed images'
    )
    
    def __init__(self, *args, **kwargs):
        """
        Initialize form with additional attributes
        """
        super().__init__(*args, **kwargs)
        
        # Add CSS classes and attributes
        for field_name, field in self.fields.items():
            if isinstance(self.fields[field_name].widget, forms.CheckboxInput):
                self.fields[field_name].widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(self.fields[field_name].widget, forms.RadioSelect):
                self.fields[field_name].widget.attrs.update({'class': 'form-check-input'})
            else:
                self.fields[field_name].widget.attrs.update({'class': 'form-select'})


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
        """
        Initialize form with additional attributes
        """
        super().__init__(*args, **kwargs)
        
        # Add CSS classes
        for field_name, field in self.fields.items():
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
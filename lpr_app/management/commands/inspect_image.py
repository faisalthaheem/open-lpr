from django.core.management.base import BaseCommand
from lpr_app.models import UploadedImage
import json


class Command(BaseCommand):
    help = 'Inspect the API response data for a specific image'
    
    def add_arguments(self, parser):
        parser.add_argument('image_id', type=int, help='Image ID to inspect')
    
    def handle(self, *args, **options):
        image_id = options['image_id']
        
        try:
            uploaded_image = UploadedImage.objects.get(id=image_id)
            
            self.stdout.write(self.style.SUCCESS(f'Inspecting Image ID: {image_id}'))
            self.stdout.write(f'Filename: {uploaded_image.filename}')
            self.stdout.write(f'Processing Status: {uploaded_image.processing_status}')
            self.stdout.write(f'Upload Timestamp: {uploaded_image.upload_timestamp}')
            self.stdout.write(f'Processing Timestamp: {uploaded_image.processing_timestamp}')
            
            if uploaded_image.error_message:
                self.stdout.write(self.style.ERROR(f'Error Message: {uploaded_image.error_message}'))
            
            self.stdout.write('\n' + '='*50)
            self.stdout.write('RAW API RESPONSE DATA:')
            self.stdout.write('='*50)
            
            if uploaded_image.api_response:
                # Pretty print the JSON response
                api_response_json = json.dumps(uploaded_image.api_response, indent=2)
                self.stdout.write(api_response_json)
            else:
                self.stdout.write(self.style.WARNING('No API response data found'))
            
            self.stdout.write('\n' + '='*50)
            self.stdout.write('DETECTION RESULTS:')
            self.stdout.write('='*50)
            
            detection_results = uploaded_image.get_detection_results()
            if detection_results:
                detection_json = json.dumps(detection_results, indent=2)
                self.stdout.write(detection_json)
                
                self.stdout.write('\n' + '-'*30)
                self.stdout.write(f'Plate Count: {uploaded_image.get_plate_count()}')
                self.stdout.write(f'Total OCR Count: {uploaded_image.get_total_ocr_count()}')
            else:
                self.stdout.write(self.style.WARNING('No detection results found'))
                
        except UploadedImage.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Image with ID {image_id} does not exist'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error inspecting image: {str(e)}'))
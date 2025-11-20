from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.core.management import call_command
import os


class Command(BaseCommand):
    help = 'Sets up the LPR project by creating migrations and superuser'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--createsuperuser',
            action='store_true',
            help='Create a superuser interactively',
        )
        parser.add_argument(
            '--skip-migrations',
            action='store_true',
            help='Skip database migrations',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up LPR project...'))
        
        # Create media directories
        self.create_media_directories()
        
        # Run migrations unless skipped
        if not options['skip_migrations']:
            self.stdout.write('Running database migrations...')
            try:
                call_command('makemigrations', ['lpr_app'])
                call_command('migrate', verbosity=0)
                self.stdout.write(self.style.SUCCESS('Database migrations completed successfully'))
            except Exception as e:
                raise CommandError(f'Migration failed: {str(e)}')
        else:
            self.stdout.write(self.style.WARNING('Skipping database migrations'))
        
        # Create superuser if requested
        if options['createsuperuser']:
            self.create_superuser()
        
        self.stdout.write(self.style.SUCCESS('LPR project setup completed!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('1. Copy .env.example to .env and configure your settings')
        self.stdout.write('2. Run: python manage.py runserver')
        self.stdout.write('3. Visit: http://127.0.0.1:8000')
    
    def create_media_directories(self):
        """Create necessary media directories"""
        from django.conf import settings
        
        media_root = settings.MEDIA_ROOT
        
        directories = [
            os.path.join(media_root, 'uploads'),
            os.path.join(media_root, 'processed'),
            os.path.join(media_root, 'uploads', '2023'),
            os.path.join(media_root, 'uploads', '2023', '01'),
            os.path.join(media_root, 'processed', '2023'),
            os.path.join(media_root, 'processed', '2023', '01'),
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                self.stdout.write(f'Created directory: {directory}')
    
    def create_superuser(self):
        """Create a superuser interactively"""
        from django.contrib.auth import get_user_model
        from django.core.exceptions import ValidationError
        
        User = get_user_model()
        
        self.stdout.write('\nCreating superuser account...')
        
        # Get user input
        username = input('Username: ').strip()
        email = input('Email: ').strip()
        password = input('Password: ').strip()
        confirm_password = input('Confirm password: ').strip()
        
        # Validate input
        if not username:
            raise CommandError('Username is required')
        
        if not email:
            raise CommandError('Email is required')
        
        if not password:
            raise CommandError('Password is required')
        
        if password != confirm_password:
            raise CommandError('Passwords do not match')
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists'))
            return
        
        try:
            # Create superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully'))
            
        except ValidationError as e:
            raise CommandError(f'Error creating superuser: {str(e)}')
        except Exception as e:
            raise CommandError(f'Unexpected error: {str(e)}')
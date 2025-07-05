"""
Safe makemigrations command that prevents dangerous User model operations.
Use this instead of the regular makemigrations command.
"""

from django.core.management.commands.makemigrations import Command as BaseMakeMigrationsCommand
from django.core.management.base import CommandError
from django.conf import settings
import re


class Command(BaseMakeMigrationsCommand):
    help = 'Safe version of makemigrations that prevents dangerous User model operations'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--force-dangerous',
            action='store_true',
            help='Force creation of dangerous migrations (use with extreme caution)',
        )

    def handle(self, *args, **options):
        # Check if we should prevent dangerous migrations
        if getattr(settings, 'PREVENT_USER_MODEL_MIGRATIONS', False):
            if not options.get('force_dangerous', False):
                # Run dry-run first to check for dangerous operations
                dry_run_options = options.copy()
                dry_run_options['dry_run'] = True
                dry_run_options['verbosity'] = 0
                
                try:
                    # Capture the dry-run output
                    import io
                    import sys
                    from contextlib import redirect_stdout, redirect_stderr
                    
                    stdout_buffer = io.StringIO()
                    stderr_buffer = io.StringIO()
                    
                    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                        super().handle(*args, **dry_run_options)
                    
                    dry_run_output = stdout_buffer.getvalue()
                    
                    # Check for dangerous operations
                    dangerous_patterns = [
                        r'- Delete model User',
                        r'~ Alter field.*user.*User',
                        r'- Remove field.*user',
                    ]
                    
                    for pattern in dangerous_patterns:
                        if re.search(pattern, dry_run_output, re.IGNORECASE):
                            self.stdout.write(
                                self.style.ERROR(
                                    '🚨 DANGEROUS MIGRATION DETECTED!\n'
                                    'This migration would affect User models and could delete user data.\n'
                                    f'Pattern found: {pattern}\n\n'
                                    'To proceed anyway (NOT RECOMMENDED), use:\n'
                                    'python manage.py safe_makemigrations --force-dangerous\n\n'
                                    'To view what would be created, use:\n'
                                    'python manage.py makemigrations --dry-run'
                                )
                            )
                            return
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Could not run safety check: {e}\n'
                            'Proceeding with caution...'
                        )
                    )
        
        # If we get here, it's safe to proceed
        if options.get('force_dangerous', False):
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  FORCING DANGEROUS MIGRATION CREATION!\n'
                    'You have chosen to override safety checks.\n'
                    'Make sure you know what you\'re doing!\n'
                )
            )
        
        # Run the actual makemigrations command
        super().handle(*args, **options) 
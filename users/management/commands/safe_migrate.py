"""
Safe migrate command that prevents dangerous User model operations.
Use this instead of the regular migrate command.
"""

from django.core.management.commands.migrate import Command as BaseMigrateCommand
from django.core.management.base import CommandError
from django.conf import settings
from django.db import connection
import re


class Command(BaseMigrateCommand):
    help = 'Safe version of migrate that prevents dangerous User model operations'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--force-dangerous',
            action='store_true',
            help='Force application of dangerous migrations (use with extreme caution)',
        )

    def handle(self, *args, **options):
        # Check if we should prevent dangerous migrations
        if getattr(settings, 'PREVENT_USER_MODEL_MIGRATIONS', False):
            if not options.get('force_dangerous', False):
                # Check for dangerous migration files that haven't been applied yet
                from django.db.migrations.loader import MigrationLoader
                from django.db.migrations.executor import MigrationExecutor
                
                try:
                    executor = MigrationExecutor(connection)
                    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
                    
                    # Check each migration in the plan for dangerous operations
                    for migration, backwards in plan:
                        if backwards:
                            continue  # Skip backwards migrations
                        
                        # Read the migration file content
                        migration_file_path = migration.migration.path if hasattr(migration.migration, 'path') else None
                        if migration_file_path:
                            try:
                                with open(migration_file_path, 'r') as f:
                                    migration_content = f.read()
                                
                                # Check for dangerous operations in the file content
                                dangerous_patterns = [
                                    r'DeleteModel.*User',
                                    r'RemoveField.*user',
                                    r'AlterField.*User.*on_delete=models.CASCADE'
                                ]
                                
                                for pattern in dangerous_patterns:
                                    if re.search(pattern, migration_content, re.IGNORECASE):
                                        self.stdout.write(
                                            self.style.ERROR(
                                                f'🚨 DANGEROUS MIGRATION DETECTED!\n'
                                                f'Migration: {migration}\n'
                                                f'File: {migration_file_path}\n'
                                                f'Pattern: {pattern}\n\n'
                                                'This migration could delete user data or break authentication.\n\n'
                                                'To proceed anyway (NOT RECOMMENDED), use:\n'
                                                'python manage.py safe_migrate --force-dangerous\n\n'
                                                'To see the plan, use:\n'
                                                'python manage.py showmigrations'
                                            )
                                        )
                                        return
                            except Exception as e:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Could not read migration file {migration_file_path}: {e}'
                                    )
                                )
                        
                        # Also check the migration operations directly
                        for operation in migration.migration.operations:
                            operation_str = str(operation)
                            if any(dangerous in operation_str.lower() for dangerous in ['delete', 'user', 'remove']):
                                if 'user' in operation_str.lower() and 'delete' in operation_str.lower():
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f'🚨 DANGEROUS OPERATION DETECTED!\n'
                                            f'Migration: {migration}\n'
                                            f'Operation: {operation}\n\n'
                                            'This operation could affect user data.\n\n'
                                            'To proceed anyway (NOT RECOMMENDED), use:\n'
                                            'python manage.py safe_migrate --force-dangerous'
                                        )
                                    )
                                    return
                
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Could not run migration safety check: {e}\n'
                            'Proceeding with caution...'
                        )
                    )
        
        # If we get here, it's safe to proceed
        if options.get('force_dangerous', False):
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  FORCING DANGEROUS MIGRATION APPLICATION!\n'
                    'You have chosen to override safety checks.\n'
                    'Make sure you have a database backup!\n'
                )
            )
        
        # Run the actual migrate command
        super().handle(*args, **options) 
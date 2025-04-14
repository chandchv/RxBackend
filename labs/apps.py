from django.apps import AppConfig


class LabsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "labs"
    verbose_name = "Laboratory Management"

    def ready(self):
        # Import signals to connect them
        import labs.signals

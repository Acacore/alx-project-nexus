from django.apps import AppConfig


class MercarolConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mercarol"

    def ready(self):
        import mercarol.signals 
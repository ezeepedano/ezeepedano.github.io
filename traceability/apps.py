from django.apps import AppConfig


class TraceabilityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'traceability'
    
    def ready(self):
        """Importar señales cuando la app esté lista"""
        import traceability.signals  # noqa

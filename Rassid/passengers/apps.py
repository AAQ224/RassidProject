from django.apps import AppConfig


class PassengersConfig(AppConfig):
    name = 'passengers'

    def ready(self):
        import passengers.signals

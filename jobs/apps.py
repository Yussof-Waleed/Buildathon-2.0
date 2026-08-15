from django.apps import AppConfig


class JobsConfig(AppConfig):
    name = 'jobs'

    def ready(self) -> None:
        # Late imports: AppConfig.ready runs after the app registry is populated.
        from django.conf import settings

        if not settings.WHATSAPP_PHONE_ID or not settings.WHATSAPP_TOKEN:
            return

        from jobs.whatsapp.handlers import register_handlers

        register_handlers()

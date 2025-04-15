from django.apps import AppConfig
from django.db import ProgrammingError, OperationalError


class TeamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.team"

    def ready(self):
        try:
            from apps.team.models import Team
            if not Team.objects.filter(is_fake=True).exists():
                Team.objects.get_or_create(
                    name="[FAKE] Dummy Team",
                    defaults={'is_fake': True}
                )
        except (OperationalError, ProgrammingError):
            pass

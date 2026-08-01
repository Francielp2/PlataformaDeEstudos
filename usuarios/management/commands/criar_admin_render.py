import os

from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Usuario


class Command(BaseCommand):
    help = "Cria o administrador inicial do Render, caso ainda não exista."

    def handle(self, *args, **options):
        email = os.getenv("DJANGO_ADMIN_EMAIL")
        password = os.getenv("DJANGO_ADMIN_PASSWORD")
        first_name = os.getenv("DJANGO_ADMIN_FIRST_NAME", "Administrador")

        if not email or not password:
            raise CommandError(
                "Defina DJANGO_ADMIN_EMAIL e DJANGO_ADMIN_PASSWORD."
            )

        if Usuario.objects.filter(email__iexact=email).exists():
            self.stdout.write(
                self.style.WARNING("O administrador já existe.")
            )
            return

        Usuario.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
        )

        self.stdout.write(
            self.style.SUCCESS("Administrador criado com sucesso.")
        )

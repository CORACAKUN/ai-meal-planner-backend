import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Reset an existing user's password and activate the account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.getenv("REPAIR_USERNAME", ""),
            help="Username to repair. Can also be provided with REPAIR_USERNAME.",
        )
        parser.add_argument(
            "--password",
            default=os.getenv("REPAIR_PASSWORD", ""),
            help="New password. Can also be provided with REPAIR_PASSWORD.",
        )

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        password = options["password"] or ""

        if not username:
            self.stdout.write(
                self.style.WARNING("REPAIR_USERNAME not set. Skipping user login repair.")
            )
            return
        if not password:
            self.stdout.write(
                self.style.WARNING("REPAIR_PASSWORD not set. Skipping user login repair.")
            )
            return

        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User '{username}' does not exist") from exc

        user.set_password(password)
        user.is_active = True
        update_fields = ["password", "is_active"]

        if user.username.lower() == "superadmin":
            user.is_staff = True
            user.is_superuser = True
            update_fields.extend(["is_staff", "is_superuser"])

        user.save(update_fields=update_fields)

        self.stdout.write(
            self.style.SUCCESS(f"Repaired login for user '{user.username}'.")
        )

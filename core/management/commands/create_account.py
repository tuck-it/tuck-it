import getpass
import os

from django.core.management.base import BaseCommand, CommandError

from core.services.accounts import create_account
from core.services.exceptions import InvalidValue


class Command(BaseCommand):
    help = "Create a real user with a workspace and owner membership."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--workspace", required=True)
        parser.add_argument("--slug", required=True)
        parser.add_argument("--username", default=None)
        parser.add_argument(
            "--password-env",
            default=None,
            help="Name of an env var holding the password (else prompt interactively).",
        )

    def handle(self, *args, **options):
        if options["password_env"]:
            password = os.environ.get(options["password_env"])
            if not password:
                raise CommandError(
                    f"Env var {options['password_env']} is empty or unset"
                )
        else:
            password = getpass.getpass("Password: ")

        try:
            user, workspace = create_account(
                email=options["email"],
                workspace_name=options["workspace"],
                slug=options["slug"],
                password=password,
                username=options["username"],
            )
        except InvalidValue as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"Created user {user.username} + workspace {workspace.slug}"
            )
        )

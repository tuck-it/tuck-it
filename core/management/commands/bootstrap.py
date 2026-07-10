from django.core.management.base import BaseCommand

from core.models import ApiToken, Area, Membership, User, Workspace
from core.services.areas import create_area, get_or_create_inbox
from core.services.tokens import generate_token


def ensure_bootstrap(username: str = "local", workspace_slug: str = "default") -> tuple[Workspace, str | None]:
    user, _ = User.objects.get_or_create(username=username)
    workspace, _ = Workspace.objects.get_or_create(
        slug=workspace_slug, defaults={"name": "Default"}
    )
    Membership.objects.get_or_create(user=user, workspace=workspace, defaults={"role": "owner"})
    get_or_create_inbox(workspace)
    if not Area.objects.filter(workspace=workspace, is_inbox=False).exists():
        create_area(workspace, "Default")

    raw = None
    if not ApiToken.objects.filter(workspace=workspace).exists():
        _, raw = generate_token(workspace, "local-cli")
    return workspace, raw


class Command(BaseCommand):
    help = "Create the default local user, workspace, membership, area, and API token."

    def handle(self, *args, **options):
        workspace, raw = ensure_bootstrap()
        self.stdout.write(self.style.SUCCESS(f"Workspace ready: {workspace.slug}"))
        if raw:
            self.stdout.write(self.style.WARNING(f"API token (shown once): {raw}"))
        else:
            self.stdout.write("API token already exists — re-run with a fresh workspace to mint another.")

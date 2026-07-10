from core.models import Membership, Workspace


def get_current_workspace(request) -> Workspace | None:
    if not request.user.is_authenticated:
        return None
    m = (Membership.objects.select_related("workspace")
         .filter(user=request.user).order_by("id").first())
    return m.workspace if m else None

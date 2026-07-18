from django.contrib import admin

from tuckit.core.models import ApiToken, OrgStatSnapshot


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "org", "last_used_at", "created_at")
    search_fields = ("name", "org__name", "org__slug")
    autocomplete_fields = ("org",)
    # token_hash is a secret; keep it read-only.
    readonly_fields = ("token_hash", "last_used_at", "created_at")


@admin.register(OrgStatSnapshot)
class OrgStatSnapshotAdmin(admin.ModelAdmin):
    """Derived, snapshot data — read-only."""

    list_display = (
        "org",
        "date",
        "building_ct",
        "backlog_ct",
        "shipped_week_ct",
        "attention_ct",
    )
    list_filter = ("date",)
    search_fields = ("org__name", "org__slug")
    readonly_fields = (
        "org",
        "date",
        "building_ct",
        "backlog_ct",
        "shipped_week_ct",
        "attention_ct",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

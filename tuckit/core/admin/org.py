from django.contrib import admin

from tuckit.core.models import Invitation, Org, OrgMember


class OrgMemberInline(admin.TabularInline):
    model = OrgMember
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("created_at",)
    inlines = [OrgMemberInline]


@admin.register(OrgMember)
class OrgMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "org", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "org__name")
    autocomplete_fields = ("user", "org")
    readonly_fields = ("created_at",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "org", "role", "accepted_at", "created_at")
    list_filter = ("role", "accepted_at")
    search_fields = ("email", "org__name")
    autocomplete_fields = ("org",)
    readonly_fields = ("created_at",)

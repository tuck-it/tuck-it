from django.contrib import admin

from tuckit.core.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_staff", "is_superuser", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email",)
    ordering = ("email",)
    # password is a hash; never edit it as plaintext from the admin.
    readonly_fields = ("password", "last_login", "date_joined")

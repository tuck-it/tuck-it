from django.contrib import admin

from tuckit.core.models import Area, Bite, Slice, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace")
    list_filter = ("workspace",)
    search_fields = ("name",)


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "workspace", "is_triage", "archived")
    list_filter = ("workspace", "archived", "is_triage")
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")


class BiteInline(admin.TabularInline):
    model = Bite
    extra = 0
    fields = ("title", "status", "source", "rank")
    show_change_link = True


@admin.register(Slice)
class SliceAdmin(admin.ModelAdmin):
    list_display = ("title", "area", "status", "source", "created_at")
    list_filter = ("status", "source")
    search_fields = ("title",)
    autocomplete_fields = ("area",)
    filter_horizontal = ("tags",)
    readonly_fields = ("created_at", "updated_at", "completed_at")
    inlines = [BiteInline]


@admin.register(Bite)
class BiteAdmin(admin.ModelAdmin):
    list_display = ("title", "slice", "status", "source")
    list_filter = ("status", "source")
    search_fields = ("title",)
    autocomplete_fields = ("slice",)
    readonly_fields = ("created_at", "updated_at")

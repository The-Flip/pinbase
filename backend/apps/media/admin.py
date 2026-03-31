from django.contrib import admin

from .models import MediaAsset, MediaVariant


class MediaVariantInline(admin.TabularInline):
    model = MediaVariant
    extra = 0
    readonly_fields = (
        "role",
        "storage_key",
        "mime_type",
        "byte_size",
        "width",
        "height",
        "is_ready",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    """Read-only inspection view. MediaAssets are created by the upload API."""

    list_display = (
        "uuid",
        "kind",
        "status",
        "original_filename",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("kind", "status")
    search_fields = ("uuid", "original_filename")
    readonly_fields = (
        "uuid",
        "kind",
        "original_filename",
        "mime_type",
        "byte_size",
        "width",
        "height",
        "status",
        "uploaded_by",
        "created_at",
        "updated_at",
    )
    inlines = [MediaVariantInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MediaVariant)
class MediaVariantAdmin(admin.ModelAdmin):
    """Read-only inspection view. MediaVariants are created by the upload API."""

    list_display = ("asset", "role", "storage_key", "is_ready")
    list_filter = ("role", "is_ready")
    search_fields = ("storage_key",)
    readonly_fields = (
        "asset",
        "role",
        "storage_key",
        "mime_type",
        "byte_size",
        "width",
        "height",
        "is_ready",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

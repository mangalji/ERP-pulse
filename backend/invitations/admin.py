from django.contrib import admin
from .models import Invitation


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'company', 'status', 'expires_at', 'accepted_at', 'created_at')
    list_filter = ('status', 'company', 'created_at')
    search_fields = ('email', 'company__name', 'token')
    readonly_fields = ('token', 'created_at', 'updated_at')

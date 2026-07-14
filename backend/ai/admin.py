from django.contrib import admin

from ai.models import AIConversation, AIMessage


class AIMessageInline(admin.TabularInline):
    """Read-only inline so a conversation's full history is visible from AIConversationAdmin."""

    model = AIMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    """
    Read-only by design, same precedent as accounts.OTPAdmin: conversations
    and messages must only ever be created by AIService, never manually
    through the admin.
    """

    ordering = ('-updated_at',)
    list_display = ('title', 'user', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'user__email')
    readonly_fields = ('id', 'user', 'title', 'created_at', 'updated_at')
    inlines = [AIMessageInline]

    def has_add_permission(self, request) -> bool:
        return False

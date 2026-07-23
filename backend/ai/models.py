"""
AI module models.

Only conversation/message history is stored here — no embeddings, no
vector storage, no NetSuite business data (Customers/Items/etc. never get
local models anywhere in this project, per NETSUITE_CONTEXT.md/PROJECT
architecture rules). This is exactly the kind of data
DATABASE_CONTEXT.md's "AI Insight" ownership describes: ERP Pulse-specific
data, not a copy of NetSuite records.
"""

import uuid

from django.conf import settings
from django.db import models


class AIConversation(models.Model):
    """One chat thread between a user and the AI Assistant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_conversations',
    )

    title = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_conversation'
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'{self.title} ({self.user.email})'


class AIMessage(models.Model):
    """A single turn (user question or assistant reply) within an AIConversation."""

    class Role(models.TextChoices):
        USER = 'USER', 'User'
        ASSISTANT = 'ASSISTANT', 'Assistant'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )

    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_message'
        ordering = ['created_at']
        indexes = [
            # Speeds up "full history for this conversation, in order" —
            # the only read pattern this model currently needs to serve.
            models.Index(fields=['conversation', 'created_at'], name='ai_message_conv_created_idx'),
        ]

    def __str__(self) -> str:
        preview = self.content[:40]
        return f'{self.role}: {preview}'

class AIAuditLog(models.Model):
    """
    One row per provider call — internal observability, distinct from
    AIMessage (the user-facing chat transcript). Tracks *how* an answer
    was produced (which provider, which prompt version, how long it
    took, whether it succeeded) rather than *what* was said.

    Written by AIService.ask() on both success and failure — a failed
    provider call is exactly the kind of thing worth auditing, so
    success=False rows are expected, not an error condition in
    themselves.

    conversation/user are nullable + SET_NULL so audit history survives
    a conversation or user being deleted later, same reasoning as
    NetSuiteConnectionAuditLog (netsuite/models.py).
    """

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null = True,blank=True,
        on_delete=models.SET_NULL,
        related_name='ai_audit_logs',    
        )
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        null=True,blank=True,
        related_name='audit_logs',
    )
    provider = models.CharField(max_length=50,null=True,blank=True)
    model = models.CharField(max_length=100,null=True,blank=True)
    prompt_version = models.CharField(max_length=20,null=True,blank=True)

    success = models.BooleanField()
    error_message = models.TextField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='ai_audit_user_recent_idx'),
        ]

    def __str__(self) -> str:
        status = 'OK' if self.success else 'FAILED'
        return f'{self.provider} ({status}) — {self.created_at:%Y-%m-%d %H:%M}'
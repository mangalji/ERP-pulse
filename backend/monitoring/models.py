from django.db import models
import uuid
from django.conf import settings

class ErrorLog(models.Model):
    """
    One row per unhandled exception surfaced through the API.
    """

    LEVEL_CHOICES = [
        ('error','Error'),
        ('warning','Warning'),
    ]
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    level = models.CharField(max_length=10,choices=LEVEL_CHOICES,default='error')
    message = models.TextField()
    exception_type = models.CharField(max_length=255,blank=True)
    traceback = models.CharField(max_length=255,blank=True)
    method = models.CharField(max_length=10,blank=True)
    path = models.CharField(max_length=500,blank=True)
    status_code = models.PositiveSmallIntegerField(null=True,blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,blank=True,
        related_name='error_logs'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monitoring_logs_table"
        ordering = ["-created_at"]
        indexes=[
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.method} {self.path} ({self.status_code})."
        
class RequestLog(models.Model):
    """
    One row per API request, written by RequestMonitoringMiddleware.
    Kept intentioanlly lean(no request/response body) since this is a high volume table. 
    """

    id = models.BigAutoField(primary_key=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField()
    response_time_ms = models.FloatField()
    is_throttled = models.BooleanField(default=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='request_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monitoring_request_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["path"]),
        ]
        
    def __str__(self):
        return f"{self.method} {self.path} -> {self.status_code} ({self.response_time_ms}ms)"
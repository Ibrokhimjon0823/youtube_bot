from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractUser):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    language_code = models.CharField(max_length=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    # Add custom related_name for these relationships
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name="groups",
        blank=True,
        related_name="bot_user_set",  # Custom related_name
        help_text="The groups this user belongs to.",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name="user permissions",
        blank=True,
        related_name="bot_user_set",  # Custom related_name
        help_text="Specific permissions for this user.",
    )

    USERNAME_FIELD = "telegram_id"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} (@{self.username or 'no_username'})"


class Download(models.Model):
    DOWNLOAD_TYPES = (
        ("VIDEO", "Video"),
        ("AUDIO", "Audio"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="downloads")
    youtube_url = models.URLField(max_length=500)
    video_title = models.CharField(max_length=500)
    download_type = models.CharField(max_length=10, choices=DOWNLOAD_TYPES)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    file_size = models.PositiveBigIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.video_title} ({self.download_type}) by {self.user.username or self.user.first_name}"

    def save(self, *args, **kwargs):
        # Update user's last_active field
        self.user.last_active = timezone.now()
        self.user.save()
        super().save(*args, **kwargs)

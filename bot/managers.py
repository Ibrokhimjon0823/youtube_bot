from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, telegram_id, password=None, **extra_fields):
        if not telegram_id:
            raise ValueError("The Telegram ID is required")

        extra_fields.setdefault("is_active", True)
        user = self.model(telegram_id=telegram_id, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, telegram_id, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(telegram_id, password, **extra_fields)

from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        AGENT = "agent", "Support Agent"
        ADMIN = "admin", "Admin"

    # Log in with email. `username` is kept only as a display name —
    # overridden here to drop AbstractUser's unique=True + validators, so
    # duplicates and any characters are allowed.
    email = models.EmailField("email address", unique=True)
    username = models.CharField(max_length=150)

    phone = models.CharField(max_length=20, blank=True, default="")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    def __str__(self):
        return self.email

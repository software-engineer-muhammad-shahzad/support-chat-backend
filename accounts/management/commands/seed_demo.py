from django.core.management.base import BaseCommand

from accounts.models import User

DEMO_PASSWORD = "demo1234"

DEMO_ACCOUNTS = [
    ("Jordan Lee", "customer@demo.com", User.Role.CUSTOMER),
    ("Alex Rivera", "agent@demo.com", User.Role.AGENT),
    ("Sam Okafor", "admin@demo.com", User.Role.ADMIN),
]


class Command(BaseCommand):
    help = f"Create or reset the demo accounts (password: {DEMO_PASSWORD})."

    def handle(self, *args, **options):
        for username, email, role in DEMO_ACCOUNTS:
            user, created = User.objects.get_or_create(email=email)
            user.username = username
            user.role = role
            user.is_staff = role == User.Role.ADMIN
            user.is_active = True
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.stdout.write(
                f"  {'created' if created else 'updated'}  {email:20}  {role}"
            )
        self.stdout.write(
            self.style.SUCCESS(f"Demo accounts ready — password: {DEMO_PASSWORD}")
        )

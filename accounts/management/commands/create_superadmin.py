import getpass

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    """Create (or promote) the system-level super-admin account.

    This is the ONLY way to create a super_admin — the API never accepts
    that role, on any endpoint, no matter who's asking.

    Usage:
        python manage.py create_superadmin --email you@example.com --username "Site Owner"
        python manage.py create_superadmin --email you@example.com --password "supersecret123"
    """

    help = "Create or promote the system-level super-admin account (CLI-only role)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Super admin's email (login).")
        parser.add_argument("--username", default="Super Admin", help="Display name.")
        parser.add_argument(
            "--password",
            help="If omitted, you'll be prompted for one (hidden input).",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        username = options["username"]
        password = options["password"] or getpass.getpass("Password: ")

        if not password or len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        user, created = User.objects.get_or_create(email=email)
        user.username = username
        user.role = User.Role.SUPER_ADMIN
        user.is_staff = True
        user.is_superuser = True  # full Django /admin/ access too
        user.is_active = True
        user.set_password(password)
        user.save()

        verb = "Created" if created else "Promoted existing account to"
        self.stdout.write(self.style.SUCCESS(f"{verb} super admin: {email}"))

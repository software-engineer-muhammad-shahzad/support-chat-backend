"""Self-service password reset — customers and admin-tier accounts only, for now."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import ADMIN_TIER_ROLES
from accounts.serializers import PasswordResetConfirmSerializer, PasswordResetRequestSerializer

# Agents aren't included yet — they'll get their own flow later.
RESETTABLE_ROLES = (User.Role.CUSTOMER, *ADMIN_TIER_ROLES)

GENERIC_RESPONSE = {"detail": "If that email is registered, a reset link has been sent."}


class PasswordResetRequestView(APIView):
    """POST {"email": "..."} -> always the same response, so a caller can
    never learn whether an email exists or which role it belongs to."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(
            email__iexact=email, role__in=RESETTABLE_ROLES, is_active=True
        ).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

            send_mail(
                subject="Reset your password",
                message=(
                    f"Hi {user.username},\n\n"
                    "We received a request to reset your password. This link "
                    "is valid for 1 hour and can only be used once:\n\n"
                    f"{reset_link}\n\n"
                    "If you didn't request this, you can safely ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        return Response(GENERIC_RESPONSE, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """POST {"uid", "token", "password"} -> sets the new password."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        try:
            pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=pk, role__in=RESETTABLE_ROLES, is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None

        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"detail": "Your password has been reset."}, status=status.HTTP_200_OK)

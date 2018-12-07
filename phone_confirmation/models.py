from __future__ import unicode_literals
import secrets
import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from phone_confirmation.fields import RandomPinField
from phone_confirmation.signals import confirmation_sms_sent, activation_key_created
from phonenumber_field.modelfields import PhoneNumberField
from sendsms import api

logger = logging.getLogger(__name__)

phone_settings = getattr(settings, 'PHONE_CONFIRMATION', {})

SALT = phone_settings.get('SALT', 'phonenumber')
ACTIVATION_TIMEOUT = phone_settings.get('ACTIVATION_TIMEOUT', 15 * 60)  # Seconds
TOKEN_PERIOD = phone_settings.get('TOKEN_PERIOD', 1)  # 1 hour as default
SMS_MESSAGE = phone_settings.get('SMS_MESSAGE', 'Your confirmation code is %(code)s')
FROM_NUMBER = phone_settings.get('FROM_NUMBER', '')
MAX_CONFIRMATIONS = phone_settings.get('MAX_CONFIRMATIONS', 10)
SILENT_CONFIRMATIONS_FILTER = phone_settings.get('SILENT_CONFIRMATIONS_FILTER', None)
CODE_LENGTH = phone_settings.get('CONFIRMATION_CODE_LENGTH', 6)


def generate_token():
    return secrets.token_urlsafe(32)


def token_period_expiration_date():
    return timezone.now() + timezone.timedelta(hours=TOKEN_PERIOD)


class PhoneConfirmationManager(models.Manager):
    """Manager for PhoneConfirmation model."""

    def validate_key(self, activation_key):
        """
        Check if the activation_key is valid and not expired.

        Return phone number if it is valid or None otherwise.
        """
        try:
            phone_number = signing.loads(
                activation_key,
                salt=SALT,
                max_age=ACTIVATION_TIMEOUT
            )
            return phone_number.get('phone_number')
        except signing.BadSignature:
            return None

    def get_confirmation_code(self, phone_number, code, id=None):
        """Get the PhoneConfirmation for the phone number and code."""
        time_threshold = timezone.now() - timedelta(minutes=ACTIVATION_TIMEOUT)
        if id is not None:
            return self.get(pk=id)
        else:
            return self.get_queryset().filter(created_at__gte=time_threshold,
                                              phone_number=phone_number,
                                              code=code).order_by('-created_at').first()

    def clear_phone_number_confirmations(self, phone_number):
        """Remove all confirmations for the phone number."""
        self.get_queryset().filter(phone_number=phone_number).delete()


class PhoneConfirmation(models.Model):
    """Store confirmation codes for phone number."""
    created_at = models.DateTimeField(auto_now_add=True)
    phone_number = PhoneNumberField(db_index=True)
    code = RandomPinField(length=CODE_LENGTH)
    first_name = models.CharField(null=True, blank=True, max_length=120)
    objects = PhoneConfirmationManager()
    activation_key = models.CharField(unique=True, default=generate_token, max_length=256)

    class Meta:
        index_together = (('created_at', 'phone_number', 'code'), ('phone_number', 'code'))

    @property
    def expiration_date(self):
        return token_period_expiration_date()

    def __str__(self):
        return str(self.phone_number)

    @staticmethod
    def _get_activation_key(phone_number):
        return signing.dumps(
            obj={'phone_number': str(phone_number)},
            salt=SALT
        )

    def _send_signal_and_log(self, signal, **kwargs):
        """Replacement for Signal.send_robust with logging"""
        rvs = signal.send_robust(sender=self.__class__, **kwargs)
        for f, exc in rvs:
            if exc is not None:
                logger.error("signal handler %s failed on %r",
                             getattr(f, '__name__', f), self,
                             exc_info=(type(exc), exc, exc.__traceback__))

    def send_sms(self, request=None):
        message = SMS_MESSAGE % {'code': self.code}
        to = str(self.phone_number)
        if callable(SILENT_CONFIRMATIONS_FILTER) and SILENT_CONFIRMATIONS_FILTER(to) is True:
            logger.debug("Filtered phone confirmation SMS to:%s text:%s", to, message)
            return

        api.send_sms(body=message,
                     from_phone=FROM_NUMBER,
                     to=[to])
        self._send_signal_and_log(confirmation_sms_sent, phone_number=self.phone_number)

    def send_activation_key_created_signal(self, user=None):
        self._send_signal_and_log(activation_key_created, user=user,
                                  phone_number=self.phone_number, first_name=self.first_name,
                                  expiration_date=self.expiration_date, activation_key=self.activation_key)


@receiver(post_save, sender=PhoneConfirmation)
def post_save_phone_confirmation_receiver(sender, instance, created, **kwargs):
    if created:
        if PhoneConfirmation.objects.filter(phone_number=instance.phone_number).count() > MAX_CONFIRMATIONS:
            PhoneConfirmation.objects.filter(phone_number=instance.phone_number).order_by('created_at').first().delete()
        instance.send_sms()

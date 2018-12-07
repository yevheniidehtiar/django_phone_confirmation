import logging

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from phone_confirmation.models import PhoneConfirmation
from phone_confirmation.serializers import (ActivationKeySerializer, ConfirmationMobileSerializer,
                                            ConfirmationSerializer, ActivationKeyMobileSerializer)

logger = logging.getLogger(__name__)


class ConfirmationView(generics.CreateAPIView):
    serializer_class = ConfirmationSerializer
    throttle_scope = 'phone-confirmation-confirmation'


class ActivationKeyView(APIView):
    throttle_scope = 'phone-confirmation-activation-key'

    def post(self, request, *args, **kwargs):
        serializer = ActivationKeySerializer(data=request.data, context={'user': request.user})
        if serializer.is_valid():
            return Response(status=status.HTTP_200_OK, data=serializer.data)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST, data=serializer.errors)


class GetActivationKeyView(APIView):
    throttle_scope = 'phone-confirmation-activation-key'

    def get(self, request, activation_key, *args, **kwargs):
        try:
            phone_number = PhoneConfirmation.objects.validate_key(activation_key)
            if phone_number:
                return Response(status=status.HTTP_200_OK, data={'phone_number': phone_number})
        except Exception:
            logger.exception('Error decoding activation key')

        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Invalid activation key'})


class ConfirmationMobileView(generics.CreateAPIView):
    serializer_class = ConfirmationMobileSerializer
    throttle_scope = 'mobile-api-get-confirmation-code'


class ActivationKeyMobileView(APIView):
    throttle_scope = 'mobile-api-activate-confirmation-code'

    def post(self, request, *args, **kwargs):
        serializer = ActivationKeyMobileSerializer(data=request.data)
        if serializer.is_valid():
            return Response(status=status.HTTP_200_OK, data=serializer.data)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST, data=serializer.errors)

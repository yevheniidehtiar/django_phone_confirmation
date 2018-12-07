from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from phone_confirmation.models import PhoneConfirmation


class ConfirmationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneConfirmation
        fields = ('phone_number', 'first_name')


class ConfirmationMobileSerializer(serializers.ModelSerializer):
    confirmation_id = serializers.SerializerMethodField('get_pk')

    class Meta:
        model = PhoneConfirmation
        fields = ('confirmation_id', 'phone_number')

    def get_pk(self, obj):
        return obj.pk


class ActivationKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneConfirmation
        fields = ('phone_number', 'code', 'activation_key')
        extra_kwargs = {
            'phone_number': {'write_only': True, 'required': True},
            'code': {'read_only': True},
            'activation_key': {'read_only': True},
        }

    def is_valid(self, raise_exception=False):
        is_valid = super(ActivationKeySerializer, self).is_valid(raise_exception=raise_exception)
        self.instance = self.Meta.model.objects.get_confirmation_code(
            phone_number=self.validated_data.get('phone_number'),
            code=self.validated_data.get('code'))
        if is_valid:
            if self.instance:
                user = self.context.get('user')
                self.instance.send_activation_key_created_signal(user=user)
                self.Meta.model.objects.clear_phone_number_confirmations(
                    phone_number=self.validated_data['phone_number'])
            else:
                raise serializers.ValidationError({"error": _("The code or phone number are invalid.")})
        return is_valid


class ActivationKeyMobileSerializer(serializers.ModelSerializer):
    """ Hardcoded copy original serializer for mobile """
    confirmation_code = serializers.SerializerMethodField('get_code')
    auth_token = serializers.SerializerMethodField('get_token')
    confirmation_id = serializers.SerializerMethodField('get_pk')

    class Meta:
        model = PhoneConfirmation
        fields = ('auth_token', 'confirmation_id', 'confirmation_code')
        extra_kwargs = {
            'auth_token': {'read_only': True},
            'confirmation_id': {'write_only': True},
            'confirmation_id': {'confirmation_code': True},
        }

    def get_code(self, obj):
        return obj.code

    def get_token(self, obj):
        return obj.activation_key

    def get_pk(self, obj):
        return obj.pk

    def is_valid(self, raise_exception=False):
        is_valid = super(ActivationKeyMobileSerializer, self).is_valid(raise_exception=raise_exception)
        self.instance = self.Meta.model.objects. \
            get_confirmation_code(id=self.validated_data.get('confirmation_id'),
                                  code=self.validated_data.get('confirmation_code'))
        if is_valid:
            if self.instance:
                self.instance.send_activation_key_created_signal()
                self.Meta.model.objects.clear_phone_number_confirmations(
                    phone_number=self.instance['phone_number'])
            else:
                raise serializers.ValidationError({"error": _("The confirmation code or id are invalid.")})
        return is_valid

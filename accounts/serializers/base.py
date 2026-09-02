from rest_framework import serializers


class StrictFieldsMixin:
    """Reject any request key that isn't a declared serializer field."""

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            f"Unknown field(s): {', '.join(unknown)}."
                        ],
                        **{
                            name: f"The field '{name}' is not allowed."
                            for name in unknown
                        },
                    }
                )
        return super().to_internal_value(data)

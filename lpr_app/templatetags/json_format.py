import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='json_format')
def json_format(value):
    if value is None:
        return ''
    try:
        formatted = json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
    return mark_safe(formatted)

from django import template

from utils.seo import trim_meta_description

register = template.Library()


@register.filter
def meta_description(value, arg=160):
    try:
        limit = int(arg)
    except (TypeError, ValueError):
        limit = 160
    return trim_meta_description(value, limit=limit)

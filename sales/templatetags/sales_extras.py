from django import template

register = template.Library()

@register.simple_tag
def check_match(value, expected, output_string='selected'):
    """
    Compares value and expected. If they match, returns output_string.
    Usage: {% check_match var1 var2 'selected' %}
    """
    # Handle string comparison loose typing if needed, but strict is safer for now.
    # Convert both to string for comparison to match Django template loose behavior if needed.
    if str(value) == str(expected):
        return output_string
    return ''

from django import template


register = template.Library()


@register.filter
def segundos_mmss(valor):
    """Formata segundos como mm:ss, ou h:mm:ss a partir de uma hora."""
    try:
        total = max(0, int(valor))
    except (TypeError, ValueError):
        return "00:00"
    horas, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segundos:02d}"
    return f"{minutos:02d}:{segundos:02d}"

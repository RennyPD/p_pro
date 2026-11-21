"""Spanish messages for request validation errors shown in the interface."""

FIELD_LABELS = {
    "username": "usuario",
    "password": "contraseña",
    "new_password": "nueva contraseña",
    "current_password": "contraseña actual",
    "email": "correo",
    "first_name": "nombres",
    "last_name": "apellidos",
    "telephone": "teléfono",
    "address": "dirección",
    "reason": "motivo",
    "name": "nombre",
    "code": "código",
    "description": "descripción",
    "amount": "monto",
    "date": "fecha",
    "capacity": "cupo",
    "credits": "créditos",
    "weight": "peso",
    "grade_value": "nota",
    "title": "título",
    "message": "mensaje",
}


def _field(loc) -> str:
    names = [
        str(part)
        for part in loc
        if part not in ("body", "query", "path") and not isinstance(part, int)
    ]
    if not names:
        return ""
    return FIELD_LABELS.get(names[-1], names[-1].replace("_", " "))


def spanish_message(error: dict) -> str:
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    field = _field(error.get("loc", ()))
    prefix = f"{field.capitalize()}: " if field else ""
    if kind == "value_error":
        # Custom validators already speak Spanish; drop Pydantic's English prefix.
        return str(error.get("msg", "")).removeprefix("Value error, ")
    if kind == "assertion_error":
        return str(error.get("msg", "")).removeprefix("Assertion failed, ")
    messages = {
        "missing": "es obligatorio",
        "string_too_short": f"debe tener al menos {ctx.get('min_length')} caracteres",
        "string_too_long": f"admite como máximo {ctx.get('max_length')} caracteres",
        "string_pattern_mismatch": "tiene un formato no válido",
        "string_type": "debe ser texto",
        "int_parsing": "debe ser un número entero",
        "int_type": "debe ser un número entero",
        "float_parsing": "debe ser un número",
        "float_type": "debe ser un número",
        "decimal_parsing": "debe ser un número",
        "bool_parsing": "debe ser sí o no",
        "greater_than": f"debe ser mayor que {ctx.get('gt')}",
        "greater_than_equal": f"debe ser mayor o igual que {ctx.get('ge')}",
        "less_than": f"debe ser menor que {ctx.get('lt')}",
        "less_than_equal": f"debe ser menor o igual que {ctx.get('le')}",
        "date_parsing": "debe ser una fecha válida",
        "date_from_datetime_parsing": "debe ser una fecha válida",
        "datetime_parsing": "debe ser una fecha y hora válidas",
        "datetime_from_date_parsing": "debe ser una fecha y hora válidas",
        "time_parsing": "debe ser una hora válida",
        "enum": "no es una opción válida",
        "literal_error": "no es una opción válida",
        "list_type": "debe ser una lista",
        "too_short": f"necesita al menos {ctx.get('min_length')} elementos",
        "too_long": f"admite como máximo {ctx.get('max_length')} elementos",
        "extra_forbidden": "no se admite",
        "json_invalid": "el contenido enviado no es válido",
        "model_attributes_type": "el contenido enviado no es válido",
        "dict_type": "el contenido enviado no es válido",
    }
    if kind in messages:
        return f"{prefix}{messages[kind]}" if field else messages[kind].capitalize()
    if "email" in str(error.get("msg", "")).lower():
        return f"{prefix}no es un correo válido" if field else "Correo no válido"
    return f"{prefix}valor no válido" if field else "Valor no válido"

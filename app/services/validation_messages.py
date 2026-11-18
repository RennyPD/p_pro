"""Spanish messages for request validation errors (audit M6).

Pydantic reports errors in English. The API keeps `loc` and `type` so clients
can react programmatically, and replaces `msg` with a Spanish sentence.
"""

from typing import Any

_PREFIXES = ("Value error, ", "Assertion failed, ")

_STATIC = {
    "missing": "Este campo es obligatorio",
    "string_type": "Debe ser un texto",
    "int_type": "Debe ser un número entero",
    "int_parsing": "Debe ser un número entero",
    "int_from_float": "Debe ser un número entero",
    "float_type": "Debe ser un número",
    "float_parsing": "Debe ser un número",
    "decimal_type": "Debe ser un número",
    "decimal_parsing": "Debe ser un número",
    "finite_number": "Debe ser un número finito",
    "bool_type": "Debe ser verdadero o falso",
    "bool_parsing": "Debe ser verdadero o falso",
    "date_type": "Debe ser una fecha válida (AAAA-MM-DD)",
    "date_parsing": "Debe ser una fecha válida (AAAA-MM-DD)",
    "date_from_datetime_parsing": "Debe ser una fecha válida (AAAA-MM-DD)",
    "date_from_datetime_inexact": "La fecha no debe incluir hora",
    "datetime_type": "Debe ser una fecha y hora válidas",
    "datetime_parsing": "Debe ser una fecha y hora válidas",
    "datetime_from_date_parsing": "Debe ser una fecha y hora válidas",
    "time_type": "Debe ser una hora válida (HH:MM)",
    "time_parsing": "Debe ser una hora válida (HH:MM)",
    "list_type": "Debe ser una lista",
    "dict_type": "Debe ser un objeto",
    "model_type": "El formato de los datos no es válido",
    "model_attributes_type": "El formato de los datos no es válido",
    "json_invalid": "El cuerpo de la petición no es un JSON válido",
    "json_type": "El cuerpo de la petición no es un JSON válido",
    "extra_forbidden": "Este campo no está permitido",
    "url_parsing": "Debe ser una dirección web válida",
    "url_scheme": "Debe ser una dirección web válida",
    "uuid_parsing": "Debe ser un identificador válido",
}

_TEMPLATES = {
    "string_too_short": "Debe tener al menos {min_length} caracteres",
    "string_too_long": "Debe tener como máximo {max_length} caracteres",
    "too_short": "Debe tener al menos {min_length} elementos",
    "too_long": "Debe tener como máximo {max_length} elementos",
    "greater_than": "Debe ser mayor que {gt}",
    "greater_than_equal": "Debe ser mayor o igual que {ge}",
    "less_than": "Debe ser menor que {lt}",
    "less_than_equal": "Debe ser menor o igual que {le}",
    "multiple_of": "Debe ser múltiplo de {multiple_of}",
    "decimal_max_digits": "Debe tener como máximo {max_digits} dígitos",
    "decimal_max_places": "Debe tener como máximo {decimal_places} decimales",
    "enum": "Valor no válido. Opciones: {expected}",
    "literal_error": "Valor no válido. Opciones: {expected}",
    "string_pattern_mismatch": "El formato no es válido",
}


def spanish_message(error: dict[str, Any]) -> str:
    kind = error.get("type", "")
    ctx = {key: str(value) for key, value in (error.get("ctx") or {}).items()}
    if kind in _STATIC:
        return _STATIC[kind]
    if kind in _TEMPLATES:
        try:
            return _TEMPLATES[kind].format(**ctx)
        except KeyError:
            return "El valor no es válido"
    if kind in {"value_error", "assertion_error"}:
        message = str(error.get("msg", ""))
        for prefix in _PREFIXES:
            message = message.removeprefix(prefix)
        if "email address" in message:
            return "El correo electrónico no es válido"
        return message or "El valor no es válido"
    return "El valor no es válido"

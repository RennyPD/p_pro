from enum import Enum
from unicodedata import combining, normalize


class DayEnum(str, Enum):
    LUNES = "Lunes"
    MARTES = "Martes"
    MIERCOLES = "Miércoles"
    JUEVES = "Jueves"
    VIERNES = "Viernes"
    SABADO = "Sábado"
    DOMINGO = "Domingo"


def day_key(value: str) -> str:
    return "".join(
        letter for letter in normalize("NFKD", value.casefold().strip()) if not combining(letter)
    )


_DAY_NAMES = {day_key(day.value): day.value for day in DayEnum}
_DAY_NAMES.update(
    zip(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        (day.value for day in DayEnum),
    )
)
DAY_ORDER = {day.value: index for index, day in enumerate(DayEnum)}


def canonical_day(value: str) -> str | None:
    return _DAY_NAMES.get(day_key(value))

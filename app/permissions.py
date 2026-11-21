"""Single source of truth for what a role can do (permissions) and over which data (scope).

Every route checks a permission from PERMISSIONS. A role's *scope* decides which
records those permissions reach:

- institution: every record of the institution.
- sections: only the sections taught by the linked teacher and their students.
- own: only the linked student's own record.
- linked: only the students linked to the guardian account.

Legacy broad grants (academic.manage, operations.manage, access.manage) are still
understood as bundles of the granular permissions, so data saved before the
catalog keeps working; migration 20261120_0046 converts it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    slug: str
    module: str
    label: str
    description: str


PERMISSIONS: tuple[PermissionDef, ...] = (
    # Comunidad académica
    PermissionDef(
        "students.view", "Estudiantes", "Consultar estudiantes", "Directorio y expedientes"
    ),
    PermissionDef(
        "students.manage",
        "Estudiantes",
        "Gestionar estudiantes",
        "Crear, editar, importar y trasladar",
    ),
    PermissionDef("teachers.view", "Docentes", "Consultar docentes", "Directorio y carga docente"),
    PermissionDef("teachers.manage", "Docentes", "Gestionar docentes", "Crear y editar docentes"),
    # Oferta académica
    PermissionDef(
        "programs.view",
        "Oferta académica",
        "Consultar oferta académica",
        "Carreras, asignaturas y períodos, sin editarlos",
    ),
    PermissionDef(
        "programs.manage",
        "Oferta académica",
        "Gestionar carreras y pensum",
        "Carreras, versiones del pensum, asignaturas y requisitos",
    ),
    PermissionDef(
        "equivalences.manage",
        "Oferta académica",
        "Gestionar equivalencias",
        "Reglas de reconocimiento entre asignaturas",
    ),
    PermissionDef("sections.view", "Secciones", "Consultar secciones", "Oferta, cupos y listas"),
    PermissionDef(
        "sections.manage", "Secciones", "Gestionar secciones", "Crear, editar y publicar secciones"
    ),
    PermissionDef(
        "schedule.manage", "Secciones", "Gestionar horarios", "Bloques de horario de las secciones"
    ),
    PermissionDef(
        "classrooms.manage", "Secciones", "Gestionar aulas", "Crear, editar y retirar aulas"
    ),
    PermissionDef(
        "enrollments.manage",
        "Secciones",
        "Gestionar inscripciones",
        "Inscribir, retirar y corregir selecciones de estudiantes",
    ),
    # Seguimiento académico
    PermissionDef(
        "grades.view", "Calificaciones", "Consultar calificaciones", "Resultados y libro de notas"
    ),
    PermissionDef(
        "grades.manage",
        "Calificaciones",
        "Gestionar calificaciones",
        "Plan de evaluación, notas, publicación y cierre",
    ),
    PermissionDef("attendance.view", "Asistencia", "Consultar asistencia", "Resúmenes y detalle"),
    PermissionDef(
        "attendance.manage", "Asistencia", "Registrar asistencia", "Pase de lista y correcciones"
    ),
    PermissionDef(
        "tasks.manage",
        "Agenda y tareas",
        "Gestionar tareas",
        "Crear, calificar y planificar clases",
    ),
    PermissionDef(
        "calendar.manage", "Agenda y tareas", "Gestionar agenda", "Eventos del calendario académico"
    ),
    # Institución
    PermissionDef(
        "finance.view", "Finanzas", "Consultar finanzas", "Cuentas, balances y movimientos"
    ),
    PermissionDef(
        "finance.manage",
        "Finanzas",
        "Gestionar finanzas",
        "Cargos, pagos, ajustes, transferencias y caja",
    ),
    PermissionDef(
        "admissions.manage", "Admisiones", "Gestionar admisiones", "Solicitudes y matrícula"
    ),
    PermissionDef(
        "cases.manage", "Seguimiento", "Gestionar casos", "Alertas tempranas e intervenciones"
    ),
    PermissionDef(
        "approvals.manage",
        "Seguimiento",
        "Resolver solicitudes",
        "Aprobar o rechazar solicitudes de revisión",
    ),
    PermissionDef(
        "communications.manage", "Comunicaciones", "Publicar avisos", "Avisos y notificaciones"
    ),
    PermissionDef(
        "reports.view", "Reportes", "Consultar reportes", "Control institucional e indicadores"
    ),
    PermissionDef(
        "audit.view", "Reportes", "Consultar auditoría", "Historial de cambios sensibles"
    ),
    # Administración
    PermissionDef(
        "settings.manage",
        "Configuración",
        "Gestionar configuración",
        "Datos institucionales, reglas y períodos académicos",
    ),
    PermissionDef("users.manage", "Configuración", "Gestionar usuarios", "Cuentas y contraseñas"),
    PermissionDef(
        "roles.manage", "Configuración", "Gestionar roles", "Crear roles y asignar sus permisos"
    ),
    # Portales personales
    PermissionDef(
        "records.own",
        "Portal personal",
        "Consultar su información",
        "Expediente, horario, notas, asistencia y cuenta propios o de estudiantes vinculados",
    ),
    PermissionDef(
        "selection.own",
        "Portal personal",
        "Elegir asignaturas",
        "Selección de asignaturas en el período de inscripción",
    ),
)

PERMISSION_SLUGS = frozenset(item.slug for item in PERMISSIONS)

SCOPES = {
    "institution": "Toda la institución",
    "sections": "Sus secciones (cuenta vinculada a un docente)",
    "own": "Su propio expediente (cuenta vinculada a un estudiante)",
    "linked": "Estudiantes vinculados (cuenta de tutor)",
}

# Administering the institution itself: only meaningful with institution scope.
# A role limited to its sections (or a personal portal) never gets them, even if
# they are granted by mistake.
INSTITUTIONAL_PERMISSIONS = frozenset(
    {
        "students.manage",
        "teachers.manage",
        "programs.manage",
        "equivalences.manage",
        "sections.manage",
        "classrooms.manage",
        "enrollments.manage",
        "finance.view",
        "finance.manage",
        "admissions.manage",
        "approvals.manage",
        "reports.view",
        "audit.view",
        "settings.manage",
        "users.manage",
        "roles.manage",
    }
)

# Broad grants used before the catalog. Holding one means holding its bundle.
LEGACY_BUNDLES: dict[str, frozenset[str]] = {
    "academic.manage": frozenset(
        {
            "students.view",
            "students.manage",
            "teachers.view",
            "teachers.manage",
            "programs.manage",
            "equivalences.manage",
            "sections.view",
            "sections.manage",
            "classrooms.manage",
            "enrollments.manage",
            "grades.view",
            "attendance.view",
            "settings.manage",
        }
    ),
    "operations.manage": frozenset(
        {"tasks.manage", "calendar.manage", "admissions.manage", "cases.manage", "approvals.manage"}
    ),
    "access.manage": frozenset({"users.manage", "roles.manage"}),
    "reports.view": frozenset({"reports.view", "audit.view"}),
    "finance.manage": frozenset({"finance.view", "finance.manage"}),
    "grades.manage": frozenset(
        {"grades.view", "grades.manage", "attendance.view", "attendance.manage"}
    ),
}

# What the built-in roles can do. Used to seed new installations and for databases
# whose permission catalog is still empty.
SYSTEM_ROLE_DEFAULTS: dict[str, tuple[str, frozenset[str]]] = {
    "admin": ("institution", PERMISSION_SLUGS - {"records.own", "selection.own"}),
    "teacher": (
        "sections",
        frozenset(
            {
                "students.view",
                "sections.view",
                "grades.view",
                "grades.manage",
                "attendance.view",
                "attendance.manage",
                "tasks.manage",
                "calendar.manage",
                "cases.manage",
                "communications.manage",
            }
        ),
    ),
    "student": ("own", frozenset({"records.own", "selection.own"})),
    "guardian": ("linked", frozenset({"records.own"})),
}


def expand(slugs: set[str] | frozenset[str]) -> frozenset[str]:
    """Granular permissions held, unfolding legacy bundles."""
    result = set(slugs)
    for slug in slugs:
        result |= LEGACY_BUNDLES.get(slug, frozenset())
    return frozenset(result)


def default_scope(role_name: str) -> str:
    return SYSTEM_ROLE_DEFAULTS.get(role_name.casefold(), ("institution", frozenset()))[0]

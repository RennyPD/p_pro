# Guía de validación integral de Nexo

## Accesos locales

| Perfil | Usuario | Contraseña |
| --- | --- | --- |
| Administración | `admin.horizonte` | `NexoAdmin2026!` |
| Docente | `profesor.01` | `NexoDocente2026!` |
| Estudiante | `estudiante.001` | `NexoEstudiante2026!` |
| Tutor | `tutor.01` | `NexoTutor2026!` |

## 1. Selección académica

1. Entra como estudiante y abre **Elegir asignaturas**.
2. Confirma carga de créditos, secciones confirmadas y lista de espera.
3. Selecciona una sección y valida que se actualice el horario.
4. Intenta seleccionar una materia repetida o con choque de horario.
5. Retira una materia y confirma la actualización del resumen.

## 2. Evaluaciones y calificaciones

1. Entra como docente y abre **Evaluaciones**.
2. Crea componentes cuya suma no exceda 100 %.
3. Registra notas para todos los estudiantes y cierra la evaluación.
4. Verifica en **Calificaciones** el promedio por sección y el detalle por estudiante.
5. Comprueba como administrador que una evaluación cerrada puede reabrirse.

## 3. Asistencia

1. Abre una sección como docente y registra asistencia.
2. Usa presente, ausencia, tardanza o justificación desde la gestión de asistencia.
3. Abre **Asistencia** y comprueba promedio por sección e historial por estudiante.
4. Valida que el estudiante vea únicamente su resumen.

## 4. Oferta y horarios

1. Como administrador crea o edita una sección con docente, asignatura, período, cupos, modalidad y estado.
2. Confirma las vistas de horario en lista, semana, 12 horas y 24 horas.
3. Intenta crear reuniones superpuestas para docente o aula.
4. En **Configuración → Períodos académicos**, intenta cerrar un período con evaluaciones incompletas y confirma el bloqueo.
5. Completa y cierra las evaluaciones, vuelve a cerrar el período y verifica que las selecciones queden consolidadas.

## 5. Carreras y pensum

1. Crea una carrera con código, título, duración, créditos requeridos y versión de pensum.
2. Agrega materias obligatorias, electivas, pasantía o trabajo de grado.
3. Configura prerrequisitos y correquisitos.
4. Abre el detalle de la carrera y revisa créditos por período.
5. Registra una equivalencia y comprueba que sea reconocida en la auditoría de graduación.

## 6. Expediente

1. Abre un estudiante y revisa promedio, asistencia y trayectoria.
2. Como estudiante abre **Mi expediente** y **Mi progreso**.
3. Comprueba créditos aprobados, materias repetidas y condición académica.
4. Abre **Mi graduación** y revisa créditos pendientes, avance y requisitos obligatorios.

## 7–9. Seguimiento, aula y admisiones

1. Abre **Agenda y tareas** y crea eventos, tareas y planes de clase.
2. Entrega una tarea como estudiante y califícala como docente.
3. Genera alertas tempranas y comprueba su visibilidad.
4. En **Control institucional**, asigna un responsable y una fecha de seguimiento a una alerta.
5. Registra una actuación con el resultado de una llamada o reunión y luego resuelve el caso con una conclusión.
6. Cambia el estado de una admisión aceptada y conviértela en estudiante.
7. Abre **Casos y seguimientos**, consulta el historial de actuaciones, resuelve un caso y comprueba que puede reabrirse.

## Portal familiar

1. Entra como `tutor.01` y abre **Seguimiento familiar**.
2. Comprueba promedio, asistencia, balance, horario y alertas del estudiante vinculado.
3. Verifica que el tutor no vea herramientas para crear tareas ni publicar comunicaciones.
4. Si el tutor tiene varios estudiantes, cambia la selección y confirma que cada resumen sea independiente.

## 10–11. Reportes, permisos y auditoría

1. Revisa los indicadores de **Control institucional** y compara permanencia, promedio, asistencia y alertas por carrera.
2. Comprueba que **Asignaturas críticas** ordene primero las materias con menor aprobación y rendimiento.
3. Confirma que los contadores de riesgo cambien al asignar o resolver una alerta.
4. Exporta expedientes CSV desde la API o documentación interactiva.
5. Asigna permisos a un rol y confirma la consulta de permisos propios.
6. Retira temporalmente `finance.manage`, `grades.manage` o `academic.manage` de un rol de prueba y confirma que desaparece la opción correspondiente y que la API responde 403.
7. Devuelve el permiso y comprueba que el acceso se restaura sin cambiar el rol.
8. Verifica eventos sensibles en el historial de auditoría.

## 12. Experiencia y accesibilidad

1. Repite los recorridos en una ventana móvil.
2. Navega formularios mediante teclado.
3. Comprueba mensajes de carga, error y listas vacías.
4. Confirma que cada perfil solo muestra opciones autorizadas.

# Manual funcional de Nexo

Nexo organiza la operación académica local en tres espacios: administración, docencia y estudiante. No procesa pagos externos ni envía mensajes por servicios de terceros.

## Flujo recomendado

1. Configurar institución, período activo, carreras, asignaturas y pensum.
2. Registrar docentes, estudiantes y usuarios vinculados a cada persona.
3. Crear aulas, secciones y reuniones semanales sin cruces de horario.
4. Abrir el período de inscripción, asignar estudiantes y gestionar cupos o lista de espera.
5. Crear evaluaciones cuya ponderación total no exceda 100 %.
6. Registrar asistencia y calificaciones desde el espacio de cada sección.
7. Cerrar evaluaciones para impedir cambios accidentales y consultar el expediente.
8. Registrar cargos, ajustes, planes y pagos internos; descargar estados de cuenta.
9. Vincular tutores y publicar avisos internos por audiencia.

## Reglas principales

- Una inscripción no puede duplicar estudiante, sección y período.
- El cupo de una sección se respeta; al agotarse, la solicitud pasa a espera cuando corresponde.
- Bloqueos académicos o financieros impiden nuevas inscripciones.
- Se validan prerrequisitos, máximo de créditos y choques de horario.
- Una evaluación cerrada no admite nuevas calificaciones hasta reabrirse.
- Las notas están entre 0 y 100; la nota final ponderada usa las evaluaciones configuradas.
- Docentes solo acceden a sus secciones y estudiantes vinculados a ellas.
- Estudiantes solo ven sus datos personales, académicos y financieros.
- El historial financiero es contable e interno; no representa confirmación bancaria.
- Las notificaciones son privadas para su destinatario y registran cuándo fueron leídas.
- Los PDF se generan al solicitarlos y no se almacenan como archivos permanentes.

## Documentos y reportes

- Expediente PDF: `GET /documents/students/{id}/transcript.pdf`.
- Estado de cuenta PDF: `GET /documents/students/{id}/statement.pdf`.
- Lista de sección PDF: `GET /documents/sections/{id}/roster.pdf`.
- Resumen académico CSV: `GET /records/reports/students.csv`.
- Estudiantes CSV: importación y exportación desde las herramientas masivas.

## Seguridad operativa

- Access token breve y renovación mediante cookie HttpOnly.
- Límite de intentos fallidos de inicio de sesión.
- Cambio de contraseña revoca sesiones anteriores.
- `GET /auth/sessions` muestra el historial de sesiones del usuario.
- `POST /auth/sessions/revoke-all` revoca todas sus renovaciones.
- Auditoría de accesos y eventos sensibles visible solo para administración.
- Segundo factor TOTP opcional, compatible con aplicaciones autenticadoras estándar.

## Lista de revisión manual

- Entrar con cada perfil de demostración y confirmar que el menú cambia según el rol.
- Inscribir un estudiante, crear dos evaluaciones que sumen 100 % y registrar notas.
- Pasar asistencia, cerrar una evaluación y comprobar que ya no acepta cambios.
- Descargar expediente, lista de sección y estado de cuenta.
- Publicar un aviso para estudiantes y marcarlo leído desde la cuenta estudiantil.
- Confirmar que un docente no abre secciones ajenas y un estudiante no abre datos de otro.

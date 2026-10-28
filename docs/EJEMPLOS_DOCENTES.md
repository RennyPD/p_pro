# Docentes de demostración

Se agregan 12 expedientes completos, identificados por los códigos `DEMO-DOC-001` a `DEMO-DOC-012` y el apellido **Demo**. Son datos ficticios: los teléfonos no deben marcarse y los documentos y registros profesionales no tienen validez. No sustituyen ni modifican los docentes anteriores.

## Cómo explorarlos

1. Entra como administrador y abre **Docentes**.
2. Busca `DEMO-DOC` para ver los ejemplos. El directorio muestra 10 registros por página; utiliza **Siguiente** para ver los demás.
3. Abre **Mariana Valdez Demo**, código `DEMO-DOC-001`, para revisar una ficha completa.
4. Recorre **Resumen**, **Perfil profesional**, **Vinculación institucional**, **Carga y horario** y **Datos y contactos**.
5. Pulsa **Editar expediente** para ver cómo se distribuyen los campos en el formulario.
6. Prueba los filtros de departamento, situación y vinculación. Hay 10 docentes activos y 2 inactivos; cada tipo de vinculación tiene 3 ejemplos.

## Qué significa cada campo

| Campo | Ejemplo | Uso |
|---|---|---|
| Nombres | Mariana | Nombres de la persona. |
| Apellidos | Valdez Demo | Apellidos; “Demo” identifica este ejemplo. |
| Documento de identidad | DEMO-NO-VALIDO-001 | Identificador personal, distinto del código de empleado. En estos ejemplos no es una cédula válida. |
| Fecha de nacimiento | 12 de enero de 1983 | Dato personal; no es la fecha de contratación. |
| Nacionalidad | Dominicana | Nacionalidad registrada. |
| Correo | docente.demo.01@example.com | Contacto del docente; no crea una cuenta de acceso. |
| Teléfono | 809-000-0101 | Contacto directo, ficticio en este conjunto. |
| Dirección | Calle Ficticia 1, Residencial de Pruebas… | Domicilio del docente, no el aula donde enseña. |
| Especialidad | Didáctica y evaluación educativa | Área de conocimiento o práctica profesional. |
| Título o grado académico | Doctorado en Educación | Formación académica alcanzada; no es una asignatura. |
| Institución de formación | Universidad Ficticia Horizonte de Pruebas | Institución donde obtuvo su formación. |
| Registro o habilitación profesional | DEMO-REG-001 (sin validez) | Referencia profesional, cuando corresponda. No demuestra por sí sola una acreditación verificada. |
| Años de experiencia docente | 18 | Trayectoria docente total, no solo antigüedad en esta institución. |
| Código institucional | DEMO-DOC-001 | Identificador interno del empleado. No es su usuario ni contraseña. |
| Departamento o área académica | Educación | Agrupación institucional usada también para filtrar el directorio. |
| Categoría docente | Titular | Clasificación académica: los ejemplos incluyen titular, adjunto, instructor y auxiliar. Actualmente es texto libre, no una escala salarial automática. |
| Tipo de vinculación | Tiempo completo | Modalidad laboral: tiempo completo, tiempo parcial, por asignatura o suplente. No se refiere a presencial/virtual. |
| Fecha de ingreso a la institución | 15 de enero de 2018 | Inicio de la vinculación institucional. |
| Docente activo | Sí | Situación del registro docente; no equivale a tener secciones o una cuenta de acceso. |
| Nombre del contacto | Contacto Ficticio 01 Demo | Persona a contactar ante una emergencia. |
| Teléfono de emergencia | 809-000-0201 | Teléfono del contacto, diferente del teléfono del docente. |
| Parentesco o relación | Hermana | Vínculo con el contacto de emergencia. |

## Casos incluidos

| Código | Docente | Departamento | Vinculación | Situación |
|---|---|---|---|---|
| DEMO-DOC-001 | Mariana Valdez Demo | Educación | Tiempo completo | Activo |
| DEMO-DOC-002 | Gabriel Peña Demo | Tecnología | Tiempo parcial | Activo |
| DEMO-DOC-003 | Camila Rosario Demo | Ciencias Empresariales | Por asignatura | Activo |
| DEMO-DOC-004 | Andrés Pimentel Demo | Ciencias Básicas | Suplente | Activo |
| DEMO-DOC-005 | Valeria Núñez Demo | Ciencias Empresariales | Tiempo completo | Activo |
| DEMO-DOC-006 | Samuel Báez Demo | Tecnología | Tiempo parcial | Activo |
| DEMO-DOC-007 | Isabel Matos Demo | Humanidades | Por asignatura | Activo |
| DEMO-DOC-008 | Diego Tavárez Demo | Idiomas | Suplente | Activo |
| DEMO-DOC-009 | Renata Cabrera Demo | Ciencias Empresariales | Tiempo completo | Activo |
| DEMO-DOC-010 | Leonardo Santana Demo | Ciencias Básicas | Tiempo parcial | Activo |
| DEMO-DOC-011 | Elena Peralta Demo | Tecnología | Por asignatura | Inactivo |
| DEMO-DOC-012 | Tomás Feliz Demo | Educación | Suplente | Inactivo |

**Datos calculados:** el identificador numérico se genera al guardar. Las secciones asignadas, estudiantes atendidos y horas programadas se calculan desde las secciones y horarios, no se escriben en la ficha. Estos nuevos docentes no tienen carga académica ni usuarios de acceso; esto evita modificar la operación ya registrada.

## Repetir la carga de forma segura

Desde la raíz del proyecto, previsualiza con `.venv\Scripts\python.exe -B -m scripts.seed_teacher_examples --database school.db`. Agrega `--apply` para insertar: crea un respaldo en `backups/`, valida todos los campos y conserva los registros anteriores. La carga es idempotente: volver a ejecutarla no duplica los ejemplos ni sobrescribe sus ediciones posteriores.

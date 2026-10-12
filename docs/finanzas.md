# Finanzas y pagos internos en República Dominicana

## Alcance

Moneda: DOP (RD$). Se registran efectivo recibido y transferencias bancarias verificadas manualmente. No hay cobros con tarjeta, pasarela activada ni conexión bancaria. El simulador no mueve dinero y nunca crea pagos, recibos ni descuentos de deuda.

Los recibos PDF son internos: **no son comprobantes fiscales, NCF ni e-CF**. Los bloqueos financieros del estudiante son controles separados; el balance no los activa ni levanta automáticamente.

## Configuración de transferencias

En el archivo local `.env`, configurar `FINANCE_TRANSFER_INSTRUCTIONS` con instrucciones bancarias autorizadas de la institución (banco, titular, cuenta, moneda y referencia). No se inventa una cuenta ni se solicita información de tarjetas. Si está vacío, se permite consultar solicitudes anteriores, pero no reportar transferencias nuevas.

`FINANCE_SIMULATOR_ENABLED=true` permite el simulador a los usuarios con gestión financiera (la interfaz actual lo muestra al administrador). Usar `false` para ocultarlo/deshabilitarlo. Reiniciar el backend tras cambiar estas variables.

## Probar como administrador

1. Abrir Finanzas. Buscar matrícula/nombre o filtrar cuentas con deuda, vencidas o sin deuda. Se incluyen cuentas de estudiantes inactivos para no ocultar obligaciones.
2. Abrir una cuenta. En Registrar cargo, efectivo o ajuste, crear un cargo. La fecha puede ser explícita o, al dejarla vacía, usar el próximo día de vencimiento configurado, adaptado al último día del mes.
3. Registrar efectivo **solo cuando se haya recibido**. Se exige referencia; el balance se valida en el servidor, con bloqueo transaccional. Reintentar la misma clave devuelve el resultado existente; cambiar los datos con esa clave o duplicar una referencia se rechaza.
4. Registrar beca/descuento/crédito (reduce deuda) o mora/débito (aumenta deuda). Todos aparecen en el historial. Los débitos tienen vencimiento; si se omite, es el día local actual.
5. En Transferencias, descargar el comprobante, verificar personalmente el ingreso en el banco y aprobar con motivo, o rechazarlo. La aprobación produce un único pago y recibo. Un segundo intento no vuelve a abonar.
6. En Cuotas y planes, crear hasta 24 cuotas mensuales. Los centavos se reparten sin perder dinero y las fechas se adaptan a febrero, manteniendo el día original para marzo. Solo se admite un plan activo.
7. Consultar los estados de cuotas, incluida cobertura parcial. Los abonos y créditos posteriores a crear el plan cubren las cuotas en orden. El plan es un compromiso informativo: **no añade deuda ni reemplaza los vencimientos originales de los cargos**. Nuevos cargos no amplían automáticamente el plan; cancelarlo y crear otro permite reprogramar.
8. Reversar un movimiento con motivo, sin eliminarlo. Si existe un plan activo, cancelarlo primero. No se admiten reversos que generen saldo a favor. Un reverso no devuelve dinero bancariamente.
9. En Caja y catálogo de conceptos, crear plantillas (frecuencia informativa, sin facturación automática) y cerrar una fecha. El cierre conserva total, cantidad y desglose entre efectivo, transferencias y registros anteriores sin método conocido.
10. El cierre bloquea pagos/aprobaciones del día y reversos de pagos pertenecientes a días cerrados. No se reabre ni se modifica el cierre; las correcciones posteriores requieren un ajuste documentado, sin simular una devolución de efectivo.
11. Consultar Auditoría: autor, fecha y detalle de las operaciones nuevas. No se inventan autores para registros antiguos.

## Probar como estudiante

- Consultar balance, vencimientos y todos los movimientos, incluidas becas, ajustes y reversos.
- Reportar una transferencia con referencia, banco, monto y comprobante privado PDF/PNG/JPEG de máximo 2 MB. Un comprobante pendiente no reduce el balance.
- Ver estado y motivo de aprobación/rechazo; descargar recibo cuando exista pago confirmado.
- Consultar cuotas; no puede registrar efectivo, aprobar transferencias, reversar movimientos ni ejecutar simulaciones.

## Cálculo y conservación

Los nuevos importes aceptan solo montos positivos, finitos y de hasta dos decimales. Los cálculos usan centavos enteros; las columnas monetarias heredadas se conservan como Float por compatibilidad, sin reescribir valores anteriores. No es una migración completa a columnas Decimal/Numeric.

Balance = cargos vigentes + débitos vigentes − créditos vigentes − pagos vigentes. Los movimientos reversados se conservan visibles pero no afectan los totales. Para calcular deuda vencida, se aplican pagos/créditos a obligaciones por vencimiento más antiguo primero. El día de corte sigue siendo informativo; no genera cargos ni mora automáticamente.

Los planes cancelados nuevos congelan su cobertura al cancelarse; pagos futuros no alteran sus compromisos históricos. Los estados de cuotas nuevas se calculan desde el libro financiero, no desde una casilla editable. Planes heredados conservan sus marcas de pago iniciales.

Las fechas de caja se calculan en UTC−04:00 (República Dominicana); los sellos de tiempo se almacenan en UTC. El comprobante se guarda en la base de datos y se sirve como descarga privada con comprobación de propietario. No se incluye en respuestas del listado ni se publica en Git.

## Instalación en otra PC

Respaldar SQLite con `python -B -m scripts.backup_database`, ejecutar `python -B -m alembic upgrade head` y reiniciar backend/frontend. La migración 20261012_0031 conserva registros y añade controles, solicitudes y auditoría. No admite downgrade destructivo automático: una restauración debe ser controlada desde respaldo.

No subir `.env`, `school.db`, respaldos ni comprobantes. Que Git ignore la base no deja de versionar copias antiguas que ya estaban rastreadas; este trabajo no elimina esos archivos ni reescribe el historial remoto.

## Futuro pago con tarjeta

La interfaz no muestra un checkout bancario ficticio. La futura pasarela deberá usar un adaptador independiente y confirmación autenticada del proveedor, validar importe/moneda/orden y evitar duplicados antes de llamar al flujo común de registro del pago. No aprobar a partir del retorno del navegador. Requiere afiliación, credenciales de pruebas y certificación del proveedor antes de habilitar producción.

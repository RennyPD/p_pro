# Pagos en línea de las familias (Fase 4, bloque E)

Las familias y los estudiantes pagan con tarjeta desde su estado de cuenta en Nexo («Pagar con tarjeta»).

## Principios

- **El dinero va directo a la institución.** Cada institución usa su propia cuenta de comercio con Azul o CardNet. Nexo no recibe, retiene ni transfiere dinero.
- **La tarjeta nunca toca Nexo.** La persona escribe los datos en la página segura del banco. Nexo solo recibe la respuesta firmada (cumplimiento PCI nivel SAQ-A).
- **El servidor decide el monto.** Cada parte va a un estudiante y no puede superar su balance pendiente. El total debe alcanzar el mínimo de la institución. Una respuesta del banco con otro monto se rechaza.
- **Cada respuesta se aplica una vez.** Si el banco repite la redirección o la persona recarga la página, no se registra nada dos veces.
- **Lo cobrado se registra siempre.** Un pago aprobado se registra aunque la caja del día ya esté cerrada. Si en el intervalo el saldo cambió (por ejemplo, también pagaron en caja), el pago queda marcado «Saldo a favor por resolver».

## Quién puede pagar

| Cuenta | Puede pagar |
|---|---|
| Tutor | Las cuentas de sus estudiantes vinculados con acceso a finanzas; en la vista familiar, repartiendo un solo pago entre varios hijos |
| Estudiante | Su propia cuenta, si la institución le deja ver sus finanzas |
| Personal | Nadie. El personal usa la caja |

## Configurar la pasarela (Finanzas › Pagos en línea)

Requiere el permiso «Gestionar finanzas».

1. **Prueba (sin cobro real):** para conocer el flujo en desarrollo o en demostraciones. En producción no está disponible.
2. **Azul (Página de Pagos):**
   - Datos: número de comercio (MerchantId), nombre del comercio y la **AuthKey** que entrega Azul.
   - Ambiente: «Pruebas del banco» (`pruebas.azul.com.do`) o «Producción» (`pagos.azul.com.do`).
   - La solicitud y la respuesta se firman con HMAC-SHA512.
3. **CardNet (botón de pago):**
   - Datos: número de comercio, **terminal** y, opcionalmente, el tipo de comercio.
   - Nexo abre la sesión de pago y lee el resultado directamente del banco.

Las claves se guardan cifradas con `PAYMENTS_ENCRYPTION_KEY` (variable del servidor). No se vuelven a mostrar: la pantalla enseña solo los últimos 4 caracteres, y guardar sin escribirlas conserva las anteriores. Cada cambio queda en la auditoría, sin las claves.

### Certificación con el banco

Azul y CardNet certifican la integración de cada comercio antes de pasar a producción:

1. La institución solicita al banco su comercio de comercio electrónico y las credenciales del **ambiente de pruebas**.
2. Las configura en Nexo con el ambiente «Pruebas del banco» y hace los pagos de prueba que pida el banco (aprobado, rechazado, cancelado).
3. Con la aprobación del banco, cambia a «Producción» y escribe las credenciales de producción.

Los adaptadores siguen las guías publicadas por cada banco y están probados con firmas y respuestas simuladas. Si el banco pide un ajuste durante la certificación (por ejemplo, un campo adicional), se hace en `app/services/payments/gateways.py`.

## Conciliación

En **Finanzas › Pagos en línea** aparece cada pago con:

- estudiantes y montos, y quién pagó;
- estado: creado, en el banco, aprobado, rechazado, sin respuesta o error;
- código de autorización, referencia y número de orden del banco;
- recibos emitidos.

El reporte diario (`/online-payments/report/daily`) suma lo aprobado por día para cuadrarlo con la liquidación del banco.

**Pagos sin respuesta.** Si la persona cierra el navegador antes de volver del banco:

1. Cada 10 minutos, el proceso de tareas programadas consulta al banco los pagos vencidos (más de una hora). Con CardNet el resultado llega solo; con Azul, el pago queda «Sin respuesta».
2. Una persona con «Supervisar finanzas» busca el número de orden en el portal del banco y usa **Resolver**: aprobado (con el código de autorización) o no aprobado, siempre con un motivo.
3. Si el banco responde tarde, la respuesta se aplica igual, porque la firma sigue siendo válida.

## Devoluciones

Por ahora:

1. Se devuelve el dinero en el portal del banco.
2. Se revierte el pago en Nexo con la reversión de siempre, que exige supervisor y motivo.

La devolución automática por la API del banco puede llegar después.

# Comprobantes fiscales (Fase 4, bloque F)

Cada institución emite sus comprobantes con **su propio RNC** y las **secuencias que le autorizó la DGII**. Nexo no emite en nombre de nadie.

> Esta guía describe cómo funciona Nexo; no es asesoría fiscal. La Ley 32-23 hace obligatorio el comprobante electrónico (e-CF) de forma escalonada: confirma con tu contador o con la DGII qué modalidad te corresponde. Revisa con tu contador el primer 607 antes de enviarlo.

## Configuración (Finanzas › Comprobantes fiscales)

1. **Emisor:**
   - RNC (Nexo valida el dígito verificador), razón social, nombre comercial y dirección fiscal.
   - Tipo de comprobante: **NCF** (B01, B02…) o **e-CF** (E31, E32…).
   - Cuándo se emite: **al registrar cada pago** (recomendado) o **solo a solicitud**.
2. **Secuencias:** registra cada rango autorizado: tipo, desde, hasta y fecha de vencimiento.
   - Nexo no permite rangos que se crucen y usa los números en orden, una sola vez.
   - Avisa cuando queda menos del 10 % de un rango, faltan 30 días para que venza, venció o se agotó.
3. **ITBIS por concepto de cobro:** exento por defecto (los servicios educativos lo están), o 16 % o 18 % para conceptos gravados como uniformes, transporte o cafetería.
   - El monto del cargo **incluye** el ITBIS; el comprobante lo desglosa.
   - Los cargos de un plan de cobro toman la tasa de su concepto.

## Qué tipo se emite

| Situación | NCF | e-CF |
|---|---|---|
| Consumidor final (sin RNC en la cuenta) | B02 | E32 |
| La cuenta tiene RNC o cédula para crédito fiscal | B01 | E31 |
| Reverso de un pago con comprobante | B04 (nota de crédito) | E34 |

**«Facturar a»** (por cuenta de estudiante, con el permiso de caja) guarda el nombre y el RNC o la cédula del responsable financiero. Nexo valida el dígito verificador de ambos.

## Emisión

- **Líneas:** son los cargos que salda el pago, del más antiguo al más reciente, con su ITBIS. Si el pago supera los cargos, el resto es «Abono a cuenta».
- **Sin secuencia vigente,** el pago **se registra igual** y el comprobante queda pendiente; nunca se detiene la caja. Al registrar una secuencia nueva, se emite desde «Emitir comprobante» (`POST /fiscal/payments/{id}/issue`). Cada pago tiene un solo comprobante.
- **PDF fiscal:** emisor, tipo, NCF, vencimiento de la secuencia (NCF), cliente, líneas, subtotal, ITBIS y total. Las familias lo descargan junto a cada pago en su estado de cuenta.

## Notas de crédito y anulaciones

- **Revertir un pago** que tiene comprobante emite una **nota de crédito** que modifica ese NCF. El comprobante original nunca se borra.
- **Anular** sirve solo para comprobantes emitidos por error. Se elige un motivo de la DGII (01 a 10) y el comprobante sale en el 608. Uno que tiene nota de crédito no se puede anular.

## Reportes 607 y 608

En «Reportes para la DGII» se elige el mes y se descargan los archivos de texto:

- **607:** comprobantes emitidos del mes, con los 23 campos del formato. Las formas de pago se asignan así:
  - efectivo;
  - cheque o transferencia;
  - tarjeta (incluye los pagos en línea).
- **608:** comprobantes anulados, con su motivo.

Pásalos por la herramienta de validación de la DGII antes de subirlos a la Oficina Virtual.

## Comprobante electrónico (e-CF)

En modo e-CF, Nexo envía cada comprobante a un **proveedor autorizado**. El proveedor lo firma en XML con el certificado digital y lo remite a la DGII. Nexo guarda la respuesta:

- estado (aceptado, en proceso o rechazado);
- TrackId;
- código de seguridad;
- fecha de firma;
- enlace de consulta de la DGII, que va como **código QR** en el PDF.

Si el proveedor no responde, el pago se registra igual y el comprobante queda «en proceso de validación». El proceso de tareas programadas lo reenvía cada 10 minutos.

Hoy está el **proveedor de prueba**, que nunca funciona en producción. Para conectar un proveedor real se añade su adaptador en `app/services/fiscal/ecf.py` cuando las instituciones lo elijan. Sus credenciales se guardan cifradas, como las de las pasarelas de pago.

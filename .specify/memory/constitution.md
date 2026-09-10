# Notificaciones Constitution

## Contexto del sistema

Este repositorio (`Notificaciones`) es **uno de varios repos** que componen RecoMe, un
sistema de recomendaciones de videojuegos y series. Otro repo actúa como **puerta de
entrada única** del sistema (ej. `api-general`) y es el dueño de la documentación de
contratos compartidos (schemas de eventos, specs OpenAPI). Este repo no conoce ni
implementa lógica de recomendación, catálogo, usuarios, reportes, ni ningún otro dominio
de negocio: es un componente de infraestructura + ejecución, deliberadamente acotado.

## Core Principles

### I. Responsabilidad acotada del repo (NON-NEGOTIABLE)

Este repo es dueño exclusivamente de dos cosas:

1. La infraestructura de un broker de mensajes (RabbitMQ): deploy y definición de
   exchanges/colas para eventos de notificación.
2. Un worker/notificador (Python + pika) que consume esos mensajes y, según lo que el
   mensaje indique, dispara notificaciones push a la web y/o notificaciones por mail.

El worker es deliberadamente **"tonto"**: no decide *si* ni *cuándo* notificar — esa
decisión ya viene tomada por otro componente del sistema en el mensaje que consume. Este
repo NO implementa, y no debe crecer para incluir:

- Generación de reportes exportables (PDF/Excel) ni nada relacionado a esa capacidad.
- Programación/scheduling de notificaciones automáticas o lógica de "cuándo" notificar.
- Almacenamiento de archivos: no hay módulo de object storage (MinIO) ni webserver de
  archivos en este repo.
- Lógica de negocio de recomendación, catálogo, usuarios, ni autenticación de usuarios
  finales — eso pertenece a otros repos del sistema (ej. `api-general`, motor de
  recomendación).

Cualquier propuesta que amplíe el alcance a alguno de estos dominios se considera **fuera
de constitution** y requiere una nueva discusión explícita de alcance antes de aceptarse,
no una simple implementación incremental.

### II. Cero acceso directo a bases de datos ajenas (NON-NEGOTIABLE)

El worker no lee ni escribe directamente sobre ninguna base de datos de otros repos del
sistema, bajo ninguna circunstancia, incluso si parece más simple o performante hacerlo.
Toda la información que el worker necesita para notificar debe llegarle de una de estas
dos formas:

- En el payload del mensaje de RabbitMQ que consume (preferido, ya que mantiene al worker
  simple y desacoplado), o
- Vía llamada REST contra el repo dueño de ese dato (solo si el dato no puede/debe viajar
  en el payload del evento).

Este repo tampoco expone ninguna base de datos propia para que otros repos accedan
directamente: no hay una DB de dominio propia más allá del estado operativo estrictamente
necesario para el worker (ej. colas, dead-letter, reintentos).

### III. Contratos de eventos como fuente externa de verdad

Este repo hostea la infraestructura del broker, pero **no es dueño unilateral** del
schema/contrato de ningún evento de RabbitMQ que consume, ni de ningún endpoint REST que
llegue a exponer. Esos contratos viven documentados en el repo "puerta de entrada" del
sistema (ej. `api-general`). Ningún cambio a un contrato compartido se implementa acá sin
antes actualizar esa documentación externa y avisar a los repos consumidores/publicadores
correspondientes. Un cambio de contrato de evento **nunca** se considera "interno" a este
repo, aunque el cambio de código quede contenido acá.

### IV. Validación estricta de payloads

El worker valida cada mensaje recibido contra el schema documentado (ver Principio III)
antes de procesarlo. Mensajes inválidos se rechazan o se envían a dead-letter; el worker
**nunca** "adivina" o rellena con valores por defecto un campo faltante o mal tipado en el
payload. Esto aplica tanto a los campos de negocio (a quién notificar, qué canal, qué
contenido) como a metadatos de control (identificadores de evento, timestamps, etc.).

### V. No accesible directamente por frontends (NON-NEGOTIABLE)

Solo el repo "puerta de entrada" del sistema puede disparar mensajes hacia el broker de
este repo. No existe acceso directo desde ningún frontend (usuario o vendedor/admin) hacia
este repo, ni hacia el broker ni hacia ningún endpoint REST que este repo llegue a
exponer. Si este repo expone un endpoint REST (p. ej. para solicitud de envío o consulta
de estado), ese endpoint se autentica servicio-a-servicio y solo es invocado por el repo
puerta de entrada, nunca directamente por un cliente final.

### VI. Test-First e Integration/Contract Testing (NON-NEGOTIABLE)

TDD obligatorio para la lógica propia del worker (armado y envío de notificaciones,
enrutamiento por canal, manejo de reintentos/dead-letter): tests escritos → aprobados →
fallando → luego implementación. Además, son obligatorios:

- **Contract tests** contra el schema de eventos documentado externamente (ver Principio
  III), ejecutados en CI antes de cualquier deploy, para detectar rupturas de
  compatibilidad tempranamente.
- **Pruebas de integración** contra RabbitMQ (colas/exchanges reales o equivalentes de
  test), cubriendo el flujo completo: mensaje recibido → validado → notificación
  disparada (push y/o mail, con proveedores reales o mockeados según corresponda).
- Ningún PR que modifique el consumo de un evento o el envío por un canal se mergea sin
  que sus contract tests e integration tests pasen.

#### Rigor de TDD por tipo de tarea

No toda tarea de implementación exige el mismo nivel de rigor TDD. Toda feature de este
repo DEBE clasificar sus tareas de implementación en uno de estos tres niveles antes de
comenzar a codear (documentado explícitamente en el `tasks.md` de la feature):

- **🟢 TDD estricto**: lógica pura/determinística, fácil de aislar sin mocks de
  infraestructura pesada (ej. validación de payload contra schema, selección de
  canal(es) según el mensaje, lógica de reintentos/backoff). Exige ciclo
  red-green-refactor completo: test unitario específico → falla → implementación mínima →
  refactor.
- **🟡 Test-first de integración**: lógica que envuelve un SDK/proveedor externo (cliente
  de push, cliente de mail). Se define primero la interfaz/contrato (mock-first) con su
  test, pero el detalle fino se valida con un test de integración en lugar de exigir TDD
  unitario puro sobre cada línea.
- **🔴 Test-first de contrato/orquestación**: el consumer de RabbitMQ que coordina
  servicios ya testeados por separado (wiring). Se escribe primero el contract test y/o
  integration test correspondiente, pero no se exige TDD unitario línea a línea sobre la
  orquestación en sí.

En los tres niveles el test se escribe **antes** que el código de implementación — lo que
cambia es la granularidad exigida, nunca si se hace test-first o no. Esta clasificación
debe mantenerse y aplicarse consistentemente en todas las features futuras de este repo,
no solo en la primera donde se definió.

### VII. Simplicidad (NON-NEGOTIABLE frente a los principios I–V)

Se prefiere siempre la solución más simple que no rompa el aislamiento de datos ni los
contratos compartidos. "Por simplicidad" **nunca** es justificación válida para: acceder
directamente a datos ajenos (Principio II), asumir unilateralmente un contrato de evento
(Principio III), adivinar campos de payload (Principio IV), exponer el repo directamente
a un frontend (Principio V), o ampliar el alcance descrito en el Principio I. Fuera de
esos límites, se evita deliberadamente sobre-diseñar: no agregar un framework REST si no
hay necesidad concreta de un endpoint; no agregar colas/exchanges adicionales sin un tipo
de evento real que los requiera.

## Decisión de diseño pendiente: mecanismo de plantillas

El formato y contenido de las plantillas de notificación (push y mail) **todavía no está
definido** y se deja explícitamente abierto como decisión de diseño pendiente, a resolver
en una spec o ADR posterior. En particular, quedan sin resolver:

- Si las plantillas viven en este repo o en otro (ej. gestionadas por el repo puerta de
  entrada y resueltas antes de publicar el evento).
- Si el mensaje que consume el worker llega con el contenido ya completo y listo para
  enviar, o si el worker debe resolver una plantilla contra algún identificador recibido.
- Si existe algún servicio externo de resolución de plantillas involucrado.

Ninguna spec ni implementación de este repo debe asumir una respuesta concreta a estas
preguntas hasta que se resuelvan explícitamente. Cualquier feature que dependa del
contenido de la notificación debe tratar el mecanismo de plantillas como una interfaz a
definir, no como un detalle ya decidido.

## Stack tecnológico

- **Broker**: RabbitMQ, un exchange/cola por tipo de evento de notificación. Deploy y
  definición base de exchanges/colas son responsabilidad de este repo.
- **Notificador**: Python + pika como consumidor de eventos.
- **Endpoint REST (opcional, evaluar antes de agregar)**: un framework REST liviano (ej.
  FastAPI) **solo si** se necesita exponer un endpoint de solicitud de envío o de
  consulta de estado. No se agrega este componente de forma especulativa: su necesidad
  debe justificarse en la spec de la feature correspondiente.
- Cambios de stack (ej. cambiar de `pika`, o el broker mismo) requieren justificación
  técnica documentada y coordinación con los equipos de los demás repos del sistema, dado
  que pueden afectar contratos o disponibilidad compartida.

## Reglas cross-repo heredadas (recordatorio vinculante)

1. Ningún repo accede directo a la base de datos de otro repo del sistema, en ninguna
   dirección.
2. El repo "puerta de entrada" del sistema es el único que puede disparar mensajes hacia
   el broker de este repo; ningún frontend accede directamente.
3. Comunicación asíncrona vía RabbitMQ, un exchange/cola por tipo de evento; contratos
   vivos documentados en el repo puerta de entrada del sistema.
4. Si este repo expone algo síncrono (REST), es con contratos versionados y
   autenticación servicio-a-servicio, nunca accesible directamente por un frontend.
5. Autenticación servicio-a-servicio con credencial/API key interna por entorno para toda
   llamada REST interna, entrante o saliente.
6. Eventos y convenciones nuevos que afecten a otros repos se definen primero en la
   documentación de contratos del repo puerta de entrada, antes de implementarse acá.

## Development Workflow

- Todo PR que toque el consumo de un evento o el envío por un canal debe enlazar la
  sección correspondiente de la documentación de contratos externa y confirmar que sigue
  vigente (o incluir el PR de actualización de esa documentación como prerequisito).
- Se requiere revisión de al menos un miembro del equipo de este repo antes de mergear
  cambios a exchanges/colas de RabbitMQ, dado que afectan a los demás repos
  consumidores/publicadores.
- CI debe correr: tests unitarios, contract tests contra el schema de eventos documentado
  externamente, y pruebas de integración contra RabbitMQ, antes de permitir merge a la
  rama principal.
- Toda spec de feature debe declarar explícitamente, antes de planificar tareas, si
  depende de una decisión de plantillas aún no resuelta (ver sección correspondiente) y,
  en ese caso, tratarla como researcheable/pendiente en vez de asumir un mecanismo.

## Governance

Esta constitution prevalece sobre cualquier práctica o atajo ad-hoc dentro de este repo.
Toda enmienda debe documentarse explícitamente, indicar impacto sobre los demás repos del
sistema si lo hubiera, y ser coordinada con sus equipos cuando afecte contratos
compartidos. Ningún PR se aprueba si introduce una violación a los principios I–V (ampliar
el alcance del repo, acceso directo a datos ajenos, redefinición unilateral de un
contrato de evento, adivinar campos de payload, o exposición directa a un frontend). La
complejidad adicional debe justificarse por escrito en el PR correspondiente.

**Version**: 2.0.0 | **Ratified**: 2026-09-10 | **Last Amended**: 2026-09-10

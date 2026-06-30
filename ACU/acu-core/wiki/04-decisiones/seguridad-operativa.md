# Seguridad Operativa

**Fecha de actualizacion**: 2026-05-18  
**Estado**: baseline operativo definido  
**Alcance**: roles, secretos, limites, auditoria y exposicion de endpoints.

## Objetivo

Este runbook fija el contrato minimo para operar ACU en entornos expuestos. El modo local se mantiene abierto para desarrollo, pero produccion debe activar autenticacion, limites de abuso, secretos de webhooks y auditoria persistente.

## Baseline De Produccion

Variables recomendadas:

```env
ACU_API_AUTH_REQUIRED=True
ACU_API_KEYS=chat-client=chat;ops-monitor=monitoring;brain-reader=braincore_read;brain-writer=braincore_write
ACU_API_RATE_LIMIT_REQUESTS=120
ACU_API_RATE_LIMIT_WINDOW_SECONDS=60
ACU_API_MAX_REQUEST_BODY_BYTES=1048576
ACU_API_CORS_ORIGINS=https://panel.example.com
ACU_ALLOW_OPERATIONAL_PUBLIC_ROUTES=False
ACU_TELEGRAM_WEBHOOK_SECRET=<secret>
ACU_SLACK_SIGNING_SECRET=<secret>
ACU_SLACK_MAX_SKEW_SECONDS=300
ACU_WEBHOOK_ALLOWED_TELEGRAM_CHATS=<chat_id_1>,<chat_id_2>
ACU_WEBHOOK_ALLOWED_SLACK_USERS=<user_id_1>,<user_id_2>
```

En produccion no se recomienda usar una sola clave `admin` para clientes normales. Crear claves separadas por rol reduce blast radius y deja auditoria mas util.

## Superficies Publicas

Estas rutas permanecen publicas por contrato de aplicacion:

| Ruta | Motivo | Riesgo operativo |
|------|--------|------------------|
| `GET /` y `HEAD /` | Root minimo para platform checks | No debe exponer datos sensibles |
| `GET /health` | Healthcheck Docker, balanceadores y smoke tests | No debe exponer datos sensibles |
| `GET /system/readiness` | Readiness sanitizado para smoke y SRE | No debe exponer datos internos |

Estas rutas operativas requieren API key cuando la autenticacion esta activa:

| Ruta | Uso | Control |
|------|-----|---------|
| `GET /api/version` | Versionado funcional y compatibilidad de clientes | API key o opt-in local explicito |
| `GET /dashboard` | Consola embebida estatica | API key o opt-in local explicito |
| `GET /docs` | OpenAPI interactivo | API key o opt-in local explicito |
| `GET /openapi.json` | Contrato API | API key o opt-in local explicito |
| `GET /redoc` | Documentacion API | API key o opt-in local explicito |
| `GET /static/*` | Assets del dashboard | API key o opt-in local explicito |

`ACU_ALLOW_OPERATIONAL_PUBLIC_ROUTES=True` solo debe usarse en desarrollo local controlado. No habilitarlo en staging o produccion.

## Matriz De Roles

| Rol | Endpoints principales | Uso esperado |
|-----|-----------------------|--------------|
| `admin` | `/api/keys`, `/tools/pending`, acciones HITL, fallback de rutas no clasificadas | Operacion privilegiada y aprobaciones |
| `chat` | `POST /chat` | Clientes conversacionales |
| `braincore_read` | `POST /braincore/search`, `GET /braincore/sources`, `GET /braincore/metrics`, `GET /braincore/decisions`, `GET /braincore/domains/{domain}/export` | Lectura de memoria |
| `braincore_write` | `POST /braincore/ingest`, `POST /braincore/decisions`, `DELETE /braincore/sources/{source_id}`, `DELETE /braincore/domains/{domain}` | Curadoria de memoria |
| `monitoring` | `GET /system/readiness`, `GET /system/metrics`, `GET /sessions`, `GET /sessions/{id}/context`, `GET /tools/executions`, `GET /api/access-log` | Observabilidad y soporte |

`admin` hereda todos los permisos. `braincore_write` tambien puede cubrir lecturas BrainCore cuando el endpoint requiere `braincore_read`.

## HITL Y Herramientas Sensibles

La cola Human-in-the-Loop queda reservada para `admin`:

- `GET /tools/pending`
- `POST /tools/pending/{tool_id}/approve`
- `POST /tools/pending/{tool_id}/reject`
- `POST /tools/pending/{tool_id}/resume`

Estas rutas pueden ejecutar, rechazar o reanudar acciones sensibles. No deben compartirse con claves `monitoring` ni `chat`.

## Webhooks Externos

Los webhooks deben validarse por canal:

| Canal | Control minimo |
|-------|----------------|
| Telegram | `ACU_TELEGRAM_WEBHOOK_SECRET` y `ACU_WEBHOOK_ALLOWED_TELEGRAM_CHATS` |
| Slack | `ACU_SLACK_SIGNING_SECRET`, `ACU_SLACK_MAX_SKEW_SECONDS` y `ACU_WEBHOOK_ALLOWED_SLACK_USERS` |

Con `ACU_API_AUTH_REQUIRED=True`, las rutas no publicas tambien pasan por middleware de API key. Si se conecta Slack/Telegram real detras de la API, usar un proxy/gateway que agregue `X-ACU-API-Key` o exponer una ruta controlada por red y secretos del proveedor. No dejar webhooks abiertos sin secreto.

## Auditoria

`GET /api/access-log` permite revisar:

- Accesos autorizados y rechazados.
- Fingerprint de clave, no la clave en claro.
- Roles asociados.
- Ruta, metodo, status code y duracion.

Las claves gestionadas por BD se guardan hasheadas y el secreto completo solo se devuelve al crearlas. Para incidentes, revocar la clave desde `POST /api/keys/{key_id}/revoke` y revisar accesos por fingerprint.

## Rate Limiting Y Payloads

Controles recomendados:

- `ACU_API_RATE_LIMIT_REQUESTS`: activar con un valor inicial conservador, por ejemplo `120`.
- `ACU_API_RATE_LIMIT_WINDOW_SECONDS`: mantener `60` salvo necesidad especifica.
- `ACU_API_MAX_REQUEST_BODY_BYTES`: definir limite para evitar payloads excesivos antes de inicializar providers.

El rate limit usa API key si esta presente; si no, usa identidad de cliente por red. En despliegues multi-replica conviene mover esta decision a Redis/proxy si se requiere consistencia global estricta.

## Readiness Runtime

`GET /system/readiness` entrega un checklist operativo para validar una instancia antes de exponerla.

Estados:

- `ready`: todos los controles pasan.
- `warning`: no hay fallos criticos, pero faltan controles recomendados como secretos webhook o Redis compartido.
- `not_ready`: existe al menos un fallo critico y la instancia no debe exponerse.

Checks criticos:

- `api_auth_required`
- `rate_limit_enabled`
- `payload_limit_enabled`
- `cors_restricted`
- `scheduler_mode`
- `api_contract`

Checks de advertencia:

- `webhook_telegram_secret`
- `webhook_slack_signing_secret`
- `redis_connected`

## Checklist De Release

Antes de exponer ACU:

- [ ] `GET /system/readiness` responde `ready` o las advertencias estan aceptadas por el responsable operativo.
- [ ] `ACU_API_AUTH_REQUIRED=True`.
- [ ] Claves separadas por rol en `ACU_API_KEYS` o claves gestionadas por BD.
- [ ] Sin uso operativo de una clave unica `admin`.
- [ ] `ACU_API_RATE_LIMIT_REQUESTS` configurado.
- [ ] `ACU_API_MAX_REQUEST_BODY_BYTES` configurado.
- [ ] CORS restringido a origenes conocidos.
- [ ] Webhooks con secretos y allowlists.
- [ ] `ACU_ALLOW_OPERATIONAL_PUBLIC_ROUTES=False` en staging/produccion.
- [ ] Dashboard/docs/OpenAPI protegidos por API key si la red es publica.
- [ ] Auditoria disponible en MySQL.
- [ ] Smoke test de `/health`, `scripts/readiness_gate.py` y prueba de acceso rechazado sin key.

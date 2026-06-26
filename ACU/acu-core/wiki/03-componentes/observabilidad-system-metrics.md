# Observabilidad - Contrato `/system/metrics`

**Fecha de actualizacion**: 2026-05-18  
**Estado**: Operativo  
**Endpoint**: `GET /system/metrics`  
**Rol requerido**: `monitoring` cuando la autenticacion API esta habilitada

## Proposito

`/system/metrics` entrega una fotografia ligera del estado operativo de ACU sin depender de Prometheus ni de infraestructura externa. El dashboard consume este contrato para mostrar salud runtime de seguridad, vector store, HITL, scheduler, Redis y webhooks.

## Request

Sin autenticacion local:

```bash
curl "http://localhost:8000/system/metrics"
```

Con API key:

```bash
curl -H "X-ACU-API-Key: acu_xxx" "http://localhost:8000/system/metrics"
```

## Response Ejemplo

```json
{
  "service": "ACU - Agente Cognitivo Universal",
  "version": "1.0.0",
  "vector_store": {
    "enabled": true,
    "available": true,
    "engine": "faiss",
    "persist_directory": "data/vectors",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "collection_name": "braincore_chunks",
    "index_path": "data/vectors/braincore_faiss.index",
    "metadata_path": "data/vectors/braincore_faiss_metadata.json",
    "index_exists": true,
    "metadata_exists": true,
    "records_count": 1200,
    "cached": false,
    "status": "ready",
    "error": null
  },
  "api_auth_required": true,
  "rate_limit_enabled": true,
  "payload_limit_enabled": true,
  "cors_enabled": true,
  "pending_tools": {
    "total": 4,
    "pending": 1,
    "approved": 0,
    "executed": 1,
    "failed": 0,
    "rejected": 1,
    "resumed": 1
  },
  "scheduler": {
    "mode": "worker",
    "valid_mode": true,
    "running": true,
    "jobs_count": 2,
    "jobs": ["prune_logs_job", "braincore_sync_job"]
  },
  "redis": {
    "enabled": true,
    "connected": true,
    "backend": "redis"
  },
  "webhooks": {
    "total": {
      "received": 25,
      "accepted": 22,
      "rejected": 2,
      "ignored": 1,
      "processed": 21,
      "failed": 1,
      "last_event_at": 1779129600.0,
      "last_error": "Invalid Slack signature"
    },
    "channels": {
      "telegram": {
        "received": 10,
        "accepted": 9,
        "rejected": 1,
        "ignored": 0,
        "processed": 9,
        "failed": 0,
        "last_event_at": 1779129500.0,
        "last_error": "Invalid Telegram webhook secret"
      },
      "slack": {
        "received": 15,
        "accepted": 13,
        "rejected": 1,
        "ignored": 1,
        "processed": 12,
        "failed": 1,
        "last_event_at": 1779129600.0,
        "last_error": "Invalid Slack signature"
      }
    }
  }
}
```

## Campos

| Campo | Tipo | Significado |
|-------|------|-------------|
| `service` | string | Nombre del servicio configurado |
| `version` | string | Version runtime de ACU |
| `vector_store` | object | Estado del backend vectorial BrainCore |
| `api_auth_required` | boolean | Indica si la API exige clave para endpoints privados |
| `rate_limit_enabled` | boolean | Indica si el rate limit esta activo |
| `payload_limit_enabled` | boolean | Indica si existe limite de tamano de payload |
| `cors_enabled` | boolean | Indica si CORS esta habilitado por allowlist |
| `pending_tools` | object | Contadores de herramientas HITL por estado |
| `scheduler` | object | Estado del scheduler en el proceso actual |
| `redis` | object | Estado de Redis o fallback local |
| `webhooks` | object | Contadores Slack/Telegram desde Redis cuando esta disponible; fallback local por proceso |

## Umbrales Operativos

| Senal | Verde | Advertencia | Critico | Accion recomendada |
|-------|-------|-------------|---------|--------------------|
| `vector_store.status` | `ready` o `disabled` esperado | `degraded` o `error` con fallback textual disponible | `enabled=true` y `available=false` sostenido | Revisar dependencias vectoriales, volumen `data/vectors` y logs de BrainCore |
| `pending_tools.pending` | `0-5` | `6-20` o pendientes de mas de 30 min | `>20` o bloqueo operacional | Revisar dashboard HITL, aprobar/rechazar, validar operadores |
| `pending_tools.failed` | `0` | `1-3` recientes | `>3` o repetidos por misma herramienta | Revisar parametros, permisos y conectividad de herramientas sensibles |
| `scheduler.valid_mode` | `true` | n/a | `false` | Corregir `ACU_SCHEDULER_MODE` |
| `scheduler.running` | `true` cuando `mode=api`, `worker` o `all` en el proceso esperado | `false` en entorno donde no debe correr | `false` en worker dedicado | Verificar contenedor `acu-scheduler`, logs y healthcheck |
| `scheduler.jobs_count` | `2` | `1` | `0` con scheduler habilitado | Revisar registro de jobs en `src/api/scheduler.py` |
| `redis.connected` | `true` si `ACU_REDIS_URL` esta configurado | `false` con fallback local aceptable en dev | `false` en prod multi-replica | Revisar servicio Redis, DNS interno y `ACU_REDIS_URL` |
| `webhooks.total.rejected` | Bajo y explicado | Ratio rechazado/recibido `>10%` | Ratio `>30%` o crecimiento brusco | Revisar secretos, firmas Slack, allowlists y replay window |
| `webhooks.total.failed` | `0` | `1-3` recientes | `>3` o errores repetidos | Revisar procesamiento del agente, logs y conectividad LLM |
| `api_auth_required` | `true` en prod | `false` solo dev/local | `false` en prod | Configurar `ACU_API_AUTH_REQUIRED=true` y API keys |
| `rate_limit_enabled` | `true` en prod | `false` en dev | `false` en endpoints expuestos publicamente | Configurar `ACU_API_RATE_LIMIT_REQUESTS` y ventana |

## Runbook Rapido

### Scheduler no corre

1. Consultar `/system/metrics` y validar `scheduler.mode`, `scheduler.running`, `jobs_count`.
2. Revisar variables:

```bash
ACU_SCHEDULER_MODE=worker
ACU_LOG_RETENTION_DAYS=30
ACU_AUDIT_RETENTION_DAYS=30
ACU_CONVERSATION_RETENTION_DAYS=30
ACU_BRAINCORE_SYNC_PATHS=
```

3. Revisar contenedor:

```bash
docker compose -f docker/docker-compose.yml ps acu-scheduler
docker compose -f docker/docker-compose.yml logs acu-scheduler
```

### Redis desconectado

1. Validar `redis.enabled`, `redis.connected`, `redis.backend`.
2. Revisar servicio:

```bash
docker compose -f docker/docker-compose.yml ps redis
docker compose -f docker/docker-compose.yml exec redis redis-cli ping
```

3. Confirmar `ACU_REDIS_URL=redis://redis:6379/0`.

### Cola HITL creciendo

1. Revisar `pending_tools.pending`.
2. Abrir `/dashboard` y operar la tabla Human-in-the-Loop.
3. Si hay fallos, revisar detalle `result/error` en la tabla HITL.
4. Revisar auditoria:

```bash
curl -H "X-ACU-API-Key: acu_xxx" "http://localhost:8000/tools/executions?limit=50"
```

### Webhooks rechazados

1. Revisar `webhooks.total.rejected` y `last_error`.
2. Telegram: validar `ACU_TELEGRAM_WEBHOOK_SECRET`.
3. Slack: validar `ACU_SLACK_SIGNING_SECRET` y `ACU_SLACK_MAX_SKEW_SECONDS`.
4. Revisar allowlists:

```bash
ACU_WEBHOOK_ALLOWED_TELEGRAM_CHATS=
ACU_WEBHOOK_ALLOWED_SLACK_USERS=
```

## Notas

- Las metricas de webhooks se consolidan en Redis cuando esta conectado; si Redis no esta disponible, el fallback local solo representa el proceso actual.
- `scheduler.running` reporta el estado del scheduler en el proceso que atiende la request. En produccion con worker dedicado, la API puede reportar `running=false` si `ACU_SCHEDULER_MODE=disabled` en `acu-agent`; el worker debe validarse por healthcheck/logs.
- `vector_store.status=disabled` puede ser correcto si el entorno no habilita busqueda vectorial.

# Readiness Operativa - Contrato `/system/readiness`

**Endpoint**: `GET /system/readiness`  
**Rol requerido**: `monitoring` cuando la autenticacion API esta habilitada  
**Estado**: implementado

## Objetivo

`/system/readiness` entrega un checklist runtime para decidir si una instancia ACU esta lista para exponerse fuera del entorno local. A diferencia de `/system/metrics`, este contrato no consulta BrainCore ni MySQL: debe responder aun cuando se esta diagnosticando el ambiente.

## Estados

| Estado | Significado | Accion |
|--------|-------------|--------|
| `ready` | Todos los checks pasan | Instancia apta para exposicion segun baseline actual |
| `warning` | No hay fallos criticos, pero hay controles opcionales incompletos | Revisar antes de produccion real |
| `not_ready` | Existe al menos un fallo critico | No exponer la instancia |

## Checks

| Check | Severidad | Criterio |
|-------|-----------|----------|
| `api_auth_required` | `critical` | `ACU_API_AUTH_REQUIRED=True` |
| `rate_limit_enabled` | `critical` | `ACU_API_RATE_LIMIT_REQUESTS > 0` |
| `payload_limit_enabled` | `critical` | `ACU_API_MAX_REQUEST_BODY_BYTES > 0` |
| `cors_restricted` | `critical` | CORS deshabilitado o restringido; nunca `*` |
| `webhook_telegram_secret` | `warning` | `ACU_TELEGRAM_WEBHOOK_SECRET` configurado |
| `webhook_slack_signing_secret` | `warning` | `ACU_SLACK_SIGNING_SECRET` configurado |
| `redis_connected` | `warning` | Redis conectado para agregados compartidos |
| `scheduler_mode` | `critical` | Modo en `disabled`, `api`, `worker` o `all` |
| `api_contract` | `critical` | Contrato API `v1` estable |

## Ejemplo

```bash
curl -H "X-ACU-API-Key: acu_monitor_key" \
  "http://localhost:8000/system/readiness"
```

Respuesta:

```json
{
  "service": "ACU - Agente Cognitivo Universal",
  "version": "1.0.0",
  "api_version": "v1",
  "status": "ready",
  "summary": {
    "passed": 9,
    "warnings": 0,
    "failed": 0
  },
  "checks": [
    {
      "name": "api_auth_required",
      "status": "pass",
      "severity": "critical",
      "detail": "Autenticacion API habilitada"
    }
  ]
}
```

## Uso Operativo

- Ejecutar despues de levantar la API y antes de publicar DNS, proxy o balanceador.
- Tratar `not_ready` como bloqueo de release.
- Tratar `warning` como aceptable solo en entornos internos o cuando el control no aplica.
- Usar `/system/metrics` para diagnostico detallado una vez que readiness confirme la postura minima.

## Gate CLI

El script `scripts/readiness_gate.py` ejecuta el contrato como gate reutilizable de despliegue.

```bash
python scripts/readiness_gate.py \
  --url http://localhost:8000/system/readiness \
  --api-key acu_monitor_key
```

Comportamiento:

- Exit code `0` con `ready`.
- Exit code `0` con `warning` por defecto, para permitir ambientes internos con advertencias aceptadas.
- Exit code `1` con `not_ready`.
- `--strict` convierte `warning` en fallo.

El workflow `.github/workflows/ci.yml` lo ejecuta despues del smoke test de `/health` sobre la imagen Docker recien construida.

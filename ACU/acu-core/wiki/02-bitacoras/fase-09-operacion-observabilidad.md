# Fase 09 - Operacion y Observabilidad

**Fecha de inicio**: 2026-05-18  
**Fecha de cierre operativo**: 2026-05-19  
**Estado**: Cerrada operativamente  
**Objetivo**: convertir el baseline estable en una superficie operable, medible y facil de supervisar.

## Resumen

Fase enfocada en visibilidad runtime, UX operativa del dashboard y trazabilidad de flujos criticos como HITL, scheduler, Redis y seguridad API.

El cierre formal queda aprobado en [Cierre Formal De Fase 9](../04-decisiones/cierre-fase-09.md). Prometheus/Grafana se difiere a [Fase 10 - Observabilidad Historica y Alertas](fase-10-observabilidad-historica.md).

## Cambios Implementados

### Metricas Operativas

- `GET /system/metrics` ahora reporta estado agregado de herramientas HITL.
- Se exponen contadores por estado: `pending`, `approved`, `executed`, `failed`, `rejected` y `resumed`.
- Se agrega estado runtime de Redis: `enabled`, `connected` y `backend`.
- Se agrega estado runtime del scheduler: modo configurado, validez, ejecucion, cantidad de jobs e IDs registrados.
- Se agregan metricas de webhooks por canal y total agregado.
- Webhooks reporta `received`, `accepted`, `rejected`, `ignored`, `processed`, `failed`, `last_event_at` y `last_error`.
- Las metricas webhook se escriben en Redis cuando esta disponible y `/system/metrics` prefiere ese agregado compartido.
- En ausencia de Redis se mantiene fallback local por proceso.

### Dashboard

- Se agregan tarjetas superiores para HITL y Scheduler.
- HITL muestra pendientes activos, total de registros, ejecuciones y reanudaciones.
- Scheduler muestra modo/estado, cantidad de jobs y backend Redis/local.
- Se agrega tarjeta Webhooks con eventos recibidos, aceptados y rechazados.
- La seccion HITL ahora muestra todos los estados vivos por TTL: `pending`, `approved`, `executed`, `failed`, `rejected` y `resumed`.
- La tabla HITL muestra resultado/error cuando la herramienta ya fue ejecutada.
- El chat recibe mensajes de sistema cuando una herramienta se rechaza o cuando la conversacion se reanuda.

### Contratos y Tipado

- Se agregan modelos Pydantic para metricas de HITL, scheduler, Redis y webhooks.
- Se agregan pruebas de contrato para `/system/metrics`.
- Se agregan pruebas de presencia de las nuevas tarjetas en el dashboard.
- Se agregan pruebas de contadores webhook para rechazos y aceptaciones.
- Se agregan pruebas estaticas para estilos y funciones HITL avanzadas del dashboard.
- Se documenta el contrato `/system/metrics` con request, response, campos, umbrales y runbook operativo.
- La superficie REST actual queda publicada como contrato `v1`.
- Se agrega `GET /api/version` con `runtime_version`, `api_version`, `stability` y `openapi_url`.
- Todas las respuestas publican headers `X-ACU-API-Version` y `X-ACU-API-Stability`.
- `/openapi.json` incluye metadata `x-acu-api-version`, `x-acu-api-stability` y politica de breaking changes.
- Se documenta el runbook [Versionado De API Y OpenAPI](../04-decisiones/versionado-api-openapi.md).
- Se agrega `GET /system/readiness` como checklist runtime para ambientes expuestos.
- Se agregan modelos Pydantic para readiness: checks, resumen y estado global.
- Se documenta el contrato [Readiness Operativa](../03-componentes/readiness-operativa.md).
- Se agrega `scripts/readiness_gate.py` como gate CLI reutilizable para despliegues.

### Docker y Healthchecks

- `docker/Dockerfile` ahora arranca FastAPI con `uvicorn src.api.app:app` por defecto.
- El healthcheck de la imagen ACU valida `GET /health` en `localhost:8000`.
- `docker-compose.yml` expone la API local en `8000:8000`.
- Compose local, compose prod y stack Swarm definen healthchecks para ACU API, scheduler, MySQL, Redis, Ollama y Jaeger.
- `acu-agent` depende tambien de Redis saludable en el compose local.
- Se agregan pruebas estaticas para fijar el contrato Docker.
- Se agrega `.dockerignore` para excluir caches, datos locales, logs, tests y wiki del contexto de build.
- Se corrige el perfil `requirements/observability.txt` con versiones OpenTelemetry fijadas y compatibles con `mysql-connector-python`.
- El workflow CI agrega job `docker-validation` con validacion de compose, build de imagen y smoke test de `/health`.
- El smoke test Docker ejecuta `scripts/readiness_gate.py` contra `/system/readiness` con una clave `monitoring` de validacion.
- El push a GHCR queda alineado a `ghcr.io/${github.repository}:latest` y `:${github.sha}`.
- El stack Swarm usa la misma imagen productiva `ghcr.io/revoxetech/acu-core:latest`.
- El workflow ahora publica tags semanticos al empujar `vX.Y.Z`: `X.Y.Z`, `X.Y`, `X` y `sha-<commit>`.
- Compose prod y stack aceptan `ACU_IMAGE` para fijar la imagen exacta de `acu-agent` y `acu-scheduler`.
- Se documenta el runbook [Versionado De Imagenes](../04-decisiones/versionado-imagenes.md).

### Seguridad Operativa

- Se documenta el runbook [Seguridad Operativa](../04-decisiones/seguridad-operativa.md).
- Se fija baseline recomendado para produccion: `ACU_API_AUTH_REQUIRED=True`, claves por rol, rate limiting, limite de payload y CORS restringido.
- Se explicita la matriz de roles para `admin`, `chat`, `braincore_read`, `braincore_write` y `monitoring`.
- Los endpoints HITL `/tools/pending` y `/tools/pending/{tool_id}/approve|reject|resume` quedan declarados explicitamente como superficie `admin`.
- Se documenta la interaccion operativa entre webhooks, secretos de proveedor, allowlists y API key.
- Se agrega checklist de release para no exponer dashboard, docs o webhooks sin una capa de proteccion adecuada.
- El checklist de release ahora referencia `/system/readiness` como gate runtime.
- El runbook de imagenes incorpora el gate de readiness despues de validar `/health`.

### Retencion Operativa

- Se agregan variables `ACU_AUDIT_RETENTION_DAYS` y `ACU_CONVERSATION_RETENTION_DAYS`.
- El scheduler poda `tool_execution_log` y `api_access_log` con retencion de auditoria.
- El scheduler poda `conversation_context` y sesiones finalizadas de `agent_sessions` con retencion conversacional.
- Las sesiones activas no se eliminan porque la poda exige `fin IS NOT NULL`.
- Compose local, prod y stack propagan las variables de retencion al servicio `acu-scheduler`.
- Se documenta el runbook [Retencion De Auditoria Y Contexto](../04-decisiones/retencion-auditoria-contexto.md).

### Gobierno BrainCore

- Se agrega `GET /braincore/domains/{domain}/export` para exportar decisiones, fuentes y chunks por dominio.
- Se agrega `DELETE /braincore/domains/{domain}` con confirmacion exacta `confirm={domain}`.
- La limpieza por dominio elimina fuentes y chunks, y limpia vector store por `source_path`.
- Las decisiones BrainCore se conservan por defecto y solo se eliminan con `delete_decisions=true`.
- Se documenta el runbook [Gobierno BrainCore Por Dominio](../04-decisiones/gobierno-braincore.md).

## Validacion

```bash
python -m ruff format --check src tests scripts main.py
python -m ruff check src tests scripts main.py
python -m mypy src scripts main.py --ignore-missing-imports
python -m pytest
```

Resultado vigente:

```text
157 passed, 4 skipped
```

## Pendientes

1. Iniciar Fase 10 si se decide implementar historicos y alertas con Prometheus/Grafana.

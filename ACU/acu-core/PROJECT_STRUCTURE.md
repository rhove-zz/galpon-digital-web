# Estructura del Proyecto - ACU

Este documento resume la estructura fisica vigente de `acu-core`.

## Arbol General

```text
acu-core/
|- main.py
|- setup.py
|- requirements.txt
|- requirements/
|  |- base.txt
|  |- dev.txt
|  |- vector.txt
|  |- vector-faiss.txt
|  |- observability.txt
|  `- all.txt
|- pytest.ini
|- mypy.ini
|- .dockerignore
|- .env.example
|- README.md
|- ARCHITECTURE.md
|- USAGE.md
|- PROJECT_STRUCTURE.md
|- DELIVERY.md
|- .github/
|  `- workflows/
|     |- ci.yml
|     `- tests.yml
|- docker/
|  |- Dockerfile
|  |- docker-compose.yml
|  |- docker-compose.prod.yml
|  |- docker-stack.yml
|  `- init.sql
|- scripts/
|  `- readiness_gate.py
|- src/
|- tests/
|- wiki/
`- data/
```

## Dependencias

| Archivo | Proposito |
|---------|-----------|
| `requirements/base.txt` | Runtime minimo API/CLI |
| `requirements/dev.txt` | Desarrollo, lint, tipos y tests |
| `requirements/vector.txt` | ChromaDB y embeddings |
| `requirements/vector-faiss.txt` | FAISS y vector completo |
| `requirements/observability.txt` | OpenTelemetry |
| `requirements/all.txt` | Union de todos los perfiles |
| `requirements.txt` | Compatibilidad; instala `requirements/all.txt` |

El perfil `requirements/observability.txt` mantiene OpenTelemetry fijado a versiones compatibles con `mysql-connector-python==8.2.0`.

## Codigo Fuente

```text
src/
|- __init__.py
|- agent/
|  |- __init__.py
|  |- agent_loop.py
|  `- prompting.py
|- api/
|  |- __init__.py
|  |- app.py
|  |- agent_runtime.py
|  |- dashboard.py
|  |- readiness.py
|  |- scheduler.py
|  |- security.py
|  |- schemas.py
|  |- telemetry.py
|  |- webhooks.py
|  |- routes/
|  |  |- __init__.py
|  |  |- api_keys.py
|  |  |- braincore.py
|  |  |- chat.py
|  |  |- monitoring.py
|  |  |- system.py
|  |  `- tools.py
|  |- static/
|  |  |- dashboard.css
|  |  `- dashboard.js
|  `- templates/
|     `- dashboard.html
|- braincore/
|  |- __init__.py
|  |- ingestion.py
|  |- manager.py
|  `- vector_store.py
|- config/
|  |- __init__.py
|  `- settings.py
|- llm/
|  |- __init__.py
|  `- ollama_client.py
|- memory/
|  |- __init__.py
|  |- mysql_manager.py
|  |- repositories/
|  |  |- __init__.py
|  |  |- audit.py
|  |  |- api_keys.py
|  |  |- brain_decisions.py
|  |  |- brain_domains.py
|  |  |- brain_metrics.py
|  |  |- brain_search.py
|  |  |- brain_sources.py
|  |  |- lessons.py
|  |  |- sessions.py
|  |  `- sql_runtime.py
|  `- redis_manager.py
|- security/
|  `- guardrails.py
|- tools/
|  |- __init__.py
|  `- tools_manager.py
`- utils/
   |- __init__.py
   |- logger.py
   `- schemas.py
```

## Responsabilidad por Modulo

| Modulo | Responsabilidad |
|--------|-----------------|
| `src/agent` | Loop ReAct, historial, HITL resume, prompts y ciclo de razonamiento |
| `src/api/app.py` | Ensamblaje FastAPI, middlewares, providers, OpenAPI y helpers transversales |
| `src/api/agent_runtime.py` | Inicializacion compartida del agente para rutas y HITL resume |
| `src/api/readiness.py` | Checklist runtime para exposicion operativa |
| `src/api/routes/api_keys.py` | Rutas de API keys gestionadas: create, list y revoke |
| `src/api/routes/braincore.py` | Rutas BrainCore para decisiones, fuentes, ingesta, busqueda, export y delete por dominio |
| `src/api/routes/chat.py` | Rutas `/chat` y `/chat/stream`, serializacion de tool calls |
| `src/api/routes/monitoring.py` | Rutas de monitoreo para sesiones, contexto conversacional y auditoria |
| `src/api/routes/system.py` | Rutas de health, version, dashboard, metricas y readiness |
| `src/api/routes/tools.py` | Rutas HITL para listar, aprobar, rechazar y reanudar herramientas pendientes |
| `src/api/security.py` | API keys, RBAC, fingerprints, expiracion y resolucion de identidad |
| `src/api/scheduler.py` | Worker de mantenimiento: poda de auditoria/contexto y sincronizacion BrainCore |
| `src/api/scheduler.py` | Jobs de mantenimiento con modo `api`/`worker` configurable |
| `src/api/telemetry.py` | OpenTelemetry opt-in |
| `src/api/webhooks.py` | Webhooks Slack/Telegram con secretos, firmas y allowlists |
| `src/braincore` | ADRs, ingesta, chunks, busqueda textual/vectorial y metricas |
| `src/config/settings.py` | Variables de entorno y configuracion central |
| `src/llm/ollama_client.py` | Cliente Ollama, completions, stream y tool parsing |
| `src/memory/mysql_manager.py` | Fachada MySQL, schema, auditoria, sesiones, BrainCore y delegacion a repositorios |
| `src/memory/repositories/audit.py` | Repositorio de auditoria: tool executions, API access log y pruning |
| `src/memory/repositories/api_keys.py` | Repositorio de API keys gestionadas: create, find active, list y revoke |
| `src/memory/repositories/brain_decisions.py` | Repositorio BrainCore para decisiones ADR: register y list |
| `src/memory/repositories/brain_domains.py` | Repositorio BrainCore para export/delete por dominio |
| `src/memory/repositories/brain_metrics.py` | Repositorio BrainCore para metricas agregadas de decisiones, fuentes, chunks, dominios y tipos |
| `src/memory/repositories/brain_search.py` | Repositorio BrainCore para busqueda lexical y ranking de chunks |
| `src/memory/repositories/brain_sources.py` | Repositorio BrainCore para fuentes y chunks: upsert, list y delete |
| `src/memory/repositories/lessons.py` | Repositorio de memoria evolutiva: registrar, consultar y actualizar uso de lecciones |
| `src/memory/repositories/sessions.py` | Repositorio de sesiones de agente, contexto conversacional y pruning asociado |
| `src/memory/repositories/sql_runtime.py` | Repositorio de schema dinamico, queries SELECT y formateo de schema para prompt |
| `src/memory/redis_manager.py` | Historial temporal, rate limiting, memoria compartida y pendientes HITL |
| `src/security/guardrails.py` | Seguridad heuristica de entrada/salida y mascaramiento PII |
| `src/tools/tools_manager.py` | Dispatcher de herramientas, auditoria, HITL y delegacion multi-agente |
| `src/utils` | Logging y modelos internos compartidos |

## Superficie API Principal

- `GET /health`
- `GET /api/version`
- `POST /chat`
- `POST /chat/stream`
- `GET /dashboard`
- `GET /system/readiness`
- `GET /system/metrics`
- `GET/POST /braincore/decisions`
- `GET /braincore/sources`
- `DELETE /braincore/sources/{source_id}`
- `POST /braincore/ingest`
- `POST /braincore/search`
- `GET /braincore/metrics`
- `GET /sessions`
- `GET /sessions/{session_id}/context`
- `GET /tools/executions`
- `GET /tools/pending`
- `POST /tools/pending/{tool_id}/approve`
- `POST /tools/pending/{tool_id}/reject`
- `POST /tools/pending/{tool_id}/resume`
- `GET /api/access-log`
- `GET/POST /api/keys`
- `POST /api/keys/{key_id}/revoke`
- `POST /webhooks/telegram`
- `POST /webhooks/slack`

## Tests

```text
tests/
|- conftest.py
|- test_agent_loop.py
|- test_api_app.py
|- test_braincore_manager.py
|- test_braincore_vector_store.py
|- test_mysql_manager.py
|- test_ollama_client.py
|- test_readiness_gate.py
|- test_scheduler.py
|- test_startup_integration.py
|- test_tools_manager.py
`- integration/
   |- test_mysql_integration.py
   `- test_vectordb_integration.py
```

Markers opt-in:

- `integration_mysql`
- `integration_vector`

## Docker y CI

| Archivo | Proposito |
|---------|-----------|
| `docker/Dockerfile` | Imagen Python API-first con perfil de dependencias configurable y healthcheck `/health` |
| `docker/docker-compose.yml` | Stack local con ACU, MySQL, Redis, Ollama, Jaeger, scheduler, retencion y healthchecks |
| `docker/docker-compose.prod.yml` | Compose de produccion con scheduler dedicado, healthchecks e imagen configurable con `ACU_IMAGE` |
| `docker/docker-stack.yml` | Plantilla Swarm con API escalable, scheduler replica unica, healthchecks e imagen configurable con `ACU_IMAGE` |
| `scripts/readiness_gate.py` | Gate CLI para bloquear despliegues con `/system/readiness` en `not_ready` |
| `.github/workflows/ci.yml` | Calidad, tests, integracion MySQL/vectorial, validacion Docker, smoke test `/health` + readiness y publicacion GHCR |
| `.github/workflows/tests.yml` | Workflow simple de pytest |

## Flujos Clave

### Chat ReAct

```text
POST /chat
  -> ACUAgent.process_user_message()
  -> observation/thought/action/conclusion
  -> ToolsManager si hay herramienta
  -> auditoria y persistencia
```

### HITL

```text
herramienta sensible
  -> ToolsManager crea pending_tool_id
  -> POST /tools/pending/{id}/approve
  -> execute_pending_tool()
  -> POST /tools/pending/{id}/resume
  -> ACUAgent.resume_after_tool_approval()
```

### Scheduler

```text
ACU_SCHEDULER_MODE=disabled  # default seguro
ACU_SCHEDULER_MODE=worker
python -m src.api.scheduler
```

### BrainCore

```text
ingest_path()
  -> ingestion.collect_documents()
  -> mysql_manager upsert source/chunks
  -> vector_store opcional
  -> fallback textual si vector no esta disponible
```

## Datos Locales

```text
data/
  vectors/
```

`data/vectors` almacena indices ChromaDB/FAISS locales cuando el vector store esta habilitado.

## Convenciones

- Codigo Python en `src/`.
- Tests en `tests/`.
- Documentacion operativa en raiz.
- Documentacion tecnica e historica en `wiki/`.
- Configuracion sensible en `.env`, no en git.
- Artefactos generados (`__pycache__`, caches, indices vectoriales) no forman parte del codigo fuente.

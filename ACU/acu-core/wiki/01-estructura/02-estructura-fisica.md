# Estructura Fisica del Proyecto

Este documento describe la estructura vigente de `acu-core` durante la estabilizacion profesional.

**Fecha de actualizacion**: 2026-05-19  
**Estado**: Fase 9 cerrada; baseline tecnico verde con operacion, readiness, CI y gobierno BrainCore  
**Verificacion**: `ruff check`, `ruff format --check`, `mypy src scripts main.py`, `241 passed, 4 skipped`

## Arbol Principal

```text
acu-core/
  main.py
  setup.py
  requirements.txt
  requirements/
  pytest.ini
  mypy.ini
  .env.example
  README.md
  USAGE.md
  ARCHITECTURE.md
  PROJECT_STRUCTURE.md
  DELIVERY.md
  .github/
  docker/
  src/
  tests/
  wiki/
    04-decisiones/seguridad-operativa.md
  data/
```

## Raiz

| Archivo | Proposito |
|---------|-----------|
| `main.py` | Entrada CLI/demo del agente ACU |
| `setup.py` | Setup local y validaciones iniciales |
| `requirements.txt` | Perfil completo por compatibilidad |
| `requirements/` | Perfiles `base`, `dev`, `vector`, `vector-faiss`, `observability` y `all` |
| `pytest.ini` | Configuracion pytest y salida limpia |
| `mypy.ini` | Configuracion de tipado estatico |
| `.env.example` | Variables de entorno de referencia |
| `README.md` | Guia principal |
| `USAGE.md` | Guia operativa y ejemplos |
| `ARCHITECTURE.md` | Arquitectura tecnica vigente |
| `PROJECT_STRUCTURE.md` | Resumen de estructura y modulos |
| `DELIVERY.md` | Entrega historica y estado agregado |
| `.github/workflows/` | CI de calidad, integracion MySQL, integracion vectorial y build |

## Codigo Fuente

```text
src/
  __init__.py
  agent/
    __init__.py
    agent_loop.py
    prompting.py
  api/
    __init__.py
    app.py
    agent_runtime.py
    dashboard.py
    readiness.py
    scheduler.py
    security.py
    schemas.py
    telemetry.py
    webhooks.py
    routes/
      __init__.py
      braincore.py
      chat.py
      system.py
    static/
      dashboard.css
      dashboard.js
    templates/
      dashboard.html
  braincore/
    __init__.py
    ingestion.py
    manager.py
    vector_store.py
  config/
    __init__.py
    settings.py
  llm/
    __init__.py
    ollama_client.py
  memory/
    __init__.py
    mysql_manager.py
    redis_manager.py
  security/
    __init__.py
    guardrails.py
  tools/
    __init__.py
    tools_manager.py
  utils/
    __init__.py
    logger.py
    schemas.py
```

## Modulos

### `src/agent/`

Responsable del nucleo ReAct.

- `agent_loop.py`: ciclo de observacion, pensamiento, accion y conclusion.
- `prompting.py`: construccion del system prompt, herramientas y schema dinamico.

### `src/api/`

Responsable de la API REST y dashboard.

- `app.py`: ensamblaje FastAPI, middlewares, providers, OpenAPI y helpers transversales.
- `agent_runtime.py`: inicializacion compartida del agente para chat y HITL resume.
- `readiness.py`: checklist runtime de exposicion operativa.
- `security.py`: API keys, RBAC, fingerprints, expiracion y resolucion de identidad.
- `routes/api_keys.py`: rutas de API keys gestionadas.
- `routes/braincore.py`: rutas BrainCore para decisiones, fuentes, ingesta, busqueda, export y delete por dominio.
- `routes/chat.py`: rutas `/chat` y `/chat/stream`.
- `routes/monitoring.py`: sesiones, contexto conversacional y auditoria.
- `routes/system.py`: health, version, dashboard, metricas y readiness.
- `routes/tools.py`: HITL para herramientas pendientes.
- `schemas.py`: modelos Pydantic de requests/responses API.
- `dashboard.py`: loader cacheado del template del dashboard.
- `scheduler.py`: scheduler operativo de mantenimiento con modo API/worker configurable.
- `telemetry.py`: configuracion OpenTelemetry.
- `webhooks.py`: entradas externas para Slack/Telegram con validacion opt-in de secretos, firmas, replay window y allowlists.
- `templates/dashboard.html`: estructura HTML del dashboard operativo.
- `static/dashboard.css`: estilos del dashboard.
- `static/dashboard.js`: logica de cliente del dashboard.

Endpoints principales:

- `GET /health`
- `GET /api/version`
- `POST /chat`
- `GET /dashboard`
- `GET/POST /braincore/decisions`
- `GET /braincore/sources`
- `DELETE /braincore/sources/{source_id}`
- `POST /braincore/ingest`
- `POST /braincore/search`
- `GET /braincore/metrics`
- `GET /braincore/domains/{domain}/export`
- `DELETE /braincore/domains/{domain}`
- `GET /system/readiness`
- `GET /system/metrics`
- `GET /sessions`
- `GET /sessions/{session_id}/context`
- `GET /tools/executions`
- `GET /api/access-log`
- `GET/POST /api/keys`
- `POST /api/keys/{key_id}/revoke`
- `GET /tools/pending` (`admin`)
- `POST /tools/pending/{tool_id}/approve` (`admin`)
- `POST /tools/pending/{tool_id}/reject` (`admin`)
- `POST /tools/pending/{tool_id}/resume` (`admin`)
- `POST /webhooks/telegram`
- `POST /webhooks/slack`

### `src/braincore/`

Responsable de memoria agentica transversal.

- `manager.py`: orquestacion BrainCore.
- `ingestion.py`: recoleccion y chunking de documentos locales.
- `vector_store.py`: ChromaDB/FAISS opcionales con fallback textual en MySQL.

Capacidades:

- Decisiones arquitectonicas.
- Ingesta local de fuentes.
- Busqueda textual/vectorial.
- Inventario y eliminacion de fuentes.
- Metricas agregadas.
- Estado runtime del vector store.

### `src/config/`

Responsable de configuracion centralizada.

- `settings.py`: dataclasses de Ollama, MySQL, vector DB, agente, sistema y API.

### `src/llm/`

Responsable del cliente Ollama.

- `ollama_client.py`: health check, completions, listado de modelos y parsing de tool calls.

### `src/memory/`

Responsable de MySQL y persistencia.

- `mysql_manager.py`: conexion, schema dinamico, SQL read-only, memoria evolutiva, auditoria, sesiones, API keys y BrainCore.
- `redis_manager.py`: historial temporal, rate limiting distribuido, memoria compartida y herramientas pendientes.

Tablas soportadas:

- `memoria_evolutiva`
- `tool_execution_log`
- `api_access_log`
- `api_keys`
- `agent_sessions`
- `conversation_context`
- `brain_decisions`
- `brain_sources`
- `brain_chunks`

### `src/tools/`

Responsable del dispatcher de herramientas del agente.

- `tools_manager.py`: SQL read-only, busqueda documental, BrainCore, registrar/consultar lecciones, HITL, delegacion y auditoria.

### `src/security/`

Responsable de guardrails del agente.

- `guardrails.py`: validaciones heuristicas de entrada/salida y enmascaramiento de PII.

### `src/utils/`

Responsable de utilidades compartidas.

- `logger.py`: logging.
- `schemas.py`: modelos internos del agente y herramientas.

## Tests

```text
tests/
  conftest.py
  test_agent_loop.py
  test_api_app.py
  test_braincore_manager.py
  test_braincore_vector_store.py
  test_mysql_manager.py
  test_ollama_client.py
  test_scheduler.py
  test_startup_integration.py
  test_tools_manager.py
  integration/
    test_mysql_integration.py
    test_vectordb_integration.py
```

Estado actual:

```text
241 passed, 4 skipped
```

Cobertura funcional:

- API REST.
- Auth por API key y roles.
- API keys gestionadas.
- Dashboard HTML/CSS/JS esperado.
- BrainCore manager.
- BrainCore vector store ChromaDB/FAISS con fakes.
- MySQL connector con fakes.
- Tools manager.
- Scheduler operativo API/worker.
- Agent loop.
- Startup integration.
- Ollama client.
- MySQL real opt-in validado: `3 passed` contra MySQL Docker en `localhost:3307`.
- VectorDB real opt-in mediante marker `integration_vector`.

## Docker

```text
docker/
  Dockerfile
  docker-compose.yml
  docker-compose.prod.yml
  docker-stack.yml
  init.sql
```

Proposito:

- MySQL local.
- Redis local.
- Ollama local.
- Servicio ACU.
- Scheduler dedicado con replica unica.
- Retencion de auditoria y contexto desde `acu-scheduler`.
- Compose productivo y plantilla Swarm.
- Imagen productiva configurable con `ACU_IMAGE`.
- Tablas iniciales y usuario `acu_reader`.

Validacion:

- `docker compose -f docker/docker-compose.yml config --quiet`
- `docker compose -f docker/docker-compose.prod.yml config --quiet`
- `docker compose -f docker/docker-stack.yml config --quiet`

## Wiki

```text
wiki/
  README.md
  01-estructura/
    00-vision-general.md
    01-arquitectura-core.md
    02-estructura-fisica.md
  02-bitacoras/
    README.md
    fase-01-foundation.md
    fase-02-enhancement.md
    fase-03-estandarizacion-roadmap.md
    fase-04-expansion-herramientas.md
    fase-05-hardening-observabilidad.md
    fase-06-orquestacion-multi-agente.md
    fase-07-interfaces-conversacionales.md
    fase-08-estabilizacion-profesional.md
    fase-09-operacion-observabilidad.md
    plantilla-fase.md
    changelog.md
  03-componentes/
    README.md
  04-decisiones/
    README.md
  05-referencias/
    README.md
```

## Datos Locales

```text
data/
  vectors/
    braincore_faiss_metadata.json
```

`data/vectors` se usa para persistencia vectorial local cuando BrainCore opera con FAISS o ChromaDB.

## Responsabilidades Por Area

| Area | Ubicacion | Estado |
|------|-----------|--------|
| ReAct core | `src/agent` | Operativo |
| API REST | `src/api/app.py` | Operativa |
| Dashboard | `src/api/templates` + `src/api/static` | Operativo |
| API schemas | `src/api/schemas.py` | Operativos |
| BrainCore | `src/braincore` | Operativo |
| MySQL/persistencia | `src/memory/mysql_manager.py` | Operativa |
| Redis/cache temporal | `src/memory/redis_manager.py` | Operativo con fallback local |
| Seguridad/guardrails | `src/security/guardrails.py` | Operativa |
| Webhooks | `src/api/webhooks.py` | Operativos con validacion opt-in |
| Scheduler | `src/api/scheduler.py` | Operativo en modo API/worker |
| Tools | `src/tools/tools_manager.py` | Operativas |
| Ollama | `src/llm/ollama_client.py` | Operativo |
| Tests | `tests/` | Operativos |
| Docker | `docker/` | Disponible |
| CI/CD | `.github/workflows` | Configurado |

## Convenciones

- Codigo Python en `src/`.
- Tests en `tests/`.
- Documentacion de producto/uso en raiz.
- Documentacion historica y tecnica en `wiki/`.
- Datos generados/locales en `data/`.
- Configuracion sensible fuera de git mediante `.env`.

## Siguiente Foco Recomendado

Fase 10:

1. Definir catalogo de metricas Prometheus.
2. Implementar exportador Prometheus opt-in.
3. Versionar dashboard Grafana y alertas iniciales.

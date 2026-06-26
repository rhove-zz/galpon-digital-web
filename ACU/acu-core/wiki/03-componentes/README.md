# Componentes - Documentacion Tecnica

Indice actualizado de componentes del sistema ACU durante la estabilizacion profesional.

**Fecha de actualizacion**: 2026-05-19  
**Estado**: Baseline tecnico verde; Fase 9 cerrada operativamente  
**Verificacion**: `ruff check`, `ruff format --check`, `mypy src scripts main.py`, `241 passed, 4 skipped`

## Componentes Principales

### Agent Core

**Ubicacion**: `src/agent/`

Archivos:

- `agent_loop.py`
- `prompting.py`

Responsabilidades:

- Ejecutar el ciclo ReAct.
- Coordinar observacion, pensamiento, accion y conclusion.
- Construir prompts con herramientas y schema dinamico.
- Persistir sesiones y contexto conversacional cuando corresponde.

Entradas principales:

- `ACUAgent.initialize()`
- `ACUAgent.process_user_message()`
- `get_agent()`

### API REST

**Ubicacion**: `src/api/`

Archivos:

- `app.py`
- `schemas.py`
- `dashboard.py`
- `scheduler.py`
- `telemetry.py`
- `webhooks.py`
- `templates/dashboard.html`
- `static/dashboard.css`
- `static/dashboard.js`

Responsabilidades:

- Exponer FastAPI.
- Aplicar autenticacion y autorizacion por API key.
- Definir schemas Pydantic de entrada/salida.
- Servir dashboard operativo.
- Exponer webhooks y consola HITL.
- Inicializar Redis y telemetria en lifespan; scheduler solo si `ACU_SCHEDULER_MODE` habilita contexto API.

Superficies principales:

- `/health`
- `/chat`
- `/dashboard`
- `/braincore/*`
- `/sessions`
- `/tools/executions`
- `/tools/pending`
- `/api/access-log`
- `/api/keys`
- `/system/readiness`
- `/system/metrics`
- `/webhooks/*`

Contrato operativo:

- [Observabilidad - Contrato `/system/metrics`](observabilidad-system-metrics.md)
- [Readiness operativa - Contrato `/system/readiness`](readiness-operativa.md)
- [Journeys funcionales criticos](journeys-funcionales.md)

### Dashboard Operativo

**Ubicacion**: `src/api/`

Archivos:

- `dashboard.py`: loader cacheado del template HTML.
- `templates/dashboard.html`: estructura del dashboard.
- `static/dashboard.css`: estilos del dashboard.
- `static/dashboard.js`: logica de cliente y llamadas API.

Responsabilidades:

- Chat ACU desde navegador.
- Monitoreo de sesiones.
- Visualizacion de contexto conversacional.
- Auditoria de herramientas.
- Auditoria de accesos API.
- Gestion de claves API.
- Operacion BrainCore: decisiones, busqueda, ingesta, fuentes, eliminacion y metricas.
- Estado de sistema, politicas runtime y vector store.
- Metricas HITL, scheduler, Redis y webhooks desde `/system/metrics`.
- Mensajes de error accionables para auth, payload, rate limit y validacion.

Nota tecnica:

- El dashboard ya no esta embebido como string gigante en Python.
- FastAPI sirve `/dashboard` desde template y `/static/*` desde archivos estaticos.

### BrainCore

**Ubicacion**: `src/braincore/`

Archivos:

- `manager.py`
- `ingestion.py`
- `vector_store.py`

Responsabilidades:

- Registrar y listar decisiones arquitectonicas.
- Ingerir fuentes locales y dividirlas en chunks.
- Buscar contexto textual y vectorial.
- Listar y eliminar fuentes indexadas.
- Exponer metricas agregadas.
- Exponer estado ligero del vector store.
- Integrarse con ChromaDB o FAISS cuando estan habilitados.
- Mantener fallback textual por MySQL.

### Memory / MySQL

**Ubicacion**: `src/memory/mysql_manager.py`

Responsabilidades:

- Conexion MySQL read-only y write.
- Schema dinamico desde `information_schema`.
- SQL read-only para herramientas.
- Memoria evolutiva.
- Auditoria de herramientas.
- Auditoria de accesos API.
- Sesiones y contexto conversacional.
- API keys gestionadas.
- Persistencia BrainCore.

Tablas principales:

- `memoria_evolutiva`
- `tool_execution_log`
- `api_access_log`
- `api_keys`
- `agent_sessions`
- `conversation_context`
- `brain_decisions`
- `brain_sources`
- `brain_chunks`

### Tools Manager

**Ubicacion**: `src/tools/tools_manager.py`

Responsabilidades:

- Ejecutar herramientas solicitadas por el agente.
- Validar parametros.
- Normalizar resultados.
- Auditar ejecuciones.

Herramientas principales:

- `ejecutar_sql_lectura`
- `buscar_documentos`
- `buscar_contexto_braincore`
- `registrar_leccion`
- `consultar_lecciones_aprendidas`
- `leer_pagina_web`
- `busqueda_web`
- `peticion_api_rest`
- `gestionar_archivos`
- `ejecutar_python`
- `delegar_tarea`
- `escribir_memoria_compartida`
- `leer_memoria_compartida`

### Redis / Memoria Temporal

**Ubicacion**: `src/memory/redis_manager.py`

Responsabilidades:

- Historial temporal de sesiones.
- Rate limiting distribuido.
- Memoria compartida para workflows multi-agente.
- Herramientas pendientes de aprobacion HITL.

### Seguridad / Guardrails

**Ubicacion**: `src/security/guardrails.py`

Responsabilidades:

- Validar entrada del usuario.
- Filtrar salida del agente.
- Enmascarar PII.

### LLM / Ollama

**Ubicacion**: `src/llm/ollama_client.py`

Responsabilidades:

- Verificar conexion con Ollama.
- Generar respuestas.
- Parsear tool calls.
- Listar modelos disponibles.
- Manejar timeouts y errores HTTP.

### Configuracion

**Ubicacion**: `src/config/settings.py`

Responsabilidades:

- Centralizar variables de entorno.
- Definir configuracion de Ollama, MySQL, vector DB, agente, sistema y API.
- Exponer instancias globales de configuracion.

### Utilidades

**Ubicacion**: `src/utils/`

Archivos:

- `logger.py`
- `schemas.py`

Responsabilidades:

- Logging.
- Schemas internos del agente.
- Tipos de tool calls, resultados, estado ReAct y contexto.

## Flujo Principal

```text
Usuario / Dashboard / API client
  -> FastAPI / CLI
  -> ACUAgent
  -> PromptBuilder
  -> OllamaClient
  -> ToolsManager
  -> MySQL / BrainCore / memoria
  -> auditoria y persistencia
  -> respuesta
```

## Flujo BrainCore

```text
POST /braincore/ingest
  -> BrainCoreManager.ingest_path()
  -> BrainCoreIngestion.collect_documents()
  -> MySQLConnector.upsert_brain_source()
  -> BrainCoreVectorStore.upsert_documents()

POST /braincore/search
  -> BrainCoreManager.search_context()
  -> BrainCoreVectorStore.search()
  -> fallback MySQLConnector.search_brain_chunks()

DELETE /braincore/sources/{source_id}
  -> MySQLConnector.delete_brain_source()
  -> BrainCoreVectorStore.delete_source()
```

## Flujo Seguridad API

```text
Request
  -> middleware API key
  -> resolver clave estatica o gestionada
  -> validar rol requerido
  -> endpoint
  -> log_api_access()
```

Roles:

- `admin`
- `chat`
- `braincore_read`
- `braincore_write`
- `monitoring`

## Tests Relacionados

```text
tests/test_agent_loop.py
tests/test_api_app.py
tests/test_braincore_manager.py
tests/test_braincore_vector_store.py
tests/test_mysql_manager.py
tests/test_ollama_client.py
tests/test_startup_integration.py
tests/test_docker_config.py
tests/integration/test_mysql_integration.py
tests/test_tools_manager.py
```

## Estado De Calidad

```bash
python -m pytest
python -m ruff check src tests scripts main.py
python -m ruff format --check src tests scripts main.py
python -m mypy src scripts main.py --ignore-missing-imports
```

Resultado esperado:

```text
241 passed, 4 skipped
```

## Pendientes De Componentizacion

1. Mantener el patron de firma/secreto para nuevos conectores externos.
2. Definir catalogo de metricas Prometheus para Fase 10.

## Referencias Cruzadas

- [Vision general](../01-estructura/00-vision-general.md)
- [Arquitectura core](../01-estructura/01-arquitectura-core.md)
- [Estructura fisica](../01-estructura/02-estructura-fisica.md)
- [Fase 2 Enhancement](../02-bitacoras/fase-02-enhancement.md)
- [Fase 9 Operacion y Observabilidad](../02-bitacoras/fase-09-operacion-observabilidad.md)
- [Decisiones tecnicas](../04-decisiones/README.md)

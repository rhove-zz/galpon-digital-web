# Arquitectura Core

Este documento describe la arquitectura vigente de `acu-core` durante la estabilizacion profesional.

**Fecha de actualizacion**: 2026-05-19  
**Estado**: Baseline tecnico verde; Fase 9 cerrada operativamente  
**Verificacion**: `ruff check`, `ruff format --check`, `mypy src scripts main.py`, `241 passed, 4 skipped`

## Vision General

```text
Cliente CLI / HTTP / Dashboard
  -> FastAPI (`src/api/app.py`) o CLI (`main.py`)
  -> ACUAgent (`src/agent/agent_loop.py`)
  -> PromptBuilder (`src/agent/prompting.py`)
  -> OllamaClient (`src/llm/ollama_client.py`)
  -> ToolsManager (`src/tools/tools_manager.py`)
  -> MySQLConnector (`src/memory/mysql_manager.py`)
  -> BrainCore (`src/braincore/manager.py`)
  -> Redis (`src/memory/redis_manager.py`)
  -> Scheduler (`src/api/scheduler.py`)
  -> Auditoria y sesiones
```

ACU esta organizado como un agente ReAct con interfaces operativas encima: CLI, API REST y dashboard. La API expone el chat, BrainCore, auditoria, sesiones, gestion de API keys y metricas de sistema. BrainCore funciona como memoria agentica transversal con decisiones, fuentes, chunks, busqueda y metricas.

## Capas Principales

### 1. Capa de Interfaz

Ubicacion:

- `main.py`
- `src/api/app.py`
- `src/api/dashboard.py`
- `src/api/templates/dashboard.html`
- `src/api/static/dashboard.css`
- `src/api/static/dashboard.js`

Responsabilidades:

- Entrada CLI para uso directo del agente.
- API REST con FastAPI.
- Dashboard operativo servido desde template HTML y archivos estaticos.
- Serializacion de requests/responses mediante schemas Pydantic.
- Webhooks para integraciones externas bajo `/webhooks`.

### 2. Capa API y Seguridad

Ubicacion:

- `src/api/app.py`
- `src/api/schemas.py`
- `src/memory/mysql_manager.py`

Responsabilidades:

- Middleware de autenticacion por `X-API-Key`.
- Resolucion de roles desde configuracion estatica o API keys gestionadas.
- Control de acceso por endpoint.
- CORS configurable por allowlist.
- Limite configurable de payload por `Content-Length`.
- Rate limiting en memoria por API key o IP.
- Auditoria de accesos API.
- Gestion de API keys: listar, crear y revocar.

Roles soportados:

| Rol | Alcance |
|-----|---------|
| `admin` | Acceso completo |
| `chat` | Uso de `POST /chat` |
| `braincore_read` | Lectura y busqueda BrainCore |
| `braincore_write` | Escritura BrainCore y permisos de lectura BrainCore |
| `monitoring` | Dashboard, health, sesiones, logs, herramientas, readiness y metricas de sistema |

### 3. Capa del Agente

Ubicacion:

- `src/agent/agent_loop.py`
- `src/agent/prompting.py`

Responsabilidades:

- Ejecutar el ciclo ReAct: observar, razonar, actuar y concluir.
- Mantener historial de conversacion.
- Coordinar LLM, herramientas, memoria y contexto.
- Construir system prompts dinamicos con schema de base de datos y herramientas disponibles.

Flujo interno:

```text
Mensaje de usuario
  -> construir estado ReAct
  -> generar pensamiento con Ollama
  -> parsear tool calls
  -> ejecutar herramientas
  -> incorporar observaciones
  -> concluir respuesta
```

### 4. Capa LLM

Ubicacion:

- `src/llm/ollama_client.py`

Responsabilidades:

- Verificar conexion con Ollama.
- Generar respuestas.
- Listar modelos disponibles.
- Parsear tool calls JSON producidos por el modelo.

Configuracion principal:

- Host y puerto Ollama.
- Modelo activo.
- Timeout.
- Parametros de generacion.

### 5. Capa de Herramientas

Ubicacion:

- `src/tools/tools_manager.py`

Responsabilidades:

- Despachar herramientas invocadas por el agente.
- Validar parametros.
- Medir tiempos de ejecucion.
- Registrar ejecuciones y errores.
- Integrar MySQL y BrainCore como acciones disponibles.
- Gestionar Human-in-the-Loop para herramientas sensibles.
- Delegar tareas a sub-agentes especializados.

Herramientas principales:

| Herramienta | Proposito |
|-------------|-----------|
| `ejecutar_sql_lectura` | Ejecutar consultas `SELECT` seguras |
| `buscar_documentos` | Buscar informacion documental |
| `buscar_contexto_braincore` | Recuperar contexto agentico desde BrainCore |
| `registrar_leccion` | Persistir aprendizajes |
| `consultar_lecciones_aprendidas` | Recuperar aprendizajes previos |

### 6. Capa de Persistencia

Ubicacion:

- `src/memory/mysql_manager.py`

Responsabilidades:

- Conexion MySQL.
- Extraccion de schema dinamico desde `information_schema`.
- Ejecucion de SQL read-only para el agente.
- Memoria evolutiva.
- Logs de herramientas.
- Logs de API.
- Sesiones y contexto conversacional.
- API keys gestionadas.
- Persistencia BrainCore.

Tablas funcionales:

- `memoria_evolutiva`
- `tool_execution_log`
- `api_access_log`
- `api_keys`
- `agent_sessions`
- `conversation_context`
- `brain_decisions`
- `brain_sources`
- `brain_chunks`

### 7. Capa BrainCore

Ubicacion:

- `src/braincore/manager.py`
- `src/braincore/ingestion.py`
- `src/braincore/vector_store.py`

Responsabilidades:

- Registrar decisiones arquitectonicas.
- Ingerir fuentes locales.
- Dividir contenido en chunks.
- Persistir fuentes y chunks en MySQL.
- Indexar y buscar en ChromaDB o FAISS cuando estan disponibles.
- Usar fallback textual MySQL cuando no hay motor vectorial.
- Listar, filtrar y eliminar fuentes.
- Calcular metricas agregadas.
- Reportar estado runtime del vector store.

Endpoints relacionados:

- `GET /braincore/decisions`
- `POST /braincore/decisions`
- `GET /braincore/sources`
- `DELETE /braincore/sources/{source_id}`
- `POST /braincore/ingest`
- `POST /braincore/search`
- `GET /braincore/metrics`
- `GET /system/readiness`
- `GET /system/metrics`

### 8. Capa de Configuracion y Soporte

Ubicacion:

- `src/config/settings.py`
- `src/utils/logger.py`
- `src/utils/schemas.py`

Responsabilidades:

- Variables de entorno.
- Dataclasses de configuracion.
- Logging.
- Schemas internos del agente y herramientas.

### 9. Capa de Orquestacion Operativa

Ubicacion:

- `src/api/scheduler.py`
- `src/api/telemetry.py`
- `src/api/webhooks.py`
- `src/memory/redis_manager.py`
- `src/security/guardrails.py`

Responsabilidades:

- Scheduler de tareas operativas.
- Telemetria OpenTelemetry.
- Webhooks externos.
- Redis para historial, rate limiting distribuido, memoria compartida y aprobaciones pendientes.
- Guardrails de entrada/salida del agente.

Restriccion actual:

- El scheduler no arranca por defecto dentro de FastAPI. Se controla con `ACU_SCHEDULER_MODE` y puede correr como worker dedicado con `python -m src.api.scheduler`.

## Flujos Operativos

### Chat

```text
POST /chat
  -> validar API key y rol `chat`
  -> crear/recuperar sesion
  -> ACUAgent.process_user_message()
  -> ejecutar ciclo ReAct
  -> registrar contexto y tool calls
  -> devolver respuesta estructurada
```

### BrainCore Ingesta

```text
POST /braincore/ingest
  -> validar rol `braincore_write`
  -> leer fuente local
  -> chunking
  -> upsert de source/chunks en MySQL
  -> indexacion vectorial opcional
  -> devolver resumen de ingesta
```

### BrainCore Busqueda

```text
POST /braincore/search
  -> validar rol `braincore_read` o `braincore_write`
  -> consultar vector store si esta disponible
  -> combinar con fallback textual MySQL
  -> devolver resultados con score, source y metadata
```

### BrainCore Fuentes

```text
GET /braincore/sources
  -> validar rol BrainCore
  -> aplicar filtros por domain, source_type, status y limit
  -> devolver inventario

DELETE /braincore/sources/{source_id}
  -> validar rol `braincore_write`
  -> eliminar chunks y source en MySQL
  -> eliminar referencia en vector store
```

### Dashboard

```text
GET /dashboard
  -> servir template HTML
  -> cargar CSS/JS desde `/static`
  -> consumir endpoints REST desde el navegador con API key local si aplica
```

El dashboard incluye paneles para health, chat, BrainCore, sesiones, herramientas, auditoria, API keys, seguridad runtime y estado del vector store.

## Dependencias Internas

```text
src/api/app.py
  -> src/api/schemas.py
  -> src/api/dashboard.py
  -> src/agent/agent_loop.py
  -> src/braincore/manager.py
  -> src/memory/mysql_manager.py

src/agent/agent_loop.py
  -> src/agent/prompting.py
  -> src/llm/ollama_client.py
  -> src/tools/tools_manager.py
  -> src/memory/mysql_manager.py

src/tools/tools_manager.py
  -> src/memory/mysql_manager.py
  -> src/braincore/manager.py
  -> src/utils/schemas.py

src/braincore/manager.py
  -> src/braincore/ingestion.py
  -> src/braincore/vector_store.py
  -> src/memory/mysql_manager.py
```

## Patrones de Diseno

| Patron | Uso |
|--------|-----|
| Singleton liviano | Clientes y managers compartidos mediante factories `get_*` |
| Provider injection | Tests y API pueden inyectar agente, DB y BrainCore |
| ReAct loop | Coordinacion agente-LLM-herramientas |
| Repository/manager | MySQLConnector concentra persistencia |
| Fallback strategy | BrainCore usa vector store o busqueda textual MySQL |
| Schema validation | Pydantic valida contratos API |

## Limites y Restricciones

| Area | Restriccion |
|------|-------------|
| SQL del agente | Solo consultas read-only |
| API | Autenticacion por API key salvo rutas publicas controladas |
| Roles | Autorizacion por endpoint |
| BrainCore | Vector store opcional con fallback MySQL |
| Dashboard | Template HTML y static CSS/JS servidos por FastAPI |
| Docker | Disponible para entorno local y pruebas reales MySQL opt-in |
| HITL | No bloqueante con `pending_tool_id`, aprobacion, ejecucion y reanudacion |
| Webhooks | Hardening opt-in con secretos, firmas, replay window y allowlists |
| Scheduler | Worker dedicado/configurable para evitar jobs duplicados |

## Estado de Calidad

Suite actual:

```text
python -m ruff check src tests scripts main.py
python -m ruff format --check src tests scripts main.py
python -m mypy src scripts main.py --ignore-missing-imports
python -m pytest
241 passed, 4 skipped
```

Verificacion adicional:

```text
python -m compileall src
```

Cobertura funcional existente:

- Agent loop.
- Ollama client.
- Tools manager.
- MySQL manager con fakes.
- BrainCore manager.
- BrainCore vector store con fakes.
- API REST, auth, roles y dashboard.
- Startup integration.
- Integracion MySQL real opt-in validada: `3 passed` contra MySQL Docker en `localhost:3307`.
- Integracion VectorDB real opt-in mediante marker `integration_vector`.

## Decisiones Vigentes

1. Mantener dashboard sin frontend separado; modularizado en template/static al iniciar Fase 3.
2. Usar roles simples por API key antes de introducir RBAC complejo.
3. Permitir vector store opcional para que BrainCore funcione aun sin ChromaDB/FAISS.
4. Centralizar persistencia en `mysql_manager.py` mientras el dominio sigue estabilizandose.
5. Mantener CLI y API compartiendo el mismo nucleo `ACUAgent`.

## Pendientes Recomendados

Fase 8:

1. Ampliar cobertura de conectores externos futuros con el mismo patron de firmas/secrets.
2. Automatizar integraciones MySQL y VectorDB como jobs claramente separados.
3. Definir politica final de `requirements.txt` frente a perfiles especializados.

## Documentos Relacionados

- [Vision general](00-vision-general.md)
- [Estructura fisica](02-estructura-fisica.md)
- [Bitacora Fase 2](../02-bitacoras/fase-02-enhancement.md)
- [Componentes](../03-componentes/README.md)
- [Decisiones](../04-decisiones/README.md)

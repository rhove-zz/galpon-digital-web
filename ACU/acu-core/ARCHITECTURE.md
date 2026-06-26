# Arquitectura Tecnica - ACU v1.0

## Objetivo

ACU implementa un agente ReAct que decide acciones a partir de:

- contexto conversacional
- schema dinamico de MySQL
- herramientas operativas
- memoria evolutiva persistente

## Componentes

### `src/config/settings.py`

Centraliza configuracion de:

- Ollama
- MySQL
- parametros del agente
- configuracion reservada para futuras integraciones de busqueda avanzada

### `src/llm/ollama_client.py`

Responsable de:

- verificar conexion a Ollama
- enviar prompts
- recibir respuestas del modelo
- extraer tool calls del texto devuelto

### `src/memory/mysql_manager.py`

Responsable de:

- conectar a MySQL en modo lectura o escritura
- extraer schema desde `information_schema`
- ejecutar `SELECT`
- registrar lecciones en `memoria_evolutiva`
- consultar lecciones previas
- mantener la fachada publica de persistencia usada por API, agente y BrainCore
- delegar auditoria de herramientas y accesos API en `src/memory/repositories/audit.py`
- delegar API keys gestionadas en `src/memory/repositories/api_keys.py`
- delegar decisiones BrainCore en `src/memory/repositories/brain_decisions.py`
- delegar export/delete de dominios BrainCore en `src/memory/repositories/brain_domains.py`
- delegar metricas BrainCore en `src/memory/repositories/brain_metrics.py`
- delegar busqueda BrainCore en `src/memory/repositories/brain_search.py`
- delegar fuentes/chunks BrainCore en `src/memory/repositories/brain_sources.py`
- delegar memoria evolutiva en `src/memory/repositories/lessons.py`
- delegar sesiones y contexto conversacional en `src/memory/repositories/sessions.py`
- delegar schema dinamico y queries SELECT en `src/memory/repositories/sql_runtime.py`

### `src/memory/repositories/audit.py`

Repositorio interno para auditoria operativa.

Responsabilidades:

- registrar ejecuciones de herramientas en `tool_execution_log`
- registrar accesos API en `api_access_log`
- listar auditoria de herramientas con filtros y normalizacion JSON
- listar accesos API con filtros y normalizacion de roles
- podar auditoria antigua de herramientas y accesos API

### `src/memory/repositories/api_keys.py`

Repositorio interno para API keys gestionadas.

Responsabilidades:

- crear claves gestionadas guardando solo hash y fingerprint
- buscar claves activas y actualizar `last_used_at`
- listar metadata sin exponer secretos
- revocar claves por ID
- normalizar roles JSON y campos temporales para respuestas API

### `src/memory/repositories/brain_decisions.py`

Repositorio interno para decisiones arquitectonicas BrainCore.

Responsabilidades:

- registrar ADRs en `brain_decisions`
- listar ADRs con filtros por busqueda, dominio, estado y limite
- normalizar alternativas/tags JSON y fechas para respuestas API

### `src/memory/repositories/brain_domains.py`

Repositorio interno para gobierno de dominios BrainCore.

Responsabilidades:

- exportar decisiones, fuentes y chunks por dominio
- eliminar fuentes/chunks de un dominio
- eliminar decisiones del dominio cuando se solicita explicitamente
- normalizar payloads de snapshot para respuestas API

### `src/memory/repositories/brain_metrics.py`

Repositorio interno para metricas agregadas BrainCore.

Responsabilidades:

- contar decisiones, fuentes, chunks y dominios
- agrupar fuentes/chunks por dominio
- agrupar fuentes/chunks por tipo de fuente
- normalizar buckets y timestamps para respuestas API

### `src/memory/repositories/brain_search.py`

Repositorio interno para busqueda textual BrainCore.

Responsabilidades:

- construir filtros lexicales sobre `brain_chunks` y `brain_sources`
- aplicar filtros por dominio y tipo de fuente
- rankear resultados por frase, tokens y coincidencia en titulo
- generar snippets compactos y normalizar metadata JSON

### `src/memory/repositories/brain_sources.py`

Repositorio interno para fuentes y chunks BrainCore.

Responsabilidades:

- insertar o actualizar fuentes en `brain_sources`
- reemplazar chunks asociados en `brain_chunks`
- listar fuentes con filtros por dominio, tipo, estado y conteo de chunks
- eliminar una fuente por ID delegando limpieza de chunks por FK/cascada
- normalizar metadata JSON y fechas para respuestas API

### `src/memory/repositories/lessons.py`

Repositorio interno para memoria evolutiva.

Responsabilidades:

- registrar lecciones en `memoria_evolutiva`
- buscar lecciones por categoria y texto
- rankear resultados por coincidencia y relevancia
- incrementar `veces_utilizada` para lecciones aplicadas

### `src/memory/repositories/sessions.py`

Repositorio interno para sesiones del agente y contexto conversacional.

Responsabilidades:

- iniciar y cerrar sesiones en `agent_sessions`
- registrar turnos en `conversation_context`
- listar sesiones con filtros por dominio/estado
- listar contexto conversacional por `session_id`
- podar turnos antiguos y sesiones finalizadas con su contexto asociado

### `src/memory/repositories/sql_runtime.py`

Repositorio interno para lectura SQL controlada y schema dinamico.

Responsabilidades:

- extraer schema desde `information_schema`
- ejecutar exclusivamente queries `SELECT`
- normalizar errores SQL para autocorreccion del agente
- formatear el schema cacheado para inyeccion en el prompt

### `src/tools/tools_manager.py`

Orquesta las herramientas del agente:

1. `ejecutar_sql_lectura`
2. `buscar_documentos`
3. `buscar_contexto_braincore`
4. `registrar_leccion`
5. `consultar_lecciones_aprendidas`

Estado actual:

- SQL de lectura: operativo
- busqueda documental: ChromaDB opcional con fallback textual operativo
- memoria evolutiva: operativa
- RAG vectorial: activable con `VECTOR_SEARCH_ENABLED=true`
- herramienta BrainCore ReAct: operativa
- auditoria de herramientas: operativa en `tool_execution_log`
- auditoria de acceso API: operativa en `api_access_log`
- sesiones conversacionales: operativas en `agent_sessions` y `conversation_context`
- autenticacion API key opcional: operativa
- autorizacion por roles API: operativa
- rotacion de claves API gestionadas: operativa
- BrainCore Fase 1: ADRs operativos en `brain_decisions`
- BrainCore Fase 2: ingesta operativa en `brain_sources` y `brain_chunks`
- BrainCore Fase 3: retrieval textual operativo sobre `brain_chunks`
- BrainCore Fase 4: retrieval semantico opcional en ChromaDB
- BrainCore Fase 5: retrieval semantico opcional en FAISS

### `src/api/app.py`

Ensambla la aplicacion FastAPI del core.

Estado actual:

- middlewares de API key, RBAC, auditoria, rate limit y payload limit: operativos
- providers lazy para agente, BrainCore, DB, auditoria y API keys: operativos
- router system: registrado
- router chat: registrado
- router BrainCore: registrado
- router monitoring: registrado
- router API keys: registrado
- router tools/HITL: registrado
- `GET /api/keys`: operativo
- `POST /api/keys`: operativo
- `POST /api/keys/{key_id}/revoke`: operativo

### `src/api/routes/braincore.py`

Agrupa las rutas de BrainCore.

Responsabilidades:

- `GET /braincore/decisions`
- `POST /braincore/decisions`
- `GET /braincore/sources`
- `DELETE /braincore/sources/{source_id}`
- `GET /braincore/metrics`
- `POST /braincore/ingest`
- `POST /braincore/search`
- `GET /braincore/domains/{domain}/export`
- `DELETE /braincore/domains/{domain}`

### `src/api/routes/api_keys.py`

Agrupa rutas de API keys gestionadas.

Responsabilidades:

- `POST /api/keys`
- `GET /api/keys`
- `POST /api/keys/{key_id}/revoke`
- Validar roles soportados y expiracion.
- Devolver el secreto de API key solo en la creacion.

### `src/api/routes/tools.py`

Agrupa rutas Human-in-the-loop para herramientas pendientes.

Responsabilidades:

- `GET /tools/pending`
- `POST /tools/pending/{tool_id}/approve`
- `POST /tools/pending/{tool_id}/reject`
- `POST /tools/pending/{tool_id}/resume`
- Coordinar estado pendiente con Redis/local fallback.
- Reanudar el agente usando `src/api/agent_runtime.py`.

### `src/api/routes/system.py`

Agrupa rutas de sistema y monitoreo operativo.

Responsabilidades:

- `GET /health`
- `GET /api/version`
- `GET /dashboard`
- `GET /system/metrics`
- `GET /system/readiness`

### `src/api/routes/chat.py`

Agrupa las rutas conversacionales.

Responsabilidades:

- `POST /chat`
- `POST /chat/stream`
- Inicializar el agente mediante `src/api/agent_runtime.py`.
- Serializar tool calls producidos durante el turno.

### `src/api/routes/monitoring.py`

Agrupa rutas de monitoreo persistente.

Responsabilidades:

- `GET /sessions`
- `GET /sessions/{session_id}/context`
- `GET /tools/executions`
- `GET /api/access-log`
- Leer desde `request.app.state.database_provider`.

### `src/api/agent_runtime.py`

Expone helpers compartidos para obtener un agente inicializado.

Uso actual:

- Router `chat`.
- Reanudacion HITL desde `POST /tools/pending/{tool_id}/resume`.

### `src/api/readiness.py`

Construye el checklist runtime de exposicion operativa usado por `GET /system/readiness`.

Responsabilidades:

- Validar controles criticos de auth, rate limit, payload y CORS.
- Reportar advertencias para secretos webhook y Redis.
- Verificar modo scheduler y contrato API estable.
- Mantener la logica de readiness fuera del ensamblador FastAPI.

### `src/api/security.py`

Centraliza autenticacion y autorizacion de la API.

Responsabilidades:

- Definir roles soportados y rutas publicas.
- Construir mapas de API keys estaticas.
- Resolver identidad entre claves estaticas y claves gestionadas por BD.
- Calcular hashes/fingerprints sin exponer secretos.
- Definir RBAC por endpoint y herencia simple de roles.
- Validar expiracion de claves gestionadas.
- roles API: `admin`, `chat`, `braincore_read`, `braincore_write`, `monitoring`

### `src/braincore/manager.py`

Implementa la primera capa de memoria agentica transversal.

Estado actual:

- registra decisiones arquitectonicas con contexto, alternativas e impacto
- lista decisiones por busqueda, dominio, estado y limite
- ingiere archivos y directorios locales como fuentes/chunks
- lista fuentes indexadas con conteo de chunks y filtros operativos
- expone metricas agregadas de fuentes, chunks, dominios y tipos
- expone estado runtime del vector store sin inicializar clientes pesados
- elimina fuentes indexadas y limpia el backend vectorial cuando esta activo
- recupera contexto ingerido con ranking textual
- prioriza busqueda semantica ChromaDB o FAISS cuando esta habilitada
- delega persistencia estructurada en MySQL

### `src/braincore/ingestion.py`

Extrae documentos locales para BrainCore.

Estado actual:

- soporta `.md`, `.txt`, `.sql`, `.py`, `.json`, `.yaml` y `.yml`
- omite directorios de cache, git, venv y data
- calcula hashes SHA-256 para fuente y chunks

### `src/braincore/vector_store.py`

Indexa y consulta chunks BrainCore en ChromaDB o FAISS.

Estado actual:

- se activa con `VECTOR_SEARCH_ENABLED=true`
- usa la coleccion ChromaDB `braincore_chunks` cuando `VECTOR_DB_ENGINE=chromadb`
- usa indice local `braincore_faiss.index` y metadata JSON cuando `VECTOR_DB_ENGINE=faiss`
- aplica filtros por `domain` y `source_type`
- si el backend vectorial falla, BrainCore vuelve al retrieval textual

### `src/agent/prompting.py`

Construye el system prompt con:

- instrucciones ReAct
- descripcion real de herramientas
- schema inyectado de la base de datos

### `src/agent/agent_loop.py`

Implementa el ciclo:

1. observacion
2. pensamiento
3. accion
4. conclusion

Incluye manejo defensivo cuando el LLM falla o devuelve tool calls invalidos.

## Flujo de inicializacion

```text
main.py
  -> ACUAgent()
  -> ollama_client.check_connection()
  -> db_connector.connect()
  -> db_connector.get_database_schema()
  -> prompt_builder.build_system_prompt()
```

## Flujo ReAct

```text
Usuario
  -> OBSERVATION
  -> THOUGHT
  -> ACTION (si aplica)
  -> repetir o CONCLUDE
  -> respuesta final
  -> persistencia del intercambio en conversation_context
```

## Flujo de monitoreo

```text
api.GET /dashboard
  -> dashboard.get_dashboard_html()
  -> template `src/api/templates/dashboard.html`
  -> static `/static/dashboard.css` y `/static/dashboard.js`
  -> navegador consume endpoints de monitoreo

api.GET /sessions
  -> mysql_manager.list_agent_sessions()

api.GET /sessions/{session_id}/context
  -> mysql_manager.get_conversation_context()

api.GET /tools/executions
  -> mysql_manager.list_tool_executions()

api.GET /api/access-log
  -> mysql_manager.list_api_access_log()

api.GET /system/metrics
  -> braincore_manager.get_vector_status()
  -> braincore_vector_store.get_status()

api.GET /system/readiness
  -> checks locales de seguridad runtime
  -> status ready/warning/not_ready
```

## Flujo de seguridad API

```text
Request operativo
  -> middleware FastAPI
  -> valida Content-Length contra ACU_API_MAX_REQUEST_BODY_BYTES si esta activo
  -> aplica rate limiting en memoria si ACU_API_RATE_LIMIT_REQUESTS > 0
  -> si ACU_API_KEY y ACU_API_KEYS estan vacios: permite modo local
  -> si hay claves configuradas: valida X-ACU-API-Key o Authorization Bearer
  -> resuelve roles de la clave
  -> valida rol requerido por endpoint
  -> endpoint
  -> registra auditoria en api_access_log
```

Claves gestionadas:

```text
api.POST /api/keys
  -> genera secreto aleatorio
  -> valida roles y expires_at
  -> guarda hash + fingerprint + roles en api_keys
  -> devuelve el secreto solo una vez

api.POST /api/keys/{key_id}/revoke
  -> marca status='revoked'
```

Rutas publicas:

- `GET /health`
- `GET /dashboard`
- OpenAPI/docs

Roles:

- `admin`: acceso total
- `chat`: `POST /chat`
- `braincore_read`: `GET /braincore/decisions`, `GET /braincore/sources`, `GET /braincore/metrics`, `POST /braincore/search`
- `braincore_write`: `POST /braincore/decisions`, `POST /braincore/ingest`, `DELETE /braincore/sources/{source_id}` y lectura BrainCore
- `monitoring`: sesiones, contexto conversacional, auditoria de herramientas, auditoria API y metricas de sistema

Controles configurables:

- `ACU_API_CORS_ORIGINS`: activa CORS por allowlist cuando no esta vacio.
- `ACU_API_CORS_METHODS`: metodos permitidos por CORS.
- `ACU_API_CORS_HEADERS`: headers permitidos por CORS.
- `ACU_API_CORS_ALLOW_CREDENTIALS`: permite credenciales CORS cuando aplica.
- `ACU_API_MAX_REQUEST_BODY_BYTES`: rechaza requests con `Content-Length` superior al limite; `0` desactiva el control.
- `ACU_API_RATE_LIMIT_REQUESTS`: maximo de requests por identidad y ventana; `0` desactiva el control.
- `ACU_API_RATE_LIMIT_WINDOW_SECONDS`: ventana de rate limiting.

El rate limiter es en memoria y por proceso. Usa fingerprint de API key si se envia una clave; de lo contrario usa IP cliente.

`expires_at` de claves gestionadas acepta ISO 8601 o `YYYY-MM-DD HH:MM:SS`, debe ser futuro y se normaliza a UTC sin zona antes de persistir.

## Flujo de acceso a datos

### SQL

```text
tools_manager._execute_sql_read()
  -> mysql_manager.execute_read_query()
  -> valida SELECT
  -> ejecuta query
```

### Documentacion del proyecto

```text
tools_manager._buscar_documentos()
  -> indexa archivos .md, .txt y .sql del repo
  -> si VECTOR_SEARCH_ENABLED=true usa ChromaDB + embeddings
  -> si ChromaDB no esta disponible usa ranking textual
  -> devuelve snippets con metadata.source
```

### BrainCore como herramienta ReAct

```text
tools_manager._buscar_contexto_braincore()
  -> braincore_manager.search_context()
  -> ChromaDB o FAISS si esta habilitado
  -> fallback textual en brain_chunks
```

### Memoria evolutiva

```text
tools_manager._registrar_leccion()
  -> mysql_manager.register_lesson()
  -> INSERT en memoria_evolutiva

tools_manager._consultar_lecciones_aprendidas()
  -> mysql_manager.query_lessons()
  -> SELECT + ranking basico
  -> actualiza veces_utilizada cuando hay conexion de escritura
```

### BrainCore ADRs

```text
api.POST /braincore/decisions
  -> braincore_manager.register_decision()
  -> mysql_manager.register_brain_decision()
  -> INSERT brain_decisions

api.GET /braincore/decisions
  -> braincore_manager.list_decisions()
  -> mysql_manager.list_brain_decisions()

api.POST /braincore/ingest
  -> braincore_manager.ingest_path()
  -> braincore_ingestion.collect_documents()
  -> mysql_manager.upsert_brain_source()
  -> UPSERT brain_sources + replace brain_chunks

api.GET /braincore/sources
  -> braincore_manager.list_sources()
  -> mysql_manager.list_brain_sources()

api.GET /braincore/metrics
  -> braincore_manager.get_metrics()
  -> mysql_manager.get_brain_metrics()

api.GET /system/metrics
  -> braincore_manager.get_vector_status()
  -> braincore_vector_store.get_status()

api.GET /system/readiness
  -> valida auth, rate limit, payload, CORS, secretos, Redis, scheduler y contrato API

api.DELETE /braincore/sources/{source_id}
  -> braincore_manager.delete_source()
  -> mysql_manager.delete_brain_source()
  -> braincore_vector_store.delete_source() si esta disponible

api.POST /braincore/search
  -> braincore_manager.search_context()
  -> braincore_vector_store.search() si esta disponible
  -> mysql_manager.search_brain_chunks() como fallback textual
```

## Decisiones actuales

### Busqueda documental con fallback textual

Se mantiene una implementacion local y textual como respaldo deterministico, y se agregan ChromaDB y FAISS como backends vectoriales opcionales.

Ventajas:

- el agente funciona aunque el modelo de embeddings no este disponible
- el RAG semantico se puede activar por configuracion
- ChromaDB cubre colecciones persistentes administradas
- FAISS cubre indice local liviano con metadata JSON
- los resultados mantienen metadata de origen

Limitacion:

- el primer uso vectorial puede descargar/cargar el modelo de embeddings configurado
- FAISS requiere instalar `faiss-cpu` cuando se use `VECTOR_DB_ENGINE=faiss`

### Separacion read-only / read-write en MySQL

Las consultas SQL del agente siguen siendo de solo lectura, pero la memoria evolutiva usa un conector de escritura independiente.

Esto evita mezclar:

- lectura operacional sobre tablas del dominio
- escritura de memoria interna del agente

Los conectores MySQL operan con `autocommit=True` para que los lectores de monitoreo vean escrituras recientes de otros conectores sin quedar retenidos por snapshots transaccionales largos.

## Riesgos vigentes

- la busqueda vectorial depende de ChromaDB o FAISS y del modelo de embeddings local
- la calidad de la decision sigue dependiendo de la disciplina del prompt y del modelo local
- las claves gestionadas en BD requieren una estrategia de backup/migracion de `api_keys`
- si se usan claves gestionadas sin clave estatica, debe activarse `ACU_API_AUTH_REQUIRED=true`

## Proximos pasos

- automatizacion de pruebas de integracion MySQL en CI
- politicas de retencion para logs y sesiones
- validaciones adicionales de seguridad
- observabilidad avanzada para ejecucion multi-proceso
- mejoras UX del dashboard y posible evolucion a Jinja/frontend dedicado

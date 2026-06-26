# Fase 09.5 - Estabilizacion Funcional y Modularizacion Core

**Fecha de inicio**: 2026-05-19  
**Fecha de cierre**: 2026-05-19  
**Estado**: Cerrada funcionalmente  
**Objetivo**: convertir el baseline operativo de Fase 9 en una base mantenible, funcionalmente probada y preparada para evolucionar sin concentrar riesgo en modulos gigantes.

## Contexto

Fase 9 cerro bien la operacion runtime: `/system/metrics`, `/system/readiness`, Docker/CI, retencion, gobierno BrainCore y seguridad de exposicion. Sin embargo, el proyecto acumula riesgo estructural:

- `src/api/app.py` supera las 1.000 lineas y mezcla rutas, middlewares, RBAC, readiness, metricas, API keys, BrainCore, sesiones y HITL.
- `src/memory/mysql_manager.py` concentra conexion, schema, auditoria, sesiones, API keys, BrainCore, pruning y normalizacion de datos.
- La suite automatizada es amplia, pero los flujos funcionales completos deben reforzarse antes de sumar infraestructura nueva.

La decision profesional es abrir una fase intermedia antes de Fase 10. El objetivo no es reescribir, sino modularizar con pruebas de caracterizacion y mantener contratos verdes en cada corte.

## Principios

1. No cambiar comportamiento publico sin prueba de contrato.
2. Extraer responsabilidades pequenas, una por una.
3. Mantener fachadas compatibles mientras se mueven implementaciones.
4. Priorizar pruebas funcionales de journeys reales sobre mas documentacion declarativa.
5. No iniciar Prometheus/Grafana hasta reducir riesgo de mantenimiento en API y persistencia.

## Alcance

### API

- Extraer readiness a `src/api/readiness.py`.
- Extraer seguridad API y RBAC a un modulo dedicado.
- Separar rutas por dominio funcional:
  - system
  - chat
  - braincore
  - sessions
  - tools
  - api_keys
- Mantener `create_app()` como punto de ensamblaje.

### Persistencia

- Mantener `MySQLConnector` como fachada publica.
- Extraer repositorios internos por responsabilidad:
  - api_keys
  - audit
  - sessions
  - braincore
  - maintenance
- Agregar pruebas de caracterizacion antes de mover cada grupo.

### Pruebas Funcionales

Journeys minimos a cubrir con MySQL real o fakes de mayor fidelidad:

- Crear clave API, usarla y revocarla.
- Chat con persistencia de sesion/contexto.
- BrainCore ingest/search/export/delete por dominio.
- HITL approve/reject/resume.
- Scheduler retention.
- Readiness gate en modo seguro e inseguro.

## Cambios Implementados

### Corte 1 - Readiness

- Se extrae la construccion de readiness desde `src/api/app.py` a `src/api/readiness.py`.
- `GET /system/readiness` mantiene el mismo contrato publico.
- Se agregan pruebas unitarias directas para el modulo extraido:
  - runtime inseguro devuelve `not_ready`.
  - baseline seguro devuelve `ready`.
  - contrato API inestable bloquea readiness.

### Corte 2 - Seguridad API y RBAC

- Se extraen constantes, roles, rutas publicas, fingerprints, hashing, expiracion y RBAC desde `src/api/app.py` a `src/api/security.py`.
- `app.py` mantiene aliases compatibles para no romper imports existentes ni endpoints.
- Se agregan pruebas unitarias directas para:
  - merge de clave legacy `admin` con `ACU_API_KEYS`.
  - RBAC por endpoint y herencia `braincore_write -> braincore_read`.
  - extraccion de API key por header y bearer token.
  - hashing/fingerprint estable sin exponer secreto.
  - validacion de `expires_at`.
  - preferencia de claves estaticas sobre lookup gestionado.

### Corte 3 - Router System

- Se crea `src/api/routes/system.py`.
- Se mueven a ese router:
  - `GET /health`
  - `GET /api/version`
  - `GET /dashboard`
  - `GET /system/metrics`
  - `GET /system/readiness`
- `create_app()` mantiene el ensamblaje y registra el router sin cambiar contratos publicos.
- Se agregan pruebas unitarias del router y del resumen de herramientas pendientes.

### Corte 4 - Router Chat

- Se crea `src/api/agent_runtime.py` para compartir la inicializacion del agente entre rutas y HITL resume.
- Se crea `src/api/routes/chat.py`.
- Se mueven a ese router:
  - `POST /chat`
  - `POST /chat/stream`
- `POST /tools/pending/{tool_id}/resume` conserva el helper compartido de inicializacion.
- Se agregan pruebas unitarias para serializacion de tool calls y manejo de inicializacion del agente.

### Corte 5 - Journeys Funcionales

- Se crea la matriz [Journeys Funcionales Criticos](../03-componentes/journeys-funcionales.md).
- Se agrega un journey funcional de API keys:
  - crear clave gestionada.
  - usarla en `/chat`.
  - revocarla.
  - confirmar rechazo posterior.
- Se agrega un journey funcional de BrainCore:
  - ingerir fuente.
  - buscar contexto.
  - exportar dominio con chunks.
  - eliminar dominio con confirmacion.
  - confirmar que fuentes y busqueda quedan vacias tras la eliminacion.
- Se agrega un journey funcional de HITL:
  - listar herramientas pendientes.
  - rechazar una herramienta pendiente.
  - bloquear reanudacion de una herramienta rechazada.
  - aprobar y ejecutar una herramienta pendiente.
  - reanudar la conversacion y validar metricas `rejected`/`resumed`.
- La matriz define politica de corte antes de modularizar persistencia.

### Corte 6 - Router BrainCore

- Se crea `src/api/routes/braincore.py`.
- Se mueven a ese router:
  - `GET /braincore/decisions`
  - `POST /braincore/decisions`
  - `GET /braincore/sources`
  - `DELETE /braincore/sources/{source_id}`
  - `GET /braincore/metrics`
  - `POST /braincore/ingest`
  - `POST /braincore/search`
  - `GET /braincore/domains/{domain}/export`
  - `DELETE /braincore/domains/{domain}`
- `create_app()` conserva el ensamblaje y registra el router sin cambiar contratos publicos.
- El corte queda protegido por el journey BrainCore completo.

### Corte 7 - Repositorio API Keys

- Se crea `src/memory/repositories/api_keys.py`.
- `MySQLConnector` conserva la fachada publica:
  - `create_api_key`
  - `find_active_api_key`
  - `list_api_keys`
  - `revoke_api_key`
- La implementacion SQL y normalizacion de claves gestionadas queda aislada en `ApiKeyRepository`.
- Se agregan pruebas contractuales directas del repositorio para create, read-only, find active, list y revoke.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 8 - Repositorio Auditoria

- Se crea `src/memory/repositories/audit.py`.
- `MySQLConnector` conserva la fachada publica:
  - `log_tool_execution`
  - `log_api_access`
  - `list_tool_executions`
  - `list_api_access_log`
  - `prune_tool_execution_log`
  - `prune_api_access_log`
- La implementacion SQL y normalizacion de auditoria queda aislada en `AuditRepository`.
- Se agregan pruebas contractuales directas del repositorio para escritura, lectura, normalizacion JSON/roles y pruning.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 9 - Repositorio Sesiones

- Se crea `src/memory/repositories/sessions.py`.
- `MySQLConnector` conserva la fachada publica:
  - `start_agent_session`
  - `end_agent_session`
  - `log_conversation_context`
  - `list_agent_sessions`
  - `get_conversation_context`
  - `prune_conversation_context`
  - `prune_agent_sessions`
- La implementacion SQL de sesiones, contexto conversacional y pruning asociado queda aislada en `SessionsRepository`.
- Se agregan pruebas contractuales directas del repositorio para escritura, lectura, limites y pruning.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 10 - Repositorio BrainCore Decisiones

- Se crea `src/memory/repositories/brain_decisions.py`.
- `MySQLConnector` conserva la fachada publica:
  - `register_brain_decision`
  - `list_brain_decisions`
- La implementacion SQL de decisiones ADR y normalizacion de `alternatives`/`tags` queda aislada en `BrainDecisionRepository`.
- Se agregan pruebas contractuales directas del repositorio para register, validaciones, list con filtros y errores de conexion.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 11 - Repositorio BrainCore Fuentes

- Se crea `src/memory/repositories/brain_sources.py`.
- `MySQLConnector` conserva la fachada publica:
  - `upsert_brain_source`
  - `list_brain_sources`
  - `delete_brain_source`
- La implementacion SQL de fuentes y chunks queda aislada en `BrainSourceRepository`.
- Se agregan pruebas contractuales directas del repositorio para upsert, validaciones, list con filtros, delete y errores de conexion.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 12 - Repositorio BrainCore Metricas

- Se crea `src/memory/repositories/brain_metrics.py`.
- `MySQLConnector` conserva la fachada publica:
  - `get_brain_metrics`
- La implementacion SQL de metricas agregadas queda aislada en `BrainMetricsRepository`.
- Se agregan pruebas contractuales directas del repositorio para agregados, normalizacion de totales vacios y errores de conexion.
- La prueba existente de `MySQLConnector` sigue validando compatibilidad de fachada.

### Corte 13 - Repositorio BrainCore Busqueda

- Se crea `src/memory/repositories/brain_search.py`.
- `MySQLConnector` conserva la fachada publica:
  - `search_brain_chunks`
- La implementacion SQL, ranking lexical, snippets y normalizacion de metadata queda aislada en `BrainSearchRepository`.
- Se agregan pruebas contractuales directas del repositorio para ranking, filtros, query vacia, limite de candidatos y errores de conexion.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 14 - Repositorio BrainCore Dominios

- Se crea `src/memory/repositories/brain_domains.py`.
- `MySQLConnector` conserva la fachada publica:
  - `export_brain_domain`
  - `delete_brain_domain`
- La implementacion SQL de snapshots por dominio, borrado de fuentes/chunks y borrado opcional de decisiones queda aislada en `BrainDomainRepository`.
- Se agregan pruebas contractuales directas del repositorio para export con/sin chunks, delete con decisiones, dominio vacio, read-only y errores de conexion.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 15 - Repositorio Memoria Evolutiva

- Se crea `src/memory/repositories/lessons.py`.
- `MySQLConnector` conserva la fachada publica:
  - `register_lesson`
  - `query_lessons`
  - `increment_lesson_usage`
- La implementacion SQL, normalizacion de terminos y ranking de lecciones queda aislada en `LessonsRepository`.
- Se agregan pruebas contractuales directas del repositorio para registro, busqueda/ranking, query vacia, incremento de uso, read-only y errores de conexion.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 16 - Repositorio SQL Runtime

- Se crea `src/memory/repositories/sql_runtime.py`.
- `MySQLConnector` conserva la fachada publica:
  - `get_database_schema`
  - `execute_read_query`
  - `format_schema_for_prompt`
- La extraccion desde `information_schema`, la validacion de queries `SELECT`, la normalizacion de errores SQL y el formateo de schema para prompt quedan aislados en `SqlRuntimeRepository`.
- Se agregan pruebas contractuales directas del repositorio para schema/cache, conexion ausente, rechazo de operaciones no `SELECT`, ejecucion exitosa, errores MySQL y formateo de prompt.
- Las pruebas existentes de `MySQLConnector` siguen validando compatibilidad de fachada.

### Corte 17 - Router Monitoring

- Se crea `src/api/routes/monitoring.py`.
- Se mueven a ese router:
  - `GET /sessions`
  - `GET /sessions/{session_id}/context`
  - `GET /tools/executions`
  - `GET /api/access-log`
- `create_app()` conserva el ensamblaje y registra el router sin cambiar contratos publicos.
- Se agregan pruebas directas para filtros de sesiones, contexto, auditoria de herramientas, auditoria API y errores de repositorio.
- Las pruebas existentes de `create_app()` siguen validando compatibilidad end-to-end de los endpoints.

### Corte 18 - Router API Keys

- Se crea `src/api/routes/api_keys.py`.
- Se mueven a ese router:
  - `POST /api/keys`
  - `GET /api/keys`
  - `POST /api/keys/{key_id}/revoke`
- `create_app()` conserva el ensamblaje, providers y middleware de autorizacion sin cambiar contratos publicos.
- Se agregan pruebas directas para creacion con secreto de un solo uso, rechazo de roles invalidos, listado con filtros y revocacion/404.
- Las pruebas existentes de administracion y journey funcional de API keys siguen validando compatibilidad end-to-end.

### Corte 19 - Router Tools/HITL

- Se crea `src/api/routes/tools.py`.
- Se mueven a ese router:
  - `GET /tools/pending`
  - `POST /tools/pending/{tool_id}/approve`
  - `POST /tools/pending/{tool_id}/reject`
  - `POST /tools/pending/{tool_id}/resume`
- `create_app()` conserva el ensamblaje, RBAC y auditoria API sin cambiar contratos publicos.
- Se agregan pruebas directas para listado/rechazo, aprobacion con ejecucion, bloqueo de resume prematuro y reanudacion exitosa.
- El journey funcional HITL existente sigue validando rechazo, aprobacion, ejecucion, reanudacion y metricas.

## Validacion

Comandos vigentes:

```bash
python -m ruff format --check src tests scripts main.py
python -m ruff check src tests scripts main.py
python -m mypy src scripts main.py --ignore-missing-imports
python -m pytest
```

Resultado vigente:

```text
241 passed, 4 skipped
```

Validacion MySQL real opt-in:

```powershell
$env:MYSQL_HOST_PORT='3307'
docker compose -f docker/docker-compose.yml up -d mysql
$env:ACU_RUN_MYSQL_INTEGRATION='true'
$env:ACU_TEST_MYSQL_HOST='127.0.0.1'
$env:ACU_TEST_MYSQL_PORT='3307'
$env:ACU_TEST_MYSQL_DATABASE='acu_db'
$env:ACU_TEST_MYSQL_USER='root'
$env:ACU_TEST_MYSQL_PASSWORD='root'
$env:ACU_TEST_MYSQL_READ_ONLY_USER='acu_reader'
$env:ACU_TEST_MYSQL_READ_ONLY_PASSWORD='acu_secure_read_only'
python -m pytest -m integration_mysql -q
```

Resultado vigente:

```text
3 passed
```

Diagnostico:

- La compuerta opt-in funciona: las pruebas dejaron de estar en `skipped`.
- `localhost:3306` estaba ocupado por otra instancia MySQL local con credenciales distintas.
- El MySQL del compose se levanto correctamente usando `MYSQL_HOST_PORT=3307`.
- Las credenciales del compose (`root/root`, `acu_reader/acu_secure_read_only`) validan schema, BrainCore, auditoria, sesiones y API keys contra MySQL real.

## Cierre De Fase

Fase 09.5 se considera cerrada funcionalmente el 2026-05-19.

### Resumen Ejecutivo Del Sistema

ACU queda cerrado en este punto como un core agentico operativo y modularizado, con API FastAPI, persistencia MySQL, Redis opcional, BrainCore, HITL, seguridad por roles, dashboard y suite automatizada verde.

El sistema opera como un agente ReAct expuesto por API REST. Recibe una consulta por `/chat`, construye contexto con schema MySQL, historial conversacional, memoria evolutiva y BrainCore, decide si debe usar herramientas y devuelve una respuesta estructurada. El ciclo cognitivo se apoya en `src/agent/agent_loop.py`, `src/llm/ollama_client.py`, `src/tools/tools_manager.py`, `src/memory/mysql_manager.py` y `src/braincore/manager.py`.

La API quedo separada por dominios funcionales:

- `src/api/routes/system.py`: salud, version, dashboard, metricas y readiness.
- `src/api/routes/chat.py`: chat sincronico y stream.
- `src/api/routes/braincore.py`: decisiones, fuentes, ingesta, busqueda, metricas y gobierno por dominio.
- `src/api/routes/monitoring.py`: sesiones, contexto conversacional y auditoria.
- `src/api/routes/api_keys.py`: creacion, listado y revocacion de API keys gestionadas.
- `src/api/routes/tools.py`: flujo HITL para aprobar, rechazar, ejecutar y reanudar herramientas pendientes.
- `src/api/webhooks.py`: canales externos Telegram/Slack con hardening opt-in.

La persistencia quedo organizada con `MySQLConnector` como fachada publica compatible y repositorios internos por responsabilidad. Esto separa API keys, auditoria, sesiones, BrainCore, memoria evolutiva y runtime SQL sin romper los contratos usados por agente, API y BrainCore.

BrainCore queda funcional como memoria tecnica transversal del proyecto: registra decisiones, ingiere fuentes locales, genera chunks, persiste fuentes/chunks en MySQL, busca contexto por ranking textual, soporta vector store opcional con ChromaDB o FAISS y permite exportar/eliminar dominios de conocimiento de forma controlada.

La seguridad operativa queda cubierta con API keys estaticas y gestionadas, hash/fingerprint sin exponer secretos, roles `admin`, `chat`, `braincore_read`, `braincore_write` y `monitoring`, RBAC por endpoint, rate limiting configurable, limite de payload, CORS por allowlist, auditoria de accesos API, auditoria de herramientas, readiness operativo y metricas runtime.

La generacion y evolucion de codigo se realizo mediante cortes pequenos, pruebas de caracterizacion, preservacion de fachadas publicas y validacion continua. El resultado no es solo una mejora estetica del codigo: queda una base funcional verificable, con suite local verde e integracion MySQL real validada.

Conclusion profesional: ACU queda en un estado sano para continuar. La siguiente etapa no debe priorizar mas refactor estructural por defecto, sino validacion end-to-end ampliada con API, MySQL, Redis, Docker completo, dashboard y journeys reales, o avanzar hacia Fase 10 con observabilidad historica opt-in.

### Criterios Cumplidos

| Criterio | Evidencia | Estado |
|----------|-----------|--------|
| Reduccion de riesgo en `app.py` | `app.py` queda en 412 lineas y sin rutas funcionales grandes embebidas | Cumplido |
| Reduccion de riesgo en `mysql_manager.py` | `mysql_manager.py` queda en 465 lineas y delega persistencia en repositorios | Cumplido |
| Compatibilidad publica | Fachadas y endpoints existentes conservan contratos; tests end-to-end siguen verdes | Cumplido |
| Modularizacion API | Routers `system`, `chat`, `braincore`, `monitoring`, `api_keys` y `tools` registrados | Cumplido |
| Modularizacion persistencia | Repositorios `api_keys`, `audit`, `sessions`, `brain_*`, `lessons` y `sql_runtime` extraidos | Cumplido |
| Journeys funcionales | API keys, BrainCore y HITL cubiertos por pruebas funcionales | Cumplido |
| MySQL real | `pytest -m integration_mysql -q` contra MySQL Docker en `localhost:3307` | Cumplido |
| Calidad estatica | `ruff format --check`, `ruff check`, `mypy` verdes | Cumplido |
| Suite automatizada | `241 passed, 4 skipped` | Cumplido |

### Estado De Modulos Al Cierre

| Modulo | Lineas | Estado |
|--------|--------|--------|
| `src/api/app.py` | 412 | Ensamblador FastAPI, middlewares, providers, OpenAPI y helpers transversales |
| `src/memory/mysql_manager.py` | 465 | Fachada MySQL y conexion; persistencia delegada |
| `src/api/routes/*.py` | 88-199 por router | Rutas separadas por dominio funcional |
| `src/memory/repositories/*.py` | 124-338 por repositorio | Persistencia separada por responsabilidad |

### Decisiones De Cierre

- No se recomienda seguir refactorizando `app.py` por tamano en esta fase; el modulo ya queda bajo control y con responsabilidades transversales claras.
- No se recomienda eliminar `MySQLConnector` como fachada publica todavia; mantiene compatibilidad y reduce riesgo de cambio para agente, API y BrainCore.
- La siguiente fase debe priorizar validacion funcional end-to-end, operacion real y observabilidad historica opt-in, no mas modularizacion estructural de bajo retorno.

## Pendientes Para La Siguiente Fase

1. Ejecutar journeys end-to-end con API + MySQL + Redis + Docker completo, no solo MySQL opt-in.
2. Evaluar pruebas smoke del dashboard contra API real.
3. Mantener `MySQLConnector` como fachada hasta que exista una estrategia formal para migrar contratos internos.
4. Retomar Fase 10 para observabilidad historica y alertas, manteniendo Prometheus/Grafana como opt-in.

# Changelog

Registro cronologico de cambios del proyecto ACU.

**Ultima actualizacion**: 2026-05-19  
**Estado actual**: Fase 9.5 cerrada funcionalmente; Fase 10 propuesta  

## [1.5.1] - 2026-05-19

### Fase 9.5: Estabilizacion Funcional y Modularizacion Core

Fase enfocada en reducir riesgo de mantenimiento antes de sumar nuevas capacidades.

#### Modularizacion API

- Se abre la fase intermedia Fase 9.5.
- Se extrae readiness desde `src/api/app.py` hacia `src/api/readiness.py`.
- `GET /system/readiness` conserva contrato publico y delega en el modulo dedicado.
- Se agregan pruebas unitarias directas para readiness: runtime inseguro, baseline seguro y contrato API inestable.
- Se extrae seguridad API/RBAC desde `src/api/app.py` hacia `src/api/security.py`.
- Se agregan pruebas unitarias directas para roles, API keys, fingerprints, expiracion y resolucion de identidad.
- Se crea `src/api/routes/system.py` para health, version, dashboard, metricas y readiness.
- Se agregan pruebas unitarias para el router system y resumen de pendientes HITL.
- Se crea `src/api/agent_runtime.py` para inicializacion compartida del agente.
- Se crea `src/api/routes/chat.py` para `/chat` y `/chat/stream`.
- Se agregan pruebas unitarias para serializacion de tool calls e inicializacion del agente.
- Se crea matriz de journeys funcionales criticos.
- Se agrega journey API keys: crear, usar en `/chat`, revocar y rechazar uso posterior.
- Se agrega journey BrainCore: ingerir, buscar, exportar, eliminar dominio y verificar estado posterior.
- Se agrega journey HITL: listar pendientes, rechazar, aprobar/ejecutar, reanudar conversacion y validar metricas.
- Se crea `src/api/routes/braincore.py` para aislar decisiones, fuentes, ingesta, busqueda, export y delete por dominio.
- Se crea `src/api/routes/monitoring.py` para aislar sesiones, contexto conversacional y auditoria.
- Se crea `src/api/routes/api_keys.py` para aislar creacion, listado y revocacion de API keys gestionadas.
- Se crea `src/api/routes/tools.py` para aislar el flujo HITL de herramientas pendientes.
- Se crea `src/memory/repositories/api_keys.py` y `MySQLConnector` delega API keys gestionadas manteniendo compatibilidad publica.
- Se crea `src/memory/repositories/audit.py` y `MySQLConnector` delega auditoria de herramientas/accesos y pruning asociado.
- Se crea `src/memory/repositories/sessions.py` y `MySQLConnector` delega sesiones, contexto conversacional y pruning asociado.
- Se crea `src/memory/repositories/brain_decisions.py` y `MySQLConnector` delega decisiones ADR BrainCore.
- Se crea `src/memory/repositories/brain_sources.py` y `MySQLConnector` delega fuentes/chunks BrainCore.
- Se crea `src/memory/repositories/brain_metrics.py` y `MySQLConnector` delega metricas agregadas BrainCore.
- Se crea `src/memory/repositories/brain_search.py` y `MySQLConnector` delega busqueda lexical BrainCore.
- Se crea `src/memory/repositories/brain_domains.py` y `MySQLConnector` delega export/delete por dominio BrainCore.
- Se crea `src/memory/repositories/lessons.py` y `MySQLConnector` delega memoria evolutiva.
- Se crea `src/memory/repositories/sql_runtime.py` y `MySQLConnector` delega schema dinamico, queries SELECT y formateo de prompt.
- Se documenta el plan de modularizacion progresiva de API y persistencia.
- Se cierra Fase 9.5 funcionalmente con `app.py` en 412 lineas y `mysql_manager.py` en 465 lineas.
- Baseline verde: `ruff`, `mypy`, `241 passed, 4 skipped`.
- Integracion MySQL real opt-in validada: `3 passed` contra MySQL Docker en `localhost:3307`.

## [1.5.0] - 2026-05-18

### Fase 9: Operacion y Observabilidad

Fase enfocada en hacer visible el estado runtime de los flujos criticos para facilitar operacion, soporte y despliegue.

#### Observabilidad API

- `GET /system/metrics` ahora reporta metricas agregadas de herramientas HITL.
- Se agregan contadores por estado: `pending`, `approved`, `executed`, `failed`, `rejected` y `resumed`.
- Se expone estado runtime de scheduler: modo, validez, ejecucion, cantidad de jobs e IDs.
- Se expone estado runtime de Redis: habilitado, conectado y backend efectivo.
- Se agregan metricas de webhooks por canal: recibidos, aceptados, rechazados, ignorados, procesados y fallidos.
- Las metricas webhook se consolidan en Redis cuando esta disponible y conservan fallback local por proceso.
- Se agrega `GET /api/version` para publicar contrato funcional `v1`.
- Se agrega `GET /system/readiness` para validar exposicion operativa antes de publicar ambientes.
- Se agrega `scripts/readiness_gate.py` y se integra al smoke test Docker/CI.
- Se agrega `GET /braincore/domains/{domain}/export` para snapshots por dominio.
- Se agrega `DELETE /braincore/domains/{domain}` con confirmacion exacta y limpieza de vector store.
- Todas las respuestas incluyen headers `X-ACU-API-Version` y `X-ACU-API-Stability`.
- OpenAPI publica `x-acu-api-version`, `x-acu-api-stability` y politica de breaking changes.

#### Dashboard

- Tarjeta HITL en el resumen superior.
- Tarjeta Scheduler en el resumen superior.
- Tarjeta Webhooks en el resumen superior.
- Dashboard consume las nuevas metricas operativas desde `/system/metrics`.
- Tabla HITL muestra estados vivos, resultado/error de ejecucion y accion de reanudacion cuando aplica.
- Chat registra eventos de rechazo y reanudacion HITL como mensajes de sistema.

#### Docker y Despliegue

- Dockerfile arranca FastAPI con Uvicorn por defecto y conserva modo CLI como override manual.
- Healthcheck de imagen ACU valida `GET /health`.
- Compose local expone `8000:8000` para API/dashboard.
- Compose local, compose prod y stack Swarm agregan healthchecks para API, scheduler, MySQL, Redis, Ollama y Jaeger.
- `acu-agent` local espera Redis saludable antes de arrancar.
- `.dockerignore` excluye caches, datos locales, logs, tests y wiki del contexto de build.
- OpenTelemetry queda fijado a versiones compatibles con `mysql-connector-python` en el perfil `observability`.
- CI agrega job `docker-validation` con `docker compose config`, `docker build`, smoke test de `/health` y gate de `/system/readiness`.
- Publicacion GHCR usa tags `ghcr.io/${{ github.repository }}:latest` y `:${{ github.sha }}`.
- Publicacion GHCR agrega tags semanticos al empujar `vX.Y.Z`: `X.Y.Z`, `X.Y`, `X` y `sha-<commit>`.
- Compose prod y stack aceptan `ACU_IMAGE` para fijar una version exacta en `acu-agent` y `acu-scheduler`.
- Compose local/prod/stack propagan `ACU_AUDIT_RETENTION_DAYS` y `ACU_CONVERSATION_RETENTION_DAYS` al scheduler.

#### Documentacion Operativa

- Se agrega contrato tecnico de `GET /system/metrics` con ejemplo request/response.
- Se documentan campos, umbrales operativos y runbook para scheduler, Redis, HITL y webhooks.
- Se agrega runbook de seguridad operativa con matriz de roles, baseline de produccion, secretos, rate limiting, auditoria y checklist de release.
- Se explicita que la cola HITL y sus acciones quedan reservadas a rol `admin`.
- Se agrega runbook de versionado de imagenes con flujo de release y rollback.
- Se agrega runbook de retencion de auditoria y contexto con criterios por tabla.
- Se agrega runbook de versionado de API y OpenAPI.
- Se agrega runbook de metricas runtime multi-replica.
- Se agrega runbook de gobierno BrainCore por dominio.
- Se aprueba el cierre formal de Fase 9.
- Se difiere Prometheus/Grafana a Fase 10 como observabilidad historica opt-in.

#### Validacion

- Pruebas de contrato API para las nuevas metricas.
- Pruebas de presencia de UI para tarjetas HITL y Scheduler.
- Pruebas de contadores webhook para aceptaciones y rechazos.
- Pruebas estaticas para contrato Docker.
- Pruebas de contrato para permisos HITL y documentacion de seguridad operativa.
- Pruebas unitarias para poda de contexto conversacional, sesiones finalizadas y scheduler de retencion.
- Pruebas de contrato para `/api/version` y metadata OpenAPI.
- Pruebas unitarias para metricas webhook compartidas en Redis y preferencia en `/system/metrics`.
- Pruebas de contrato para exportacion y limpieza controlada de dominios BrainCore.
- Validacion estatica de sintaxis JavaScript con `node --check`.
- Build local `acu-core:local-check` validado.
- Smoke test local de contenedor validado contra `/health`.
- Baseline verde: `ruff`, `mypy`, `157 passed, 4 skipped`.

## [1.4.0] - 2026-05-18

### Fase 8: Estabilizacion Profesional

Fase enfocada en convertir los avances recientes en un baseline profesional verificable antes de seguir agregando nuevas capacidades.

#### Calidad y Validacion

- `ruff check src tests scripts main.py` queda verde.
- `ruff format --check src tests scripts main.py` queda verde.
- `mypy src scripts main.py --ignore-missing-imports` queda verde.
- `pytest` queda verde con `122 passed, 4 skipped`.
- Registro del marker `integration_vector` en `pytest.ini`.

#### Correcciones de Contrato

- Correccion inicial de delegacion multi-agente para inicializar sub-agentes con `initialize(session_id=...)`.
- Manejo defensivo de respuestas vacias del juez LLM en `delegar_tarea`.
- Correccion de tipos en operaciones Redis `hset`/`hget`.
- Eliminacion de compuerta HITL duplicada en `agent_loop.py`; la decision queda centralizada en `ToolsManager`.
- Conversion de HITL a flujo no bloqueante con `pending_tool_id` y ejecucion posterior desde endpoint de aprobacion.
- Pruebas unitarias para cola HITL y ejecucion posterior a aprobacion.
- Hardening opt-in para webhooks Slack/Telegram con secretos, firmas, ventana anti-replay y allowlists.
- Pruebas unitarias de seguridad para webhooks.
- Scheduler configurable por contexto mediante `ACU_SCHEDULER_MODE`.
- Worker dedicado ejecutable con `python -m src.api.scheduler`.
- Servicios `acu-scheduler` agregados a compose local, produccion y stack.
- Pruebas unitarias de modos de scheduler.
- Pruebas unitarias de `delegar_tarea` para inicializacion, juez `PASS`, juez `FAIL` y autocorreccion.
- Reanudacion conversacional HITL mediante `POST /tools/pending/{tool_id}/resume`.
- Dashboard actualiza el chat con la respuesta final tras aprobar y ejecutar herramientas sensibles.
- Pruebas de reanudacion HITL a nivel agente y API.
- Perfiles de dependencias separados en `requirements/base.txt`, `dev.txt`, `vector.txt`, `vector-faiss.txt`, `observability.txt` y `all.txt`.
- CI separado en jobs de calidad/tests, MySQL real y VectorDB real.

#### Gobernanza

- Actualizacion de wiki principal, arquitectura, estructura, componentes, decisiones y bitacoras.
- Priorizacion formal de pendientes: estructura documental y jobs de integracion.

## [1.3.0] - 2026-05-18

### Fase 06: Orquestación Multi-Agente y Casos de Uso Empresariales

Fase enfocada en la creación de capacidades de investigación en internet, sub-agentes asíncronos y seguridad estricta para canales externos.

#### Real-Time Web Search
- Integración nativa de búsqueda web en internet usando `duckduckgo-search`.
- Construcción de un *Scraper* ligero capaz de procesar DOM web, limpiarlo y convertirlo a Markdown para consumo del modelo en la herramienta `leer_pagina_web`.

#### Multi-Agent Swarm & Stateful Workflows
- Implementación del patrón *ReAct Supervisor-Worker*, con la creación de la herramienta `delegar_tarea` en `tools_manager.py`.
- Incorporación de perfiles hiper-especializados (`Investigador Web`, `Soporte Técnico`, `Arquitecto`, etc.) en `prompting.py`.
- Desarrollo de un esquema de Memoria Compartida Stateful a través de Redis (`escribir_memoria_compartida`, `leer_memoria_compartida`) preservando historiales aislados.

#### Evaluaciones (LLM-as-a-Judge) y Seguridad
- Inyección de evaluaciones autónomas en la fase de delegación; los *Workers* son auditados rigurosamente por un modelo juez antes de entregar el resultado al *Supervisor*.
- Implementación de un middleware robusto de Guardrails (`guardrails.py`) para detección heurística de Prompt Injection y enmascaramiento activo de PII (ej. tarjetas de crédito).

#### Integración y Webhooks (Omnicanalidad)
- Desacople del Dashboard mediante la creación de un motor asíncrono en FastAPI (`webhooks.py`) capaz de ingerir peticiones externas y despachar el agente en *background*.
- Mock-ups operativos para integración de bots en **Telegram** y **Slack** usando IDs de usuario como llaves de sesión en el Swarm.

## [1.2.0] - 2026-05-17

### Fase 05: Hardening y Observabilidad

Fase enfocada en garantizar grado de produccion mediante integracion continua, tipos estrictos, escalabilidad asincrona, UI reactiva en tiempo real y human-in-the-loop.

#### Estabilidad y Tipado Mypy
- Se auditaron todos los componentes con `mypy --strict`.
- Eliminacion de 77 errores de tipado, logrando Type-Safety al 100%.
- Refactorizacion de `mysql_manager.py` (casteo a strings) para sort key seguro.
- Refactorizacion de `agent_loop.py` garantizando null-safety en `observation`.

#### Escalabilidad Asincrona y Redis
- Soporte total asincrono para la API usando `FastAPI`.
- Migracion de decoradores `@on_event("startup")` hacia el estandar `@asynccontextmanager (lifespan)`.
- Eliminacion de "DeprecationWarnings" de `Pydantic V2` (`model_dump` en vez de `dict`).
- Implementacion de `redis_manager.py` para Rate Limiting distribuido y persistencia temporal.

#### Observabilidad y UI ReAct en Tiempo Real
- Refactorizacion visual del dashboard separando JS y CSS.
- El endpoint `/chat/stream` ahora expone en tiempo real las fases cognitivas del agente (SSE).
- Renderizado tipo terminal monoespaciado para pensamientos (`THOUGHT`) de ACU.
- Renderizado y animaciones CSS reactivas (`pulsePending`) para herramientas (`ACTION`) en espera.

#### Consola Human-in-the-Loop
- Mecanismo de intercepcion de `SENSITIVE_TOOLS` en `tools_manager.py`.
- Nueva UI persistente que alerta al administrador de acciones criticas.
- Endpoints dedicados para aprovar (`/tools/pending/{id}/approve`) o rechazar acciones.
- Polling cada 3 segundos en el cliente para mantener consistencia.

#### CI/CD y Pruebas
- Suite en `tests/integration/` para testear flujos end-to-end.
- Prueba real `test_vectordb_integration.py` con `FAISS` aislada en directorios seguros.
- Archivo `.github/workflows/ci.yml` configurado para correr integracion (MySQL + Vector).
- Automatizacion de compilacion y publicacion (Build & Push) a Docker Registry (`ghcr.io`) en push a `main`.
- Creacion del orquestador `docker-compose.prod.yml` final, securizado para produccion.

## [1.1.0] - 2026-05-17

### Fase 2: Enhancement Operativo

Fase enfocada en convertir el core ReAct inicial en una plataforma operable mediante API REST, dashboard, BrainCore persistente, seguridad por roles y suite automatizada.

#### API y Dashboard

- FastAPI operativo en `src/api/app.py`.
- Endpoint `GET /health`.
- Endpoint `POST /chat` conectado al agente ACU.
- Endpoint `GET /dashboard` con dashboard operativo.
- Endpoint `GET /system/metrics` para estado runtime, seguridad y vector store.
- Dashboard operativo para chat, sesiones, auditoria, herramientas, BrainCore y API keys.
- Consola Chat ACU integrada en el dashboard.
- Paneles de BrainCore para decisiones, fuentes, metricas, ingesta, busqueda y eliminacion.
- Panel de API keys para listar, crear y revocar claves gestionadas.
- Modularizacion posterior del dashboard en `templates/dashboard.html`, `static/dashboard.css` y `static/dashboard.js`.
- Mensajes claros en dashboard para errores 401, 403, 413, 429 y 422.
- Historial de chat visible, tool calls expandibles y copia de clave API recien creada.
- Tarjetas de dashboard para vector store y politicas runtime.

#### BrainCore

- Registro y listado de decisiones arquitectonicas.
- Ingesta local de fuentes.
- Chunking de contenido.
- Persistencia de fuentes y chunks en MySQL.
- Busqueda contextual textual.
- Integracion vectorial opcional con ChromaDB/FAISS.
- Estado ligero de vector store sin cargar dependencias pesadas.
- Fallback textual MySQL cuando no hay vector store disponible.
- Inventario de fuentes indexadas.
- Filtros por `domain`, `source_type`, `status` y `limit`.
- Eliminacion de fuentes indexadas con limpieza de chunks y best-effort en vector store.
- Metricas agregadas de decisiones, fuentes, chunks, dominios, tipos y estados.

#### Seguridad y Auditoria

- API keys estaticas desde configuracion.
- API keys gestionadas por base de datos.
- Hash seguro y fingerprint de claves gestionadas.
- Validacion estricta de `expires_at` en claves gestionadas.
- Roles soportados: `admin`, `chat`, `braincore_read`, `braincore_write` y `monitoring`.
- Middleware de autorizacion por endpoint.
- CORS configurable por allowlist.
- Limite configurable de payload por request.
- Rate limiting configurable en memoria por API key o IP.
- Auditoria persistente de accesos API.
- Registro de ejecuciones de herramientas.

#### Persistencia

- Tablas funcionales para memoria evolutiva, sesiones, contexto, API logs, API keys, BrainCore y tool logs.
- Conector MySQL ampliado para operaciones BrainCore.
- Operaciones de lectura SQL del agente siguen restringidas a `SELECT`.
- Escrituras internas separadas para memoria, auditoria, sesiones, API keys y BrainCore.

#### Testing

- Suite automatizada con pytest.
- Cobertura de API REST, auth, roles y dashboard.
- Cobertura de BrainCore manager y vector store con fakes.
- Cobertura de MySQL manager con fakes.
- Cobertura de ToolsManager, AgentLoop, OllamaClient y startup integration.
- Estado validado: `105 passed, 3 skipped`.
- `python -m compileall src` validado.
- Pruebas reales MySQL opt-in validadas: `3 passed`.

#### Documentacion

- README, USAGE, ARCHITECTURE y PROJECT_STRUCTURE actualizados.
- Wiki reorganizada para reflejar Fase 2.
- Bitacora de Fase 2 creada.
- Estructura fisica, arquitectura core, componentes y decisiones alineadas con el estado real.

## [1.0.0-rc1] - 2024-04-23

### Fase 1: Foundation

Fase enfocada en construir el nucleo inicial del agente ACU con arquitectura modular, patron ReAct, Ollama, MySQL y herramientas base.

#### Core ReAct

- `ACUAgent` implementado en `src/agent/agent_loop.py`.
- Ciclo de observacion, pensamiento, accion y conclusion.
- Historial de conversacion en memoria del agente.
- Iteraciones configurables para ejecucion de herramientas.

#### LLM

- Cliente Ollama en `src/llm/ollama_client.py`.
- Health check contra Ollama.
- Generacion de respuestas.
- Parsing de tool calls JSON.
- Listado de modelos disponibles.

#### MySQL y Schema Dinamico

- Conector MySQL en `src/memory/mysql_manager.py`.
- Lectura de `information_schema`.
- Formateo de schema para prompts.
- Validacion de consultas read-only.
- Usuario recomendado `acu_reader`.

#### Herramientas Base

- `ejecutar_sql_lectura`.
- `buscar_documentos`.
- `registrar_leccion`.
- `consultar_lecciones_aprendidas`.

#### Configuracion y Soporte

- Configuracion centralizada en `src/config/settings.py`.
- Logging en `src/utils/logger.py`.
- Schemas internos en `src/utils/schemas.py`.
- Dockerfile, docker-compose e init SQL iniciales.

#### Documentacion Inicial

- README principal.
- ARCHITECTURE.
- USAGE.
- PROJECT_STRUCTURE.
- DELIVERY.
- Wiki inicial del proyecto.

## Roadmap De Versiones

| Version | Fecha | Fase | Estado |
|---------|-------|------|--------|
| `1.0.0-rc1` | 2024-04-23 | Fase 1 Foundation | Completada |
| `1.1.0` | 2026-05-17 | Fase 2 Enhancement | Completada operativamente |
| `1.2.0` | Por definir | Fase 3 Hardening | Recomendada |
| `2.0.0` | Por definir | Escalamiento mayor | Futuro |

## Fase 3 Recomendada

Los siguientes cambios quedan como foco natural despues de Fase 2:

1. Automatizar pruebas de integracion MySQL en CI.
2. Separar dependencias dev/vectoriales.
3. Mejorar UX del dashboard con estados visuales avanzados.
4. Completar hardening API: validaciones adicionales.
5. Evaluar evolucion del dashboard modularizado a Jinja o frontend dedicado.
6. Definir observabilidad avanzada para despliegues multi-proceso.

## Convenciones De Versionado

Formato recomendado:

```text
MAJOR.MINOR.PATCH[-PRERELEASE]
```

- `MAJOR`: cambios incompatibles o reescrituras arquitectonicas.
- `MINOR`: nuevas capacidades compatibles.
- `PATCH`: correcciones, mantenimiento y documentacion.
- `PRERELEASE`: versiones alpha, beta o release candidate.

## Documentos Relacionados

- [Fase 1 Foundation](fase-01-foundation.md)
- [Fase 2 Enhancement](fase-02-enhancement.md)
- [Plantilla de Fase](plantilla-fase.md)
- [Wiki Principal](../README.md)
- [README del proyecto](../../README.md)

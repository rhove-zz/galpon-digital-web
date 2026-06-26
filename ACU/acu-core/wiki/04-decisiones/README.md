# Decisiones Tecnicas - ADRs

Registro actualizado de decisiones arquitectonicas del proyecto ACU.

**Fecha de actualizacion**: 2026-05-19  
**Estado**: Baseline tecnico verde; Fase 9 cerrada operativamente  
**Verificacion**: `ruff check`, `ruff format --check`, `mypy src scripts main.py`, `241 passed, 4 skipped`

## Decisiones Vigentes

| # | Decision | Estado | Impacto | Resumen |
|---|----------|--------|---------|---------|
| 1 | Python puro sin LangChain | Implementada | Alto | Control total del ReAct loop y menor dependencia de frameworks de agentes |
| 2 | Schema dinamico MySQL | Implementada | Alto | Leer `information_schema` para operar sobre dominios distintos |
| 3 | SQL del agente read-only | Implementada | Alto | Separar consultas del agente de operaciones de escritura |
| 4 | Async-first | Implementada | Medio | Preparar el core para I/O concurrente |
| 5 | FastAPI como capa REST | Implementada | Alto | Exponer chat, BrainCore, seguridad y monitoreo |
| 6 | BrainCore como memoria transversal | Implementada | Alto | Persistir decisiones, fuentes, chunks y contexto reusable |
| 7 | ChromaDB y FAISS como backends vectoriales opcionales | Implementada | Medio | Mantener busqueda semantica local con fallback textual |
| 8 | API keys con roles | Implementada | Alto | Proteger endpoints operativos y separar permisos |
| 9 | Auditoria persistente | Implementada | Alto | Registrar accesos API, herramientas, sesiones y contexto |
| 10 | Dashboard operativo modularizado | Implementada | Medio | Operar ACU sin frontend separado, con HTML/CSS/JS separados en templates/static |
| 11 | Pytest como suite base | Implementada | Alto | Validar API, agente, BrainCore, MySQL fakes y dashboard |
| 12 | Hardening API configurable | Implementada parcial | Medio | CORS, limite de payload, rate limiting y validacion de expiracion de claves |
| 13 | Metricas de sistema runtime | Implementada | Medio | Exponer estado de seguridad, vector store, HITL, scheduler, Redis y webhooks |
| 14 | Redis para estado temporal | Implementada parcial | Medio | Historial temporal, memoria compartida y herramientas pendientes |
| 15 | Scheduler configurable por contexto | Implementada | Medio | Modo `disabled`, `api`, `worker` o `all`; worker dedicado recomendado |
| 16 | Webhooks externos | Implementada | Alto | Slack/Telegram con hardening opt-in por firma/secreto, replay window y allowlists |
| 17 | Seguridad operativa documentada | Implementada | Alto | Runbook de roles, secretos, rate limiting, auditoria y checklist de produccion |
| 18 | Versionado semantico de imagenes | Implementada | Alto | GHCR publica tags por SHA y SemVer; despliegue fija `ACU_IMAGE` |
| 19 | Retencion de auditoria y contexto | Implementada | Alto | Scheduler poda auditoria, contexto y sesiones finalizadas con variables dedicadas |
| 20 | Versionado funcional de API | Implementada | Alto | Contrato `v1` publicado en headers, `/api/version` y OpenAPI |
| 21 | Metricas runtime multi-replica | Implementada parcial | Medio | Webhooks se consolidan en Redis con fallback local |
| 22 | Gobierno BrainCore por dominio | Implementada | Alto | Exportacion y limpieza controlada de memoria curada por dominio |
| 23 | Readiness operativa | Implementada | Alto | Checklist runtime para bloquear exposicion con fallos criticos |
| 24 | Cierre formal de Fase 9 | Aprobada | Alto | Prometheus/Grafana se difiere a Fase 10 y Fase 9 queda cerrada |

## Detalle De Decisiones

### 1. Python puro sin LangChain

ACU mantiene un ReAct loop propio para tener control directo sobre prompts, tool calls, memoria, errores y auditoria.

Consecuencias:

- Menos abstraccion externa.
- Mayor transparencia.
- Mas responsabilidad local sobre orquestacion.

### 2. Schema dinamico MySQL

El agente extrae metadata desde `information_schema` para no depender de tablas hardcodeadas.

Consecuencias:

- Mejor portabilidad por dominio.
- Prompt mas ajustado al schema real.
- Requiere cache y manejo cuidadoso de permisos.

### 3. SQL read-only para el agente

Las consultas SQL expuestas al agente aceptan solo `SELECT`. Las escrituras internas usan conectores separados y rutas controladas.

Consecuencias:

- Reduce riesgo operativo.
- Permite auditoria clara.
- Las escrituras deben pasar por funciones explicitamente disenadas.

### 4. Async-first

El loop del agente y varias superficies operan en modo async para facilitar llamadas de red y herramientas.

Consecuencias:

- Mejor compatibilidad con FastAPI.
- Requiere tests async y cuidado con providers/singletons.

### 5. FastAPI como API REST

FastAPI se adopta como capa REST para `/chat`, BrainCore, monitoreo, seguridad y dashboard.

Consecuencias:

- OpenAPI disponible.
- Validacion Pydantic integrada.
- Facil de testear con `TestClient`.

### 6. BrainCore como memoria transversal

BrainCore organiza decisiones, fuentes, chunks y busqueda contextual para que el agente y operadores reutilicen conocimiento del proyecto.

Consecuencias:

- Base para RAG local.
- Permite operar memoria desde API y dashboard.
- Requiere inventario, metricas y limpieza de fuentes.

### 7. ChromaDB y FAISS opcionales

La busqueda semantica se habilita con `VECTOR_SEARCH_ENABLED=true`; si falla o no esta disponible, se usa fallback textual.

Consecuencias:

- Sistema util sin dependencias vectoriales obligatorias.
- FAISS permite persistencia local simple.
- ChromaDB permite colecciones persistentes.

### 8. API keys con roles

El sistema soporta claves estaticas y claves gestionadas en BD con roles.

Roles actuales:

- `admin`
- `chat`
- `braincore_read`
- `braincore_write`
- `monitoring`

Consecuencias:

- Separacion de permisos por superficie.
- Claves gestionadas pueden revocarse.
- El secreto se devuelve solo al crear la clave.

### 9. Auditoria persistente

ACU registra accesos API, ejecuciones de herramientas, sesiones y contexto conversacional.

Consecuencias:

- Mejor trazabilidad.
- Dashboard puede monitorear actividad reciente.
- Requiere politicas futuras de retencion/limpieza.

### 10. Dashboard modularizado

Durante Fase 2 se entrego el dashboard embebido para avanzar rapido sin crear frontend separado. En el arranque de Fase 3 se separo en template HTML y archivos estaticos bajo `src/api/templates` y `src/api/static`.

Consecuencias:

- Deployment simple.
- Test HTML, CSS y JS por separado.
- Mejor mantenibilidad sin introducir framework frontend.
- `src/api/dashboard.py` queda como loader cacheado del template.

### 11. Pytest como suite base

Pytest valida el core con fakes y tests unitarios/integracion ligera.

Consecuencias:

- Suite rapida y deterministica.
- Estado actual: `241 passed, 4 skipped`.
- Las pruebas reales con MySQL existen como opt-in y estan validadas: `3 passed` contra MySQL Docker en `localhost:3307`.

### 12. Hardening API configurable

La API permite activar CORS por allowlist, rechazar requests cuyo `Content-Length` supere `ACU_API_MAX_REQUEST_BODY_BYTES`, aplicar rate limiting en memoria por API key o IP y validar `expires_at` de claves gestionadas.

Consecuencias:

- El modo local no cambia si las variables quedan vacias o en `0`.
- Clientes web externos pueden habilitarse explicitamente con `ACU_API_CORS_ORIGINS`.
- Payloads excesivos pueden rechazarse antes de inicializar agente o providers.
- El rate limiter no requiere dependencias externas y queda desactivado con `ACU_API_RATE_LIMIT_REQUESTS=0`.
- Las claves gestionadas no aceptan expiraciones invalidas o vencidas.

### 13. Metricas de sistema runtime

La API expone `GET /system/metrics` para reportar servicio, version, politicas runtime activas, estado ligero del vector store, HITL, scheduler, Redis y webhooks.

Consecuencias:

- El dashboard puede mostrar estado de seguridad, vector store, HITL, scheduler, Redis y webhooks sin depender de infraestructura externa de metricas.
- El endpoint queda bajo rol `monitoring`.
- La observabilidad base no depende de infraestructura externa.
- El contrato y sus umbrales se documentan en [Observabilidad - Contrato `/system/metrics`](../03-componentes/observabilidad-system-metrics.md).

### 17. Seguridad operativa documentada

ACU fija un runbook de operacion para roles, secretos, webhooks, rate limiting, payload limits y auditoria.

Consecuencias:

- Produccion debe activar `ACU_API_AUTH_REQUIRED=True`.
- HITL queda reservado a rol `admin`.
- Webhooks expuestos requieren secretos del proveedor y allowlists.
- El checklist de release queda documentado en [Seguridad Operativa](seguridad-operativa.md).

### 23. Readiness operativa

La API expone `GET /system/readiness` para validar controles criticos antes de publicar una instancia.

Consecuencias:

- El endpoint queda bajo rol `monitoring`.
- El estado `not_ready` bloquea exposicion cuando faltan autenticacion, rate limit, limite de payload, CORS restringido, scheduler mode valido o contrato API estable.
- Los secretos webhook y Redis compartido se reportan como advertencias cuando no aplican o faltan.
- El contrato queda documentado en [Readiness Operativa](../03-componentes/readiness-operativa.md).

### 24. Cierre formal de Fase 9

Fase 9 queda cerrada operativamente con observabilidad runtime, readiness, seguridad, Docker/CI, retencion y gobierno BrainCore.

Consecuencias:

- Prometheus/Grafana no entra en Fase 9.
- La observabilidad historica pasa a [Fase 10 - Observabilidad Historica y Alertas](../02-bitacoras/fase-10-observabilidad-historica.md).
- El cierre queda documentado en [Cierre Formal De Fase 9](cierre-fase-09.md).

### 18. Versionado semantico de imagenes

El pipeline publica imagenes GHCR con tags `latest`, `sha-<commit>` y SemVer al empujar tags Git `vX.Y.Z`.

Consecuencias:

- Produccion puede fijar `ACU_IMAGE=ghcr.io/revoxetech/acu-core:X.Y.Z`.
- `acu-agent` y `acu-scheduler` comparten la misma imagen por variable.
- `latest` queda como fallback de compatibilidad, no como pin recomendado.
- La politica se documenta en [Versionado De Imagenes](versionado-imagenes.md).

### 19. Retencion de auditoria y contexto

El scheduler ejecuta poda diaria de auditoria tecnica, accesos API, contexto conversacional y sesiones finalizadas.

Consecuencias:

- `ACU_AUDIT_RETENTION_DAYS` controla `tool_execution_log` y `api_access_log`.
- `ACU_CONVERSATION_RETENTION_DAYS` controla `conversation_context` y `agent_sessions` finalizadas.
- BrainCore no se poda automaticamente porque es memoria curada.
- La politica se documenta en [Retencion De Auditoria Y Contexto](retencion-auditoria-contexto.md).

### 20. Versionado funcional de API

La superficie REST actual queda fijada como contrato `v1` y se publica en headers, endpoint de version y metadata OpenAPI.

Consecuencias:

- Cada respuesta incluye `X-ACU-API-Version` y `X-ACU-API-Stability`.
- `GET /api/version` permite a clientes validar compatibilidad.
- `/openapi.json` incluye metadata `x-acu-api-version`, `x-acu-api-stability` y politica de breaking changes.
- La politica se documenta en [Versionado De API Y OpenAPI](versionado-api-openapi.md).

### 21. Metricas runtime multi-replica

Las metricas webhook se escriben en Redis cuando esta disponible y `/system/metrics` prefiere ese agregado compartido.

Consecuencias:

- Despliegues con varias replicas API pueden ver contadores webhook agregados.
- El fallback local sigue funcionando para desarrollo sin Redis.
- Prometheus/Grafana queda como evolucion para historicos largos y alertas.
- La politica se documenta en [Metricas Runtime Multi-Replica](metricas-multireplica.md).

### 22. Gobierno BrainCore por dominio

BrainCore se gobierna por dominio: primero exportacion, luego limpieza controlada de fuentes y chunks con confirmacion explicita.

Consecuencias:

- `GET /braincore/domains/{domain}/export` permite respaldar conocimiento por dominio.
- `DELETE /braincore/domains/{domain}` exige `confirm={domain}`.
- Las decisiones se conservan salvo `delete_decisions=true`.
- La politica se documenta en [Gobierno BrainCore Por Dominio](gobierno-braincore.md).

## Decisiones Intercambiables

Estas decisiones pueden revisarse sin reescribir todo el sistema:

- Backend vectorial por defecto: ChromaDB vs FAISS.
- Frontend dedicado vs dashboard static vanilla.
- Estrategia de metricas y observabilidad.
- Separacion de dependencias en archivos por perfil.

## Decisiones No Recomendadas Sin Redisenio

- Eliminar SQL read-only para el agente.
- Acoplar el core a un dominio especifico.
- Reemplazar ReAct propio por framework externo sin ADR nuevo.
- Quitar auditoria de herramientas/accesos.

## Pendientes De Decision Para Fase 10

1. Definir catalogo inicial de metricas Prometheus.
2. Definir politica de cardinalidad y etiquetas.
3. Definir umbrales iniciales de alertas.

## Proceso Para Nuevos ADRs

Crear un ADR cuando exista:

- Cambio arquitectonico significativo.
- Trade-off no trivial.
- Decision con impacto en multiples modulos.
- Cambio de seguridad, persistencia o despliegue.

Formato recomendado:

```markdown
# ADR-NNN - Titulo

## Contexto

## Opciones Consideradas

## Decision

## Consecuencias

## Alternativas Futuras
```

## Referencias Cruzadas

- [Vision general](../01-estructura/00-vision-general.md)
- [Arquitectura core](../01-estructura/01-arquitectura-core.md)
- [Componentes](../03-componentes/README.md)
- [Fase 2 Enhancement](../02-bitacoras/fase-02-enhancement.md)
- [Changelog](../02-bitacoras/changelog.md)

---

**Ultima actualizacion**: 2026-05-18  
**Siguiente revision recomendada**: cierre de Fase 8

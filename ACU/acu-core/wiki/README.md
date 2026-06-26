# Wiki del Proyecto ACU - Agente Cognitivo Universal

Este wiki centraliza documentacion tecnica, bitacoras, decisiones y referencias del proyecto ACU.

## Estado Actual

**Fecha de actualizacion**: 2026-05-19  
**Fase vigente**: Fase 9.5 - Estabilizacion Funcional y Modularizacion Core  
**Estado**: Fase 9.5 cerrada funcionalmente; lista para validacion end-to-end ampliada  
**Verificacion**: `ruff check`, `ruff format --check`, `mypy src scripts main.py`, `241 passed, 4 skipped`
**Integracion MySQL**: `3 passed` opt-in contra MySQL Docker en `localhost:3307`

ACU ya cuenta con:

- API REST FastAPI operativa.
- Dashboard operativo en `/dashboard`.
- Dashboard modularizado en template HTML y archivos CSS/JS estaticos.
- Chat ACU desde API y dashboard.
- BrainCore con decisiones, ingesta, busqueda, fuentes, eliminacion y metricas.
- Retrieval textual y vectorial opcional con ChromaDB o FAISS.
- Metricas de sistema, vector store, HITL, scheduler, Redis y webhooks en `/system/metrics`.
- Checklist runtime de exposicion operativa en `/system/readiness`.
- API keys estaticas y gestionadas por BD.
- Roles: `admin`, `chat`, `braincore_read`, `braincore_write`, `monitoring`.
- CORS, limite de payload y rate limiting configurables.
- Auditoria de herramientas y accesos API.
- Persistencia de sesiones y contexto conversacional.
- Suite automatizada vigente.
- Baseline de calidad local verde: lint, formato, tipos y tests.

Documento principal de la fase vigente:

- [Fase 2 Enhancement](02-bitacoras/fase-02-enhancement.md)
- [Fase 8 Estabilizacion Profesional](02-bitacoras/fase-08-estabilizacion-profesional.md)
- [Fase 9 Operacion y Observabilidad](02-bitacoras/fase-09-operacion-observabilidad.md)
- [Fase 9.5 Estabilizacion Funcional](02-bitacoras/fase-09-5-estabilizacion-funcional.md)
- [Fase 10 Observabilidad Historica y Alertas](02-bitacoras/fase-10-observabilidad-historica.md)

## Navegacion Principal

### 01 - Estructura del Proyecto

- [Vision general](01-estructura/00-vision-general.md)
- [Arquitectura core](01-estructura/01-arquitectura-core.md)
- [Estructura fisica](01-estructura/02-estructura-fisica.md)

### 02 - Bitacoras de Avances

- [Indice de bitacoras](02-bitacoras/README.md)
- [Fase 1 Foundation](02-bitacoras/fase-01-foundation.md)
- [Fase 2 Enhancement](02-bitacoras/fase-02-enhancement.md)
- [Changelog](02-bitacoras/changelog.md)
- [Plantilla de fase](02-bitacoras/plantilla-fase.md)
- [Fase 8 Estabilizacion Profesional](02-bitacoras/fase-08-estabilizacion-profesional.md)
- [Fase 9 Operacion y Observabilidad](02-bitacoras/fase-09-operacion-observabilidad.md)
- [Fase 9.5 Estabilizacion Funcional](02-bitacoras/fase-09-5-estabilizacion-funcional.md)
- [Fase 10 Observabilidad Historica y Alertas](02-bitacoras/fase-10-observabilidad-historica.md)

### 03 - Componentes

- [Indice de componentes](03-componentes/README.md)
- [Contrato `/system/metrics`](03-componentes/observabilidad-system-metrics.md)
- [Readiness operativa](03-componentes/readiness-operativa.md)
- [Journeys funcionales criticos](03-componentes/journeys-funcionales.md)

### 04 - Decisiones Tecnicas

- [Decisiones y ADRs](04-decisiones/README.md)
- [Seguridad operativa](04-decisiones/seguridad-operativa.md)
- [Versionado de imagenes](04-decisiones/versionado-imagenes.md)
- [Retencion de auditoria y contexto](04-decisiones/retencion-auditoria-contexto.md)
- [Versionado de API y OpenAPI](04-decisiones/versionado-api-openapi.md)
- [Metricas runtime multi-replica](04-decisiones/metricas-multireplica.md)
- [Gobierno BrainCore por dominio](04-decisiones/gobierno-braincore.md)
- [Cierre formal de Fase 9](04-decisiones/cierre-fase-09.md)

### 05 - Referencias

- [Referencias tecnicas](05-referencias/README.md)

## Estado Por Area

| Area | Estado | Detalles |
|------|--------|----------|
| ReAct core | Operativo | Bucle agente, herramientas, prompt y LLM local |
| API REST | Operativa | FastAPI con chat, BrainCore, monitoreo y seguridad |
| Dashboard | Operativo | Chat, BrainCore, sesiones, auditoria, API keys y estado runtime |
| BrainCore | Operativo | ADRs, ingesta, busqueda, fuentes, metricas y estado vectorial |
| Seguridad | Operativa | API keys estaticas/gestionadas, roles, runbook operativo y controles de produccion |
| Auditoria | Operativa | Accesos API y ejecuciones de herramientas |
| Tests | Operativos | `241 passed, 4 skipped` |
| Scheduler | Operativo con worker dedicado | `ACU_SCHEDULER_MODE`: `disabled`, `api`, `worker`, `all` |
| Docker/MySQL real tests | Verificado opt-in | `3 passed` contra `acu-mysql` publicado en `localhost:3307` |
| Calidad estatica | Operativa | `ruff check`, `ruff format --check`, `mypy src scripts main.py` |
| HITL avanzado | Operativo | Cola no bloqueante, aprobacion, ejecucion y reanudacion conversacional |
| Webhooks externos | Operativos con hardening opt-in | Telegram secret, Slack signing secret, replay window y allowlists |
| Observabilidad operativa | Cerrada Fase 9 | `/system/metrics` reporta vector store, seguridad, HITL, scheduler, Redis y webhooks |
| Readiness operativa | Operativa | `/system/readiness` y `scripts/readiness_gate.py` bloquean exposicion con fallos criticos |
| Docker/healthchecks | Operativo | API, scheduler, MySQL, Redis, Ollama y Jaeger con healthchecks en compose/stack |
| Versionado de imagenes | Operativo | GHCR publica `latest`, `sha-<commit>` y tags semanticos `X.Y.Z`, `X.Y`, `X` |
| Retencion de datos operativos | Operativa | Scheduler poda auditoria, contexto y sesiones finalizadas segun politica |
| Versionado API | Operativo | Contrato `v1` publicado en headers, `/api/version` y OpenAPI |
| Metricas multi-replica | Operativa parcial | Webhooks consolida en Redis; Prometheus queda como evolucion futura |
| Gobierno BrainCore | Operativo | Exportacion y limpieza controlada por dominio |

## Inicio Rapido

```bash
cd acu-core
pip install -r requirements/dev.txt
copy .env.example .env
python -m pytest
```

`requirements.txt` sigue disponible como perfil completo por compatibilidad.

Modo API:

```bash
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Dashboard:

```text
http://127.0.0.1:8000/dashboard
```

## Lecturas Recomendadas

1. [Vision general](01-estructura/00-vision-general.md)
2. [Arquitectura core](01-estructura/01-arquitectura-core.md)
3. [Fase 2 Enhancement](02-bitacoras/fase-02-enhancement.md)
4. [Changelog](02-bitacoras/changelog.md)
5. [Contrato `/system/metrics`](03-componentes/observabilidad-system-metrics.md)
6. [Seguridad operativa](04-decisiones/seguridad-operativa.md)
7. [Versionado de imagenes](04-decisiones/versionado-imagenes.md)
8. [Retencion de auditoria y contexto](04-decisiones/retencion-auditoria-contexto.md)
9. [Versionado de API y OpenAPI](04-decisiones/versionado-api-openapi.md)
10. [Metricas runtime multi-replica](04-decisiones/metricas-multireplica.md)
11. [Gobierno BrainCore por dominio](04-decisiones/gobierno-braincore.md)
12. [Readiness operativa](03-componentes/readiness-operativa.md)
13. [Journeys funcionales criticos](03-componentes/journeys-funcionales.md)
14. [README principal](../README.md)
15. [USAGE](../USAGE.md)
16. [ARCHITECTURE](../ARCHITECTURE.md)

## Siguiente Foco Recomendado

Fase 9.5: estabilizacion funcional y modularizacion core.

Prioridades:

1. Expandir journey BrainCore ingest/search/export/delete.
2. Convertir HITL approve/execute/resume en journey funcional unico.
3. Preparar extraccion de repositorio API keys desde `mysql_manager.py`.

---

**Version del wiki**: 1.2.0  
**Ultima actualizacion**: 2026-05-19  
**Mantenedor**: RevoxeTech AI Team

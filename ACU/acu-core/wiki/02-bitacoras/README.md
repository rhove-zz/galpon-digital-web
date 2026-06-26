# Bitacoras y Registro de Cambios

Este directorio mantiene el historial de desarrollo de ACU por fases, junto con el changelog consolidado.

## Estado Actual

**Fecha de actualizacion**: 2026-05-19  
**Fase vigente**: Fase 9.5 - Estabilizacion Funcional y Modularizacion Core  
**Estado**: Fase 9.5 cerrada funcionalmente; lista para validacion end-to-end ampliada  
**Calidad verificada**: `ruff check`, `ruff format --check`, `mypy src scripts main.py`, `241 passed, 4 skipped`

ACU ya cuenta con API REST, dashboard operativo, BrainCore funcional, seguridad por roles, auditoria persistente, Redis, scheduler, webhooks, guardrails y suite automatizada vigente. Fase 9 deja esos flujos como una superficie operable y observable; Fase 9.5 reduce riesgo de mantenimiento antes de iniciar Fase 10.

## Indice de Fases

### Fase 1: Foundation

- **Periodo**: 23 Abril 2024
- **Documento**: [fase-01-foundation.md](fase-01-foundation.md)
- **Estado**: Completa
- **Resumen**: arquitectura base, ReAct loop, configuracion, herramientas iniciales, MySQL read-only, logging y Docker.

Hitos principales:

- Orquestador ReAct base.
- Cliente Ollama.
- Conector MySQL y schema dinamico.
- Tools manager inicial.
- Memoria evolutiva inicial.
- Documentacion fundacional.

### Fase 2: Enhancement

- **Fecha de actualizacion**: 2026-05-17
- **Documento**: [fase-02-enhancement.md](fase-02-enhancement.md)
- **Estado**: Completada operativamente
- **Resumen**: backend API, dashboard, BrainCore operativo, seguridad por roles, auditoria y tests automatizados.

Hitos principales:

- FastAPI REST operativa.
- Dashboard en `/dashboard`.
- Chat ACU desde API y dashboard.
- BrainCore con decisiones, ingesta, busqueda, fuentes, eliminacion y metricas.
- Backends vectoriales opcionales ChromaDB y FAISS.
- Metricas de sistema y estado del vector store en `/system/metrics`.
- API keys estaticas y gestionadas por BD.
- Roles `admin`, `chat`, `braincore_read`, `braincore_write`, `monitoring`.
- Auditoria de API y herramientas.
- Persistencia de sesiones y contexto conversacional.
- Suite pytest al cierre de Fase 2: `105 passed, 3 skipped`.
- Pruebas MySQL reales validadas opt-in: `3 passed`.

### Fase 8: Estabilizacion Profesional

- **Fecha de actualizacion**: 2026-05-18
- **Documento**: [fase-08-estabilizacion-profesional.md](fase-08-estabilizacion-profesional.md)
- **Estado**: Estabilizada
- **Resumen**: saneamiento de calidad estatica, tipos, formato, pruebas y realineacion de flujos criticos.

Hitos principales:

- Baseline verde en `ruff check`.
- Baseline verde en `ruff format --check`.
- Baseline verde en `mypy src`.
- Suite pytest vigente: `122 passed, 4 skipped`.
- Correccion y cobertura unitaria de delegacion multi-agente.
- Correccion inicial de contratos Redis/tipos.
- Registro de marker `integration_vector`.
- Webhooks seguros opt-in, scheduler configurable y HITL reanudable.
- Perfiles de dependencias separados y CI por jobs de integracion.

### Fase 9: Operacion y Observabilidad

- **Fecha de inicio**: 2026-05-18
- **Documento**: [fase-09-operacion-observabilidad.md](fase-09-operacion-observabilidad.md)
- **Estado**: Cerrada operativamente
- **Resumen**: metricas operativas para HITL, scheduler, Redis y webhooks, visibles desde `/system/metrics` y dashboard; readiness runtime para exposicion segura; UX HITL avanzada para estados vivos.

Hitos principales:

- Contrato `/system/metrics` ampliado con `pending_tools`, `scheduler`, `redis` y `webhooks`.
- Tarjetas superiores del dashboard para HITL, Scheduler y Webhooks.
- Tabla HITL con estados `pending`, `executed`, `failed`, `rejected` y `resumed`.
- Metricas webhook consolidadas en Redis para despliegues multi-replica, con fallback local.
- Gobierno BrainCore por dominio con exportacion y limpieza controlada.
- Readiness operativa en `/system/readiness` con gate CLI `scripts/readiness_gate.py`.
- Docker local/prod/stack con healthchecks por servicio.
- CI valida compose, construye imagen productiva y ejecuta smoke test de `/health` + readiness.
- CI publica tags GHCR `latest`, `sha-<commit>` y SemVer cuando se empuja `vX.Y.Z`.
- Compose prod y stack permiten fijar releases mediante `ACU_IMAGE`.
- Contrato `/system/metrics` documentado con ejemplo request/response, umbrales y runbook.
- Runbook de seguridad operativa con roles, secretos, limites, auditoria y checklist de release.
- Retencion operativa para auditoria, contexto conversacional y sesiones finalizadas desde `acu-scheduler`.
- Contrato API `v1` publicado en headers, `/api/version` y OpenAPI.
- Pruebas de contrato API y presencia de UI.
- Cierre formal aprobado en [cierre-fase-09.md](../04-decisiones/cierre-fase-09.md).

### Fase 9.5: Estabilizacion Funcional y Modularizacion Core

- **Fecha de inicio**: 2026-05-19
- **Documento**: [fase-09-5-estabilizacion-funcional.md](fase-09-5-estabilizacion-funcional.md)
- **Fecha de cierre**: 2026-05-19
- **Estado**: Cerrada funcionalmente
- **Resumen**: fase intermedia que modulariza `app.py` y `mysql_manager.py`, refuerza journeys funcionales y valida MySQL real antes de Fase 10.

Hitos principales:

- Extraccion de readiness a `src/api/readiness.py`.
- Extraccion de seguridad API/RBAC a `src/api/security.py`.
- Routers `system`, `chat`, `braincore`, `monitoring`, `api_keys` y `tools`.
- Repositorios MySQL por responsabilidad para API keys, auditoria, sesiones, BrainCore, memoria evolutiva y SQL runtime.
- `app.py` reducido a 412 lineas y `mysql_manager.py` reducido a 465 lineas.
- Journeys funcionales de API keys, BrainCore y HITL protegidos por pruebas.
- MySQL real opt-in validado: `3 passed` contra MySQL Docker en `localhost:3307`.

### Fase 10: Observabilidad Historica y Alertas

- **Documento**: [fase-10-observabilidad-historica.md](fase-10-observabilidad-historica.md)
- **Estado**: Propuesta
- **Resumen**: evolucion opt-in hacia Prometheus/Grafana, historicos, alertas y dashboards externos.

Hitos propuestos:

- Catalogo de metricas y politica de cardinalidad.
- Exportador Prometheus opt-in.
- Compose/stack con perfil de observabilidad historica.
- Dashboard Grafana versionado.
- Alertas de alta senal para disponibilidad, seguridad y backlog HITL.

## Estadisticas por Fase

| Fase | Estado | Documento | Verificacion |
|------|--------|-----------|--------------|
| 1 Foundation | Completa | [fase-01-foundation.md](fase-01-foundation.md) | Manual / base funcional |
| 2 Enhancement | Completa operativamente | [fase-02-enhancement.md](fase-02-enhancement.md) | `105 passed, 3 skipped` |
| 3 Roadmap | Documentada | [fase-03-estandarizacion-roadmap.md](fase-03-estandarizacion-roadmap.md) | Documental |
| 4 Herramientas | Documentada | [fase-04-expansion-herramientas.md](fase-04-expansion-herramientas.md) | Documental |
| 5 Hardening | Documentada | [fase-05-hardening-observabilidad.md](fase-05-hardening-observabilidad.md) | Documental |
| 6 Multi-agente | Documentada | [fase-06-orquestacion-multi-agente.md](fase-06-orquestacion-multi-agente.md) | Documental |
| 7 Interfaces | Documentada | [fase-07-interfaces-conversacionales.md](fase-07-interfaces-conversacionales.md) | Documental |
| 8 Estabilizacion Profesional | Estabilizada | [fase-08-estabilizacion-profesional.md](fase-08-estabilizacion-profesional.md) | `ruff`, `mypy`, `122 passed, 4 skipped` |
| 9 Operacion y Observabilidad | Cerrada operativamente | [fase-09-operacion-observabilidad.md](fase-09-operacion-observabilidad.md) | `ruff`, `mypy`, `157 passed, 4 skipped` |
| 9.5 Estabilizacion Funcional | Cerrada funcionalmente | [fase-09-5-estabilizacion-funcional.md](fase-09-5-estabilizacion-funcional.md) | `ruff`, `mypy`, `241 passed, 4 skipped`, MySQL `3 passed` |
| 10 Observabilidad Historica | Propuesta | [fase-10-observabilidad-historica.md](fase-10-observabilidad-historica.md) | Pendiente |

## Changelog

Registro consolidado de cambios:

- [changelog.md](changelog.md)

Entrada vigente:

- `1.5.0` - Fase 9 Operacion y Observabilidad.

## Plantillas

Para documentar una nueva fase:

1. Copiar [plantilla-fase.md](plantilla-fase.md).
2. Renombrar como `fase-NN-nombre.md`.
3. Completar resumen, hitos, cambios, validacion y pendientes.
4. Actualizar este README.
5. Agregar entrada en [changelog.md](changelog.md).

## Formato Recomendado Para Nuevos Hitos

~~~markdown
## YYYY-MM-DD

### Objetivo

Descripcion clara del cambio.

### Completado

- Feature 1
- Feature 2

### Validacion

```bash
python -m pytest
```

### Pendientes

- Siguiente tarea
~~~

## Enlaces Rapidos

- [Fase 1 Foundation](fase-01-foundation.md)
- [Fase 2 Enhancement](fase-02-enhancement.md)
- [Fase 8 Estabilizacion Profesional](fase-08-estabilizacion-profesional.md)
- [Fase 9 Operacion y Observabilidad](fase-09-operacion-observabilidad.md)
- [Fase 9.5 Estabilizacion Funcional](fase-09-5-estabilizacion-funcional.md)
- [Fase 10 Observabilidad Historica](fase-10-observabilidad-historica.md)
- [Changelog](changelog.md)
- [Wiki principal](../README.md)
- [Vision general](../01-estructura/00-vision-general.md)

---

**Ultima actualizacion**: 2026-05-19  
**Siguiente foco recomendado**: validacion end-to-end ampliada y Fase 10 - observabilidad historica opt-in

# Cierre Formal De Fase 9

**Fecha**: 2026-05-19  
**Estado**: aprobado  
**Alcance**: operacion, observabilidad runtime, seguridad de exposicion, Docker/CI y gobierno BrainCore.

## Decision

Fase 9 se considera cerrada operativamente cuando el proyecto cumple estos criterios:

| Criterio | Evidencia | Estado |
|----------|-----------|--------|
| Observabilidad runtime | `GET /system/metrics` documentado y probado | Cumplido |
| Readiness de exposicion | `GET /system/readiness` y `scripts/readiness_gate.py` | Cumplido |
| Seguridad operativa | Runbook de roles, secretos, rate limit, payload y CORS | Cumplido |
| Docker y release | Imagen API-first, healthchecks, `ACU_IMAGE` y smoke test CI | Cumplido |
| Retencion operativa | Scheduler poda auditoria, contexto y sesiones cerradas | Cumplido |
| Gobierno BrainCore | Exportacion y limpieza controlada por dominio | Cumplido |
| Contrato API | `v1` publicado en headers, `/api/version` y OpenAPI | Cumplido |
| Calidad | `ruff`, `mypy`, `pytest` verdes | Cumplido |

## Validacion De Cierre

Comandos vigentes:

```bash
python -m ruff format --check src tests scripts main.py
python -m ruff check src tests scripts main.py
python -m mypy src scripts main.py --ignore-missing-imports
python -m pytest
```

Resultado vigente:

```text
157 passed, 4 skipped
```

## Decision Sobre Prometheus/Grafana

Prometheus/Grafana no entra en Fase 9. La fase ya entrega observabilidad runtime suficiente para operar ACU con dashboard, `/system/metrics`, readiness y CI smoke gates.

La observabilidad historica se difiere a Fase 10 porque requiere decisiones adicionales:

- Modelo de metricas exportables.
- Cardinalidad y etiquetas permitidas.
- Retencion de series temporales.
- Alertas operativas y severidades.
- Compose/stack con Prometheus y Grafana.
- Dashboards versionados.

## Consecuencias

- Fase 9 queda enfocada y cerrable sin introducir nueva infraestructura obligatoria.
- Fase 10 arranca con alcance claro: historicos, alertas y dashboards externos.
- El core mantiene compatibilidad local; Prometheus/Grafana debe ser opt-in.

## Criterios De No Regresion

- No eliminar `GET /system/metrics`, `GET /system/readiness` ni `/api/version` sin migracion de contrato.
- No romper `scripts/readiness_gate.py` en CI.
- Mantener `pytest`, `ruff` y `mypy` verdes antes de abrir Fase 10.

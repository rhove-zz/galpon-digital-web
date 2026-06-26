# Fase 10 - Observabilidad Historica y Alertas

**Estado**: Propuesta  
**Dependencia**: Fase 9 cerrada operativamente  
**Objetivo**: evolucionar la observabilidad runtime de ACU hacia historicos, alertas y dashboards externos.

## Razonamiento

Fase 9 deja la operacion base lista: metricas runtime, readiness, seguridad de exposicion, Docker/CI, retencion y gobierno BrainCore. El siguiente salto profesional no es agregar mas endpoints aislados, sino convertir senales runtime en historicos consultables y alertas accionables.

Prometheus/Grafana se adopta como evolucion opt-in, no como dependencia obligatoria del core.

## Alcance Propuesto

1. Exportador Prometheus opt-in.
2. Metricas versionadas para API, HITL, scheduler, Redis, webhooks y BrainCore.
3. politica de cardinalidad para etiquetas.
4. Compose/stack con Prometheus y Grafana.
5. Dashboard Grafana versionado.
6. Reglas de alerta para seguridad, disponibilidad y backlog HITL.
7. Runbook de incidentes y triage.

## Fuera De Alcance Inicial

- APM distribuido completo.
- Trazas obligatorias en todos los flujos.
- Dependencia obligatoria de Prometheus para desarrollo local.
- Alertas multicanal reales sin definir proveedor operativo.

## Criterios De Entrada

- Fase 9 cerrada.
- `GET /system/metrics` y `GET /system/readiness` estables.
- CI verde con gate de readiness.
- Baseline de seguridad operativo documentado.

## Criterios De Salida

- Endpoint o middleware de metricas Prometheus opt-in.
- Compose local con perfil de observabilidad historica.
- Dashboard Grafana exportado como JSON versionado.
- Alertas documentadas con umbrales iniciales.
- Tests de contrato para metricas exportadas.
- Validacion completa verde.

## Riesgos

| Riesgo | Mitigacion |
|--------|------------|
| Cardinalidad excesiva | Limitar etiquetas y documentar convenciones |
| Complejidad de despliegue | Mantener Prometheus/Grafana como perfil opt-in |
| Alertas ruidosas | Empezar con pocas alertas de alta senal |
| Duplicidad con `/system/metrics` | Usar `/system/metrics` para snapshot humano y Prometheus para series historicas |

## Primeros Hitos Recomendados

1. Definir catalogo de metricas y nombres.
2. Agregar exportador Prometheus opt-in.
3. Crear compose profile `observability`.
4. Versionar dashboard Grafana inicial.
5. Agregar alertas minimas.

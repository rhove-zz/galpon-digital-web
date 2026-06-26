# Metricas Runtime Multi-Replica

**Fecha de actualizacion**: 2026-05-18  
**Estado**: politica operativa definida  
**Alcance**: metricas webhook compartidas, Redis y `/system/metrics`.

## Objetivo

Evitar que despliegues con varias replicas API reporten contadores parciales por proceso. ACU conserva fallback local para desarrollo, pero en produccion usa Redis como fuente compartida cuando esta conectado.

## Decision

Las metricas de webhooks se registran en dos capas:

1. Memoria local del proceso como fallback.
2. Redis bajo claves `webhook_metrics:{channel}` cuando `ACU_REDIS_URL` esta activo y conectado.

`GET /system/metrics` prefiere los contadores Redis. Si Redis no esta disponible, devuelve el snapshot local del proceso.

## Canales Y Campos

Canales iniciales:

- `telegram`
- `slack`

Campos consolidados:

- `received`
- `accepted`
- `rejected`
- `ignored`
- `processed`
- `failed`
- `last_event_at`
- `last_error`

## Reglas Operativas

- En despliegues multi-replica, Redis es obligatorio para que webhooks sean agregados.
- El fallback local solo representa el proceso actual.
- Las metricas webhook en Redis expiran despues de 7 dias de inactividad para evitar crecimiento indefinido.
- HITL ya usa Redis cuando esta disponible porque la cola vive en `pending_tool:*`.
- Para historicos largos o alertas avanzadas, Prometheus/Grafana sigue siendo una evolucion futura.

## Validacion

1. Configurar `ACU_REDIS_URL=redis://redis:6379/0`.
2. Levantar al menos dos replicas API.
3. Enviar eventos webhook a distintas replicas.
4. Consultar `GET /system/metrics`.
5. Confirmar que `webhooks.total.received` refleja el agregado.


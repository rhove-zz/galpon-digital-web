# Retencion De Auditoria Y Contexto

**Fecha de actualizacion**: 2026-05-18  
**Estado**: politica operativa definida  
**Alcance**: `tool_execution_log`, `api_access_log`, `conversation_context` y `agent_sessions`.

## Objetivo

Mantener trazabilidad suficiente para soporte y seguridad sin acumular datos operativos indefinidamente. La retencion se ejecuta desde el scheduler y debe correr en un unico worker productivo.

## Variables

| Variable | Default | Aplica a | Notas |
|----------|---------|----------|-------|
| `ACU_LOG_RETENTION_DAYS` | `30` | fallback legacy | Se usa si no se configuran variables especificas |
| `ACU_AUDIT_RETENTION_DAYS` | `ACU_LOG_RETENTION_DAYS` | `tool_execution_log`, `api_access_log` | Auditoria tecnica y seguridad |
| `ACU_CONVERSATION_RETENTION_DAYS` | `ACU_LOG_RETENTION_DAYS` | `conversation_context`, `agent_sessions` finalizadas | Contexto conversacional y ciclo de sesion |

Baseline recomendado:

```env
ACU_SCHEDULER_MODE=worker
ACU_AUDIT_RETENTION_DAYS=90
ACU_CONVERSATION_RETENTION_DAYS=30
```

## Rutina Automatizada

El job `prune_logs_job` corre diariamente a las `03:00` en el scheduler. En produccion debe ejecutarse desde el servicio `acu-scheduler`, no desde multiples replicas API.

Orden de limpieza:

1. `tool_execution_log` por `fecha_ejecucion`.
2. `api_access_log` por `fecha_acceso`.
3. `conversation_context` por `timestamp`.
4. `agent_sessions` finalizadas por `fin`.

Las sesiones activas no se eliminan porque `agent_sessions.fin IS NOT NULL` es condicion obligatoria. Antes de borrar sesiones finalizadas antiguas, se borra contexto asociado para respetar la relacion con `conversation_context`.

## Criterio De Datos

| Dato | Retencion sugerida | Razon |
|------|--------------------|-------|
| Accesos API | 90 dias | Investigacion de seguridad y soporte |
| Ejecuciones de herramientas | 90 dias | Trazabilidad de acciones sensibles |
| Contexto conversacional | 30 dias | Reducir exposicion de texto libre |
| Sesiones finalizadas | 30 dias | Mantener historial operativo reciente |
| BrainCore | Sin poda automatica | Es memoria curada; se elimina por fuente o decision explicita |
| API keys revocadas | Sin poda automatica inicial | Se conservan para auditoria de fingerprints |

## Runbook

1. Configurar `ACU_SCHEDULER_MODE=worker`.
2. Definir `ACU_AUDIT_RETENTION_DAYS` y `ACU_CONVERSATION_RETENTION_DAYS`.
3. Ejecutar una replica unica de `acu-scheduler`.
4. Revisar `/system/metrics` para confirmar `scheduler.running=true` y job `prune_logs_job`.
5. Revisar logs del scheduler despues de las `03:00`.
6. Si se requiere retener datos por cumplimiento, respaldar/exportar antes de bajar los dias.

## Riesgos Y Controles

- Retencion demasiado baja puede eliminar evidencia util para incidentes.
- Retencion demasiado alta puede acumular texto libre y auditoria innecesaria.
- Multiples schedulers pueden duplicar trabajo. Usar `ACU_SCHEDULER_MODE=worker` y una sola replica.
- BrainCore no se poda automaticamente para evitar perdida accidental de conocimiento curado.


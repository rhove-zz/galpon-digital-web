# Journeys Funcionales Criticos

**Fecha**: 2026-05-19  
**Estado**: matriz inicial  
**Alcance**: flujos funcionales que deben proteger la modularizacion de Fase 9.5.

## Objetivo

Esta matriz define los journeys que deben permanecer verdes antes de mover codigo estructural, especialmente `mysql_manager.py` y routers API. El foco es demostrar comportamiento funcional completo, no solo cobertura unitaria.

## Matriz

| ID | Journey | Criticidad | Tipo minimo | Evidencia actual |
|----|---------|------------|-------------|------------------|
| J-APIKEY-001 | Crear API key, usarla en `/chat`, revocarla y confirmar rechazo posterior | Alta | API funcional + MySQL real opt-in | `test_api_key_functional_journey_create_use_revoke_then_rejects`, `test_mysql_integration_audit_sessions_and_api_keys_round_trip` |
| J-BRAIN-001 | Registrar decision BrainCore, listarla y filtrarla por dominio | Alta | API funcional + MySQL real opt-in | `test_braincore_decision_endpoint_registers_adr`, `test_mysql_integration_braincore_round_trip` |
| J-BRAIN-002 | Ingerir fuente, buscar contexto, exportar dominio y eliminar dominio con confirmacion | Alta | API funcional + MySQL real opt-in | `test_braincore_functional_journey_ingest_search_export_delete_domain`, `test_braincore_domain_export_endpoint_returns_snapshot`, `test_braincore_domain_delete_requires_confirmation_and_deletes_domain` |
| J-HITL-001 | Aprobar/rechazar herramienta pendiente y reanudar conversacion ejecutada | Alta | API funcional con Redis fake + smoke real posterior | `test_hitl_functional_journey_reject_approve_execute_and_resume`, `test_resume_pending_tool_uses_session_context_and_marks_resumed` |
| J-RETENTION-001 | Ejecutar retencion de auditoria, contexto y sesiones finalizadas | Media | Unitario + MySQL real opt-in | `test_prune_agent_sessions_deletes_context_before_completed_sessions`, `test_mysql_integration_audit_sessions_and_api_keys_round_trip` |
| J-READY-001 | Validar readiness inseguro, seguro y gate CLI | Alta | API funcional + CLI | `test_system_readiness_reports_not_ready_for_insecure_runtime`, `test_system_readiness_reports_ready_for_security_baseline`, `test_readiness_gate_rejects_not_ready` |

## Politica De Corte

Antes de extraer un repositorio o router:

1. Identificar journeys impactados.
2. Confirmar que existen pruebas automatizadas del journey.
3. Ejecutar pruebas enfocadas del journey.
4. Ejecutar suite completa.
5. Si el corte toca persistencia, ejecutar `pytest -m integration_mysql` cuando Docker/MySQL este disponible.

## Siguiente Cobertura Recomendada

1. Antes de extraer repositorios de `mysql_manager.py`, agregar pruebas contractuales por repositorio destino.
2. Ejecutar `pytest -m integration_mysql` despues del primer corte real sobre persistencia BrainCore/API keys.
3. Preparar router dedicado para BrainCore manteniendo los journeys verdes.

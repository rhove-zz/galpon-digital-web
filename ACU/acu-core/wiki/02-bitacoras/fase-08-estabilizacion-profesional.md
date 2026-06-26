# Fase 8 - Estabilizacion Profesional

## Estado

**Fecha**: 2026-05-18  
**Estado**: en progreso  
**Objetivo**: llevar ACU a un baseline profesional verificable antes de seguir agregando superficie funcional.

Esta fase no busca sumar mas features. Su objetivo es cerrar deuda tecnica, alinear documentacion con codigo real y asegurar que los flujos nuevos funcionen bajo criterios objetivos.

## Baseline Validado

Comandos ejecutados:

```bash
python -m ruff check src tests main.py
python -m ruff format --check src tests main.py
python -m mypy src
python -m pytest
```

Resultado actual:

```text
ruff check: passed
ruff format --check: passed
mypy: success, no issues found in 28 source files
pytest: 122 passed, 4 skipped
```

## Cambios Aplicados

- Se registro el marker `integration_vector` en `pytest.ini`.
- Se corrigieron imports y retornos duplicados en API/webhooks/tests.
- Se corrigieron errores de tipos en `redis_manager.py`.
- Se corrigio la creacion del sub-agente delegado en `tools_manager.py`.
- Se hizo defensiva la evaluacion `LLM-as-a-Judge` cuando el juez no responde.
- Se elimino la doble compuerta Human-in-the-Loop del loop del agente para que la decision viva en `ToolsManager`.
- Se convirtio Human-in-the-Loop a flujo no bloqueante: las herramientas sensibles devuelven `pending_tool_id` y se ejecutan al aprobar.
- Se agregaron pruebas unitarias para cola HITL y ejecucion posterior a aprobacion.
- Se agrego hardening opt-in para webhooks: Telegram secret, Slack signing secret, ventana anti-replay y allowlists.
- Se agregaron pruebas de seguridad para webhooks Slack/Telegram.
- Se profesionalizo el scheduler con `ACU_SCHEDULER_MODE` y worker dedicado (`python -m src.api.scheduler`).
- Se agregaron servicios `acu-scheduler` en compose local, produccion y stack.
- Se agregaron pruebas unitarias para modos de scheduler.
- Se agregaron pruebas unitarias de `delegar_tarea` para descripcion requerida, inicializacion fallida, juez `PASS` y juez `FAIL` con autocorreccion.
- Se agrego reanudacion conversacional HITL mediante `POST /tools/pending/{tool_id}/resume`.
- El dashboard encadena aprobacion, ejecucion y reanudacion para mostrar la respuesta final del agente.
- Se agregaron pruebas de reanudacion a nivel agente y API.
- Se separaron dependencias por perfil: `base`, `dev`, `vector`, `vector-faiss`, `observability` y `all`.
- Docker instala por defecto el perfil `observability`; CI usa `dev` para pruebas rapidas y perfiles dedicados para integraciones.
- Se normalizo formato con `ruff format`.

## Criterio Profesional

Un avance queda aceptado solo si cumple:

1. `ruff check` sin errores.
2. `ruff format --check` sin cambios pendientes.
3. `mypy src` sin errores.
4. `pytest` sin fallas.
5. Wiki actualizada si el cambio altera arquitectura, flujo o estado de fase.

## Pendientes Priorizados

### P0 - Cierre de Contratos Criticos

1. Separar pruebas vectoriales pesadas de CI regular o cachear modelos de embeddings.

### P1 - Seguridad Operativa

1. Definir politica para nuevos conectores externos usando el mismo patron de firma/secreto.
2. Hacer Redis opt-in fuera de Docker/prod para evitar ruido local.

### P2 - Arquitectura de Ejecucion

1. Actualizar `PROJECT_STRUCTURE.md` con modulos nuevos.
2. Revisar politica final de `requirements.txt` como perfil completo por compatibilidad.

## Riesgos Abiertos

| Riesgo | Impacto | Mitigacion |
|--------|---------|------------|
| Reanudacion HITL | El flujo depende de endpoint explicito `/resume` o del dashboard | Mantener contrato documentado y probar clientes externos |
| Scheduler mal configurado | Jobs deshabilitados o duplicados si `ACU_SCHEDULER_MODE` se configura incorrectamente | Usar `worker` en produccion y una sola replica de `acu-scheduler` |
| Nuevos conectores sin firma | Entrada externa falsificable si se agregan integraciones sin hardening | Reusar patron Slack/Telegram |
| CI vectorial pesado | Builds lentos o inestables | Job separado y cache de modelos |
| Documentacion adelantada | Confunde estado real | Mantener estado por fase verificable |

## Definicion de Listo Para Produccion

ACU se considerara listo para un despliegue profesional inicial cuando:

- CI ejecute lint, formato, tipos y tests en cada cambio.
- Integracion MySQL real este automatizada como job opt-in o servicio CI.
- Webhooks externos expuestos tengan validacion criptografica o secreto dedicado.
- HITL sea persistente, observable y no bloqueante.
- Scheduler no duplique jobs bajo multiples procesos.
- La wiki refleje estados reales, no aspiracionales.

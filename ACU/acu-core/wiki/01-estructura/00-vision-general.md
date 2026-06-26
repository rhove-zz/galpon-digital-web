# Vision General - ACU Project

## Que Es ACU

**ACU** (Agente Cognitivo Universal) es un orquestador Python que implementa el patron ReAct (`Reason + Act`) para operar como agente cognitivo autonomo.

El agente separa razonamiento, datos y memoria:

- Razona con LLM local via Ollama.
- Consulta datos por herramientas controladas.
- Usa MySQL para datos estructurados, memoria y auditoria.
- Usa BrainCore para memoria agentica transversal.
- Expone operacion por API REST y dashboard.

## Mision

Construir un agente autonomo que:

1. Separe razonamiento de conocimiento operacional.
2. Use herramientas para acceder a datos reales.
3. Mantenga consultas SQL de lectura bajo control.
4. Aprenda y preserve contexto operativo.
5. Sea observable, auditable y extensible.
6. Pueda operar en multiples dominios sin reescribir el core.

## Estado Actual

**Fecha de actualizacion**: 2026-05-19  
**Fase vigente**: Fase 9 cerrada; Fase 10 propuesta  
**Estado**: Baseline tecnico verde; observabilidad runtime cerrada  
**Validacion**: `ruff check`, `ruff format --check`, `mypy src scripts main.py`, `241 passed, 4 skipped`

| Area | Estado | Descripcion |
|------|--------|-------------|
| ReAct core | Operativo | Loop de agente, prompts, herramientas y conclusion |
| Ollama client | Operativo | Health check, completions y parsing de tool calls |
| MySQL | Operativo | Schema dinamico, SQL read-only, memoria y auditoria |
| API REST | Operativa | FastAPI con chat, BrainCore, monitoreo y seguridad |
| Dashboard | Operativo | UI de operacion, monitoreo y estado runtime |
| BrainCore | Operativo | Decisiones, ingesta, busqueda, fuentes, metricas y estado vectorial |
| Seguridad | Operativa | API keys estaticas y gestionadas por BD, readiness runtime y controles de exposicion |
| Tests | Operativos | Suite pytest vigente |
| Multi-agente | En hardening | Delegacion corregida y cubierta con pruebas unitarias |
| HITL | Operativo | Flujo no bloqueante con aprobacion, ejecucion y reanudacion conversacional |
| Webhooks | Operativos con hardening opt-in | Telegram secret, Slack signing secret, replay window y allowlists |

## Stack Tecnologico

```text
Dashboard
  -> FastAPI
    -> ACU Agent ReAct
      -> Ollama
      -> ToolsManager
        -> MySQL read-only
        -> BrainCore
        -> Memoria evolutiva
      -> Auditoria y sesiones

BrainCore
  -> MySQL textual fallback
  -> ChromaDB opcional
  -> FAISS opcional
```

Componentes principales:

- Python 3.11+
- FastAPI
- Ollama
- MySQL
- ChromaDB opcional
- FAISS opcional
- Pydantic
- pytest
- loguru

## Capacidades Operativas

### Agente

- Procesamiento de mensajes por `/chat`.
- Bucle ReAct con herramientas.
- Persistencia de sesiones y contexto conversacional.
- Auditoria de herramientas.

### BrainCore

- Registro/listado de decisiones arquitectonicas.
- Ingesta local de archivos y directorios.
- Busqueda contextual textual y vectorial opcional.
- Inventario de fuentes indexadas.
- Eliminacion de fuentes.
- Metricas agregadas.

### Dashboard

- Chat ACU.
- Sesiones y contexto.
- Auditoria de herramientas.
- Auditoria de accesos API.
- Gestion de API keys.
- BrainCore ADRs.
- Busqueda BrainCore.
- Ingesta/listado/eliminacion de fuentes.
- Metricas BrainCore.
- Metricas de sistema y estado del vector store.
- Readiness operativa para ambientes expuestos.

### Seguridad

- API key estatica (`ACU_API_KEY`).
- Mapa de claves por roles (`ACU_API_KEYS`).
- Claves gestionadas en BD.
- Checklist runtime en `GET /system/readiness`.
- Roles:
  - `admin`
  - `chat`
  - `braincore_read`
  - `braincore_write`
  - `monitoring`

## Fases

### Fase 1: Foundation

Estado: completa.

Entrego:

- Arquitectura modular.
- ReAct loop base.
- Integracion Ollama.
- Conector MySQL.
- Tools manager.
- Logging y configuracion.
- Docker base.
- Documentacion fundacional.

### Fase 2: Enhancement

Estado: completada operativamente.

Entrego:

- FastAPI REST.
- Dashboard.
- Suite pytest.
- BrainCore operativo.
- Seguridad por roles.
- API keys gestionadas.
- Auditoria persistente.
- Sesiones y contexto conversacional.
- Backends vectoriales opcionales.

Documento: [Fase 2 Enhancement](../02-bitacoras/fase-02-enhancement.md)

### Fase 4: Expansión Cognitiva y de Herramientas

Estado: completa.

Entrego:

- Pipeline RAG Multimodal (PDF, Word, CSV).
- Interfaz de comandos Sandbox (Python, Pandas).
- Interfaz de lectura/escritura File System (Sandbox).
- Interfaz HTTP Client API (GET/POST externo).
- Seguridad Human-in-the-Loop para autorizaciones.
- Auditoría extrema de ejecución de payload.
- Planificador (Task Decomposition) y Perfiles de Agente.

Documento: [Fase 4 Expansion](../02-bitacoras/fase-04-expansion-herramientas.md)

### Fase 5: Hardening, Observabilidad y Evolución UI

Estado: completa.

Objetivos:

- Implementar OpenTelemetry y métricas LLM.
- Rate limiting y circuit breakers para estabilidad de API.
- Modularización de UI, streaming ReAct interactivo y panel Human-in-the-Loop.
- Pruebas E2E y flujos CI/CD listos para producción.

Documento: [Fase 5 Hardening](../02-bitacoras/fase-05-hardening-observabilidad.md)

### Fase 6: Orquestación Multi-Agente y Casos de Uso Empresariales

Estado: completa.

Objetivos:

- Evolucionar hacia un enjambre (Swarm) de agentes especializados.
- Comunicación asíncrona entre agentes (Worker vs Supervisor).
- Despliegue de plantillas empresariales (Consultor ERP, Integrador APIs, Soporte, Analista).
- Integración nativa con interfaces externas (Telegram, Slack, Teams).

Documento: [Fase 6 Orquestacion](../02-bitacoras/fase-06-orquestacion-multi-agente.md)

### Fase 7: Interfaces Conversacionales Nativas

Estado: en progreso.

Objetivos:

- Evolucionar el panel de comandos en el Dashboard hacia una verdadera interfaz de Chat con formato enriquecido (Markdown, Tablas, Gráficos).
- Manejo interactivo del Human-in-the-Loop directamente en el chat.
- Despliegue y configuración de Webhooks externos desde UI.

### Fase 8: Estabilizacion Profesional

Estado: en progreso.

Objetivos:

- Mantener verde lint, formato, tipos y pruebas.
- Alinear documentacion con el estado real del codigo.
- Mantener Human-in-the-Loop como flujo persistente, auditable y reanudable.
- Mantener y ampliar politicas de seguridad para webhooks externos.
- Mantener el scheduler como worker dedicado/configurable en despliegues multi-worker.

Documento: [Fase 8 Estabilizacion Profesional](../02-bitacoras/fase-08-estabilizacion-profesional.md)

## Ubicacion Del Codigo

```text
acu-core/
  src/
    agent/
    api/
    braincore/
    config/
    llm/
    memory/
    tools/
    utils/
  tests/
  docker/
  wiki/
```

## Documentos Clave

- [README principal](../../README.md)
- [USAGE](../../USAGE.md)
- [ARCHITECTURE](../../ARCHITECTURE.md)
- [PROJECT_STRUCTURE](../../PROJECT_STRUCTURE.md)
- [Bitacora Fase 1](../02-bitacoras/fase-01-foundation.md)
- [Bitacora Fase 2](../02-bitacoras/fase-02-enhancement.md)
- [Changelog](../02-bitacoras/changelog.md)

## Criterio De Salud Del Proyecto

Antes de cerrar cambios:

```bash
python -m pytest
python -m ruff check src tests scripts main.py
python -m ruff format --check src tests scripts main.py
python -m mypy src scripts main.py --ignore-missing-imports
```

Resultado esperado actual:

```text
241 passed, 4 skipped
```

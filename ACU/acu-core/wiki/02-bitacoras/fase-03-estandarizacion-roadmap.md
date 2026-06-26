# 🗺️ Roadmap de Implementación: Fase 3 - Estandarización y Enterprise

**Fase**: 3 - Estandarización y Enterprise (Planificación)  
**Fecha de Creación**: 2026-05-17  
**Estado**: 🔜 Planificado  

---

## 🎯 Visión General

Tras la exitosa consolidación de la Fase 1 (Foundation) y Fase 2 (Enhancement), donde se blindó la arquitectura con medidas de seguridad (CORS, Rate Limiting) y métricas de observabilidad, el objetivo de la **Fase 3** es elevar ACU-CORE al nivel de un "Estándar de Industria" (Enterprise-Grade).

Este roadmap arquitectónico estructura las mejoras propuestas en 5 etapas lógicas y secuenciales para garantizar la estabilidad continua del sistema.

---

## 🚦 Etapas de Implementación

### Etapa 1: Base Inquebrantable (CI/CD y Calidad de Código)
*Objetivo: Asegurar que ninguna de las futuras mejoras rompa el núcleo estable actual mediante automatización.*

- [ ] **Tarea 1.1 - Análisis Estático Avanzado**: Integrar `Ruff` (formateo y linting hiper-rápido) y `MyPy` (validación estricta de tipos).
- [ ] **Tarea 1.2 - Pipeline de CI/CD Automatizado**: Crear flujos de trabajo (ej. GitHub Actions) que levanten los contenedores (`docker-compose up -d mysql`), ejecuten la suite de `pytest` completa (incluyendo integración) y validen el código en cada PR.
- **Entregable**: Repositorio auto-evaluado que rechaza automáticamente regresiones y código defectuoso.

### Etapa 2: Higiene de Datos y Mantenimiento Autónomo (Políticas de Retención)
*Objetivo: Prevenir la degradación de rendimiento de la base de datos MySQL por crecimiento infinito de logs operativos.*

- [x] **Tarea 2.1 - Motor de Tareas Asíncronas**: Integrar un scheduler ligero (ej. `APScheduler` o `BackgroundTasks` de FastAPI) para rutinas recurrentes.
- [x] **Tarea 2.2 - Rutinas de Poda (Pruning)**: Script automatizado de ejecución nocturna para purgar o archivar registros de `api_access_log` y `tool_execution_log` que superen los 30-60 días de antigüedad.
- **Entregable**: Sistema auto-gestionado que mantiene la base de datos ágil.

### Etapa 3: Mejoras de UX Agéntica (Streaming & Consola Administrativa)
*Objetivo: Reducir la latencia percibida a cero y proveer un centro de mando visual para la operación del agente.*

- [x] **Tarea 3.1 - Refactorización a Server-Sent Events (SSE)**: Modificar `AgentLoop` para implementar generadores asíncronos (`yield`). Exponer un nuevo endpoint `/chat/stream` que transmita los "Thoughts" y "Tool Executions" en tiempo real.
- [x] **Tarea 3.2 - Despliegue de Consola Administrativa (UI)**: Evolucionar el dashboard actual hacia un andamiaje Frontend moderno con un rediseño UI altamente pulido (Dark Mode y Glassmorphism) que consume los endpoints de métricas y SSE.
- **Entregable**: Interfaz de "Caja de Cristal" donde los usuarios y administradores visualizan el flujo cognitivo del agente en vivo de manera sofisticada.

### Etapa 4: Observabilidad Distribuida (El Ecosistema Enterprise)
*Objetivo: Evolucionar de métricas aisladas ("pull") a trazabilidad distribuida completa ("push").*

- [x] **Tarea 4.1 - Instrumentación OpenTelemetry**: Agregar instrumentación al stack de FastAPI, cliente LLM y conectores MySQL para generar trazas de ejecución.
- [x] **Tarea 4.2 - Stack de Monitoreo Dockerizado**: Incorporar herramientas como **Jaeger** (trazas) o **Prometheus/Grafana** (métricas) al entorno Docker Compose.
- **Entregable**: Capacidad gráfica para diagnosticar cuellos de botella exactos (ej. milisegundos invertidos en consultar la BD vs. milisegundos invertidos en el LLM).

### Etapa 5: Escalabilidad Horizontal (Redis & Swarm)
*Objetivo: Permitir que ACU-CORE corra en múltiples réplicas (nodos) sin pérdida de estado.*

- [x] **Tarea 5.1 - Estado Compartido en Redis**: Migración del Rate Limiter en memoria y la gestión de sesiones de agentes a un clúster Redis (`src/memory/redis_manager.py`), asegurando consistencia total.
- [x] **Tarea 5.2 - Orquestación de Producción**: Proveer manifiestos de Docker Swarm (`docker/docker-stack.yml`), separando estratégicamente las cargas de trabajo (Nodos LLM vs Nodos API).
- **Entregable**: Plataforma "Stateless" a nivel de API, capaz de balancear carga entre infinitas réplicas, respaldada por Redis y MySQL, lista para despliegues masivos.

---

## 📌 Prioridad Estratégica

La implementación debe ser **estrictamente secuencial**. Se comenzará con la **Etapa 1 (CI/CD)** para establecer la red de seguridad del código, seguida inmediatamente por la **Etapa 2 (Higiene de Datos)** para salvaguardar la integridad de la base de datos en producción.

---
*Documento autogenerado como planificación arquitectónica por el equipo de ingeniería.*

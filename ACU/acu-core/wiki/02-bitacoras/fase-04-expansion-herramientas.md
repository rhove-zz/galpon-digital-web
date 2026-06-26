# 🚀 Bitácora Fase 04: Expansión Cognitiva y de Herramientas (Tooling & Knowledge Expansion)

## 📌 Contexto de la Fase
Con la arquitectura base (ACU-CORE) refactorizada, dockerizada y escalable, el objetivo de esta fase es dotar al agente de la capacidad de interactuar con el entorno externo y comprender información no estructurada de manera masiva. Transformaremos un consultor aislado en un **Agente Autónomo Operativo**.

---

## 🚦 Roadmap de Implementación

### Etapa 1: Ingesta de Conocimiento Multimodal (BrainCore 2.0)
*Objetivo: Extender las capacidades RAG del agente para comprender el entorno corporativo vivo.*

- [x] **Tarea 1.1 - Pipeline RAG Multiformato:** Desarrollar conectores (`loaders`) en BrainCore para ingerir automáticamente archivos PDF, Word, CSV y código (Git).
- [x] **Tarea 1.2 - Ingesta Web Dinámica:** Desarrollar una nueva herramienta (Web Scraper/Crawler Tool) que permita al agente navegar una URL proveída en tiempo real, extraer texto y guardarlo en su memoria temporal.
- [x] **Tarea 1.3 - Sincronización Continua de Fuentes:** Implementar un demonio (Daemon/Scheduler) que monitoree carpetas locales o buckets en la nube para sincronizar la base de datos vectorial automáticamente tras cambios en archivos.
- **Entregable:** Un agente capaz de asimilar libros, repositorios y páginas web bajo demanda o por sincronización programada.

### Etapa 2: Suite de Herramientas Operativas (External Actuators)
*Objetivo: Otorgar "manos" al agente para interactuar con sistemas informáticos de terceros.*

- [x] **Tarea 2.1 - Módulo de Peticiones API REST (HTTP Client Tool):** Desarrollar la herramienta que autorice al agente a generar peticiones HTTP `GET`/`POST`, con inyección segura de credenciales (OAuth/API Keys), para comunicarse con herramientas externas (CRMs, Slack, etc.).
- [x] **Tarea 2.2 - Módulo de Gestión de Archivos (File System Tools):** Crear herramientas de solo-lectura y de escritura para crear, editar o eliminar archivos en un entorno de trabajo designado (Workspace Sandbox), útil para redacción de reportes o logs.
- [x] **Tarea 2.3 - Módulo de Análisis de Datos (Data Analysis Sandbox):** Otorgar capacidades matemáticas complejas permitiendo al agente ejecutar pequeños bloques de Python (`Pandas`) dentro de un Sandbox seguro para evaluar bases de datos extensas o datasets sin sobrecargar el LLM.
- **Entregable:** Un agente capaz de crear y editar archivos de texto, consumir APIs externas y realizar reportes analíticos complejos.

### Etapa 3: Seguridad y "Human-in-the-Loop"
*Objetivo: Garantizar la integridad del ecosistema frente a las nuevas habilidades operativas del agente.*

- [x] **Tarea 3.1 - Aprobación Interrumpida (Human-in-the-Loop):** Modificar el `AgentLoop` y el esquema SSE para pausar ejecuciones de herramientas "sensibles" (modificadoras de estado) y emitir un evento especial a la UI para pedir confirmación al usuario antes de proceder.
- [x] **Tarea 3.2 - Auditoría Detallada de Herramientas:** Ampliar el log de base de datos MySQL (`tool_execution_log`) para registrar con extrema exactitud el payload de salida enviado a APIs de terceros y el archivo editado en el file system.
- **Entregable:** Sistema robusto que restringe al agente ejecutar cambios no autorizados, delegando el poder destructivo o de impacto final a la confirmación de un humano.

### Etapa 4: Cognición Evolutiva (Task Decomposition & Personas)
*Objetivo: Refinar la capacidad del LLM para resolver prompts de alta complejidad funcional.*

- [x] **Tarea 4.1 - Memoria de Preferencias (Personas):** Permitir inyectar preferencias de usuario (almacenadas en Redis o MySQL) directamente en el System Prompt, ajustando longitud, nivel de formalidad o tecnicismo.
- [x] **Tarea 4.2 - Planificador de Tareas:** Para peticiones que superen cierto umbral de complejidad, obligar al agente (vía Prompt Engineering o framework de agentes múltiples) a generar un "Plan de Ejecución" antes de dar el primer paso operativo.
- **Entregable:** Interacciones hiper-personalizadas y éxito constante en tareas que requieren más de 5 pasos consecutivos o la orquestación de más de 3 herramientas distintas.

---

## 📝 Reglas de Oro para la Fase 04
1. **Sandboxing:** Ninguna herramienta debe permitir acceso irrestricto al sistema operativo host (`os.system` prohibido fuera del sandbox).
2. **Secretos Seguros:** Las credenciales que el agente utilice para consultar APIs externas NUNCA deben vivir en la memoria del agente ni inyectarse en el prompt del LLM; deben vivir en el `tools_manager` y aplicarse a nivel cliente HTTP.
3. **Fallas Aisladas (Graceful Degradation):** Si una herramienta falla (ej. la página Web a leer está caída), el agente debe ser instruido a reportarlo ordenadamente y sugerir alternativas, sin crashear el ciclo ReAct.

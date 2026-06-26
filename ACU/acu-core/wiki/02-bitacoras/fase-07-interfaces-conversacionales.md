# Fase 07: Interfaces Conversacionales Nativas

**Estado:** En Progreso 🚀
**Objetivo Principal:** Evolucionar la interacción del usuario final desde un panel de comandos tosco hacia una experiencia de Chat moderna, reactiva y enriquecida, centralizando el Human-in-the-Loop, configuraciones y despliegues en una sola interfaz.

---

## 🎯 Objetivos y Plan de Tareas

### Etapa 1: Interfaz de Chat Moderna (UI/UX)
*Objetivo: Reemplazar el panel estático por una ventana de chat estilo ChatGPT que soporte Markdown, código y métricas.*

- [x] **Tarea 1.1 - Maquetación y Componentes (HTML/CSS/JS):** Crear un layout de Chat (mensajes de usuario, mensajes del bot, panel lateral de hilos de conversación).
- [x] **Tarea 1.2 - Renderizado Enriquecido:** Integrar librerías nativas (ej. `marked.js` y `highlight.js`) para parsear respuestas del agente y mostrar código, tablas y formato de Markdown correctamente en el frontend.
- [x] **Tarea 1.3 - Conexión SSE Bi-direccional:** Modificar el frontend para que lea el flujo asíncrono (Streaming SSE) del agente y renderice las "fases de razonamiento" y "herramientas usadas" en tiempo real antes de la respuesta final.

### Etapa 2: Human-in-the-Loop UI (Autorizaciones en Chat)
*Objetivo: Migrar la lógica de validación de seguridad directamente a notificaciones interactivas en la conversación.*

- [x] **Tarea 2.1 - Tarjetas de Autorización:** Cuando el agente pausa por usar una herramienta sensible (API, Python, FileSystem), mostrar en el chat un widget visual con la herramienta a usar, los parámetros y botones de [Aprobar] o [Rechazar].
- [x] **Tarea 2.2 - Resolución de Estado:** Conectar los botones del frontend con los endpoints `/tools/pending/{tool_id}/approve` y `/reject`, reanudando el stream del agente de manera transparente sin recargar la página.

### Etapa 3: Gestión Visual de Webhooks y Roles
*Objetivo: Configurar el Swarm y los canales externos (Telegram/Slack) sin tocar código ni endpoints.*

- [x] **Tarea 3.1 - Panel de Webhooks UI:** Crear una sección en el dashboard lateral para registrar URLs, verificar firmas de webhooks y asociar agentes/roles específicos a diferentes canales.
- [x] **Tarea 3.2 - Despliegue Dinámico de Personas:** Habilitar un selector en el chat para cambiar de "Persona" (Arquitecto, Investigador, Soporte) al vuelo antes de enviar una consulta.

---

## 📝 Reglas de Oro para la Fase 07

1. **Vanilla Primero:** Para mantener las dependencias al mínimo (ya que no usamos frameworks JS como React en este proyecto), usar Vanilla JS bien estructurado y módulos ES6 limpios.
2. **Estética y Modernidad:** El chat debe verse premium (Dark mode elegante, transiciones suaves, tipografía legible, sombras sutiles, micro-animaciones).
3. **Robustez ante Errores:** Si el SSE se corta o hay error 500 en el backend, el chat debe mostrar un mensaje amigable y permitir reintentar sin romper la UI.

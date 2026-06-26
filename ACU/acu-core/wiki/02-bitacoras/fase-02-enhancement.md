# Bitacora Fase 2: Enhancement - API, BrainCore y Dashboard Operativo

**Fase**: 2 - Enhancement  
**Estado**: Completada operativamente  
**Fecha de actualizacion**: 2026-05-17  
**Version objetivo**: 1.1.0  

## Resumen

La Fase 2 convierte la base ReAct de ACU en un backend operativo con API REST, monitoreo, seguridad por roles y memoria BrainCore usable desde endpoints y dashboard.

El proyecto ya no esta solo en estado foundation. Actualmente cuenta con FastAPI, suite pytest, persistencia de sesiones, auditorias, API keys gestionadas, BrainCore con ingesta/busqueda/listado/eliminacion de fuentes, metricas operativas y un dashboard funcional para operar esas capacidades.

## Hitos Completados

### API REST

- `GET /health`
- `POST /chat`
- `GET /dashboard`
- `GET /sessions`
- `GET /sessions/{session_id}/context`
- `GET /tools/executions`
- `GET /api/access-log`

### Seguridad API

- API key estatica compatible con `ACU_API_KEY`.
- Mapa de claves por rol con `ACU_API_KEYS`.
- Roles operativos:
  - `admin`
  - `chat`
  - `braincore_read`
  - `braincore_write`
  - `monitoring`
- Claves API gestionadas en base de datos:
  - `GET /api/keys`
  - `POST /api/keys`
  - `POST /api/keys/{key_id}/revoke`
- Hash de claves, fingerprint y devolucion del secreto solo en creacion.
- Validacion estricta de `expires_at` para claves gestionadas.
- CORS configurable por allowlist.
- Limite configurable de payload por request.
- Rate limiting configurable en memoria por API key o IP.
- Auditoria persistente de accesos API.

### BrainCore

- Registro y listado de decisiones arquitectonicas:
  - `GET /braincore/decisions`
  - `POST /braincore/decisions`
- Ingesta local de archivos y directorios:
  - `POST /braincore/ingest`
- Busqueda contextual:
  - `POST /braincore/search`
- Inventario de fuentes indexadas:
  - `GET /braincore/sources`
- Eliminacion controlada de fuentes:
  - `DELETE /braincore/sources/{source_id}`
- Metricas agregadas:
  - `GET /braincore/metrics`
- Retrieval textual con fallback estable.
- Retrieval vectorial opcional con ChromaDB o FAISS.
- Limpieza best-effort del indice vectorial al eliminar fuentes.

### Dashboard Operativo

El dashboard en `/dashboard` permite:

- Ver health/status del servicio.
- Guardar API key localmente para llamadas protegidas.
- Chatear con ACU desde la UI.
- Ver sesiones y contexto conversacional.
- Ver auditoria de herramientas.
- Ver auditoria de acceso API.
- Ver, crear y revocar claves API gestionadas.
- Ver decisiones BrainCore.
- Buscar contexto BrainCore.
- Ingerir fuentes BrainCore.
- Listar fuentes indexadas.
- Eliminar fuentes indexadas.
- Ver metricas BrainCore: decisiones, fuentes, chunks, dominios y actividad reciente.
- Ver metricas de sistema, politicas runtime y estado del vector store.
- Mostrar mensajes accionables para errores 401, 403, 413, 429 y 422.
- Mantener historial visible de chat en pantalla.
- Mostrar tool calls en detalles expandibles.
- Copiar la clave API recien creada desde la UI.

Nota de continuidad Fase 3:

- El dashboard fue modularizado despues del cierre operativo de Fase 2.
- `src/api/dashboard.py` carga `templates/dashboard.html`.
- `/static/dashboard.css` y `/static/dashboard.js` contienen estilos y logica de cliente.

### Persistencia y Auditoria

- `agent_sessions`
- `conversation_context`
- `tool_execution_log`
- `api_access_log`
- `api_keys`
- `brain_decisions`
- `brain_sources`
- `brain_chunks`

### Tests

- Suite automatizada con pytest.
- Estado actual validado: `105 passed, 3 skipped`.
- Pruebas reales contra MySQL validadas como opt-in: `3 passed`.
- Cache de pytest desactivado para evitar fallos de permisos en entornos restringidos.
- Warning externo de `requests`/`chardet` filtrado en `pytest.ini` para mantener salida limpia cuando el entorno global no respeta `requirements.txt`.

## Archivos Principales Impactados

- `src/api/app.py`
- `src/api/schemas.py`
- `src/api/dashboard.py`
- `src/api/templates/dashboard.html`
- `src/api/static/dashboard.css`
- `src/api/static/dashboard.js`
- `src/braincore/manager.py`
- `src/braincore/ingestion.py`
- `src/braincore/vector_store.py`
- `src/memory/mysql_manager.py`
- `tests/test_api_app.py`
- `tests/test_mysql_manager.py`
- `tests/test_braincore_manager.py`
- `tests/test_braincore_vector_store.py`
- `README.md`
- `USAGE.md`
- `ARCHITECTURE.md`
- `PROJECT_STRUCTURE.md`
- `pytest.ini`

## Estado de Calidad

```bash
python -m pytest
python -m compileall src
```

Resultado esperado:

```text
105 passed, 3 skipped
```

## Pendientes Recomendados

1. Automatizar pruebas de integracion MySQL en CI.
2. Separar dependencias en `requirements-dev.txt` y opcionales vectoriales.
3. Mejorar UX del dashboard:
   - mensajes visuales avanzados de exito/error
4. Completar hardening de seguridad:
   - limites por rol y validaciones adicionales
5. Evaluar si el dashboard modularizado debe evolucionar a Jinja o frontend dedicado.
6. Definir observabilidad avanzada para despliegues multi-proceso.

## Cierre de Fase

La Fase 2 queda funcionalmente completada como backend/API/dashboard operativo. Las siguientes tareas pertenecen a una fase de hardening, modularizacion de frontend y automatizacion de integracion real.

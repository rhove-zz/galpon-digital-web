# ACU - Agente Cognitivo Universal v1.0

ACU es un orquestador de agente autonomo basado en ReAct (`Reason + Act`) que separa razonamiento, acceso a datos y memoria operativa.

## Estado actual

- LLM local via Ollama.
- Bucle ReAct con observacion, decision, accion y conclusion.
- Inyeccion dinamica del schema de MySQL en el prompt.
- Consultas SQL de solo lectura.
- Memoria evolutiva persistente en MySQL.
- Busqueda documental local con RAG vectorial opcional y fallback textual.
- Auditoria persistente de ejecucion de herramientas.
- Persistencia de sesiones y contexto conversacional.
- BrainCore Fase 1: registro de decisiones arquitectonicas.
- BrainCore Fase 2: ingesta local de fuentes y chunks.
- BrainCore Fase 3: retrieval textual sobre fuentes ingeridas.
- BrainCore Fase 4: retrieval semantico opcional con ChromaDB.
- BrainCore Fase 5: backend FAISS opcional para retrieval semantico local.
- Inventario consultable de fuentes BrainCore indexadas.
- Metricas agregadas BrainCore para monitoreo operativo.
- Metricas de sistema y estado del vector store para monitoreo runtime.
- Herramienta ReAct `buscar_contexto_braincore` integrada.
- Endpoints de sesiones y auditoria operativos.
- Dashboard de monitoreo operativo en FastAPI.
- API keys opcionales con roles para proteger endpoints operativos.
- Auditoria persistente de acceso API.
- Claves API gestionadas en BD con creacion y revocacion.

## Arquitectura resumida

```text
acu-core/
|- src/
|  |- agent/      # loop ReAct + prompting
|  |- llm/        # cliente Ollama
|  |- memory/     # MySQL + memoria evolutiva
|  |- tools/      # herramientas del agente
|  |- api/        # FastAPI app + endpoints REST
|  |- braincore/  # memoria agentica transversal
|  |- utils/      # logger + schemas
|- docker/        # compose + init.sql
|- main.py
```

## Requisitos

- Python 3.11+
- Ollama disponible en `http://localhost:11434` o configurado via `.env`
- MySQL accesible con:
  - usuario de lectura para SQL del agente
  - usuario de escritura para registrar memoria evolutiva

## Instalacion local

```bash
cd acu-core
python -m venv venv
venv\Scripts\activate
pip install -r requirements/dev.txt
copy .env.example .env
```

Edita `.env` con tus valores reales.

Perfiles disponibles:

| Perfil | Comando | Uso |
|--------|---------|-----|
| Base | `pip install -r requirements/base.txt` | Runtime API/CLI sin vector ni telemetria |
| Dev | `pip install -r requirements/dev.txt` | Desarrollo, lint, mypy y tests |
| Vector | `pip install -r requirements/vector.txt` | ChromaDB y embeddings |
| Vector FAISS | `pip install -r requirements/vector-faiss.txt` | FAISS + vector completo |
| Observability | `pip install -r requirements/observability.txt` | OpenTelemetry |
| Full | `pip install -r requirements.txt` | Compatibilidad: instala todos los perfiles |

## Ejecucion

```bash
python main.py
```

Modo demo:

```bash
python main.py --demo
```

Modo API:

```bash
uvicorn src.api.app:app --reload
```

Para proteger endpoints fuera del entorno local, define `ACU_API_KEY` o `ACU_API_KEYS` en `.env`.
Los clientes deben enviar `X-ACU-API-Key: <clave>` o `Authorization: Bearer <clave>`.

Health check:

```bash
curl http://localhost:8000/health
```

Dashboard:

```text
http://localhost:8000/dashboard
```

Chat:

```bash
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -H "X-ACU-API-Key: tu_clave_si_aplica" ^
  -d "{\"message\":\"Busca informacion sobre autenticacion\", \"domain\":\"generic\"}"
```

Registrar decision BrainCore:

```bash
curl -X POST http://localhost:8000/braincore/decisions ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Usar FastAPI\",\"context\":\"Necesitamos exponer ACU por API\",\"decision\":\"Mantener FastAPI como puente REST\",\"alternatives\":[\"Flask\"],\"impact\":\"Permite clientes externos\",\"domain\":\"acu\",\"tags\":[\"api\",\"braincore\"]}"
```

Ingerir fuentes BrainCore:

```bash
curl -X POST http://localhost:8000/braincore/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"path\":\"wiki\",\"source_type\":\"auto\",\"domain\":\"acu\"}"
```

Buscar contexto BrainCore:

```bash
curl -X POST http://localhost:8000/braincore/search ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"arquitectura fastapi\",\"domain\":\"acu\",\"top_k\":5}"
```

Si `VECTOR_SEARCH_ENABLED=true`, BrainCore indexa los chunks ingeridos en el backend configurado por `VECTOR_DB_ENGINE` (`chromadb` o `faiss`) y `POST /braincore/search` usa retrieval semantico. Si el backend vectorial no esta disponible, vuelve automaticamente al ranking textual MySQL/Python.

Listar fuentes BrainCore indexadas:

```bash
curl "http://localhost:8000/braincore/sources?domain=acu&source_type=markdown&limit=10"
```

Consultar metricas BrainCore:

```bash
curl "http://localhost:8000/braincore/metrics"
```

Consultar metricas de sistema:

```bash
curl "http://localhost:8000/system/metrics"
```

Validar readiness antes de exponer un ambiente:

```bash
python scripts/readiness_gate.py ^
  --url http://localhost:8000/system/readiness ^
  --api-key tu_clave_monitoring
```

Por defecto el gate bloquea `not_ready` y acepta `warning`; usa `--strict` para exigir `ready`.

Eliminar una fuente BrainCore indexada:

```bash
curl -X DELETE http://localhost:8000/braincore/sources/3
```

Monitoreo:

```bash
http://localhost:8000/dashboard
curl "http://localhost:8000/sessions?domain=acu&limit=10"
curl "http://localhost:8000/sessions/{session_id}/context?limit=20"
curl "http://localhost:8000/tools/executions?tool_name=buscar_contexto_braincore&limit=20"
curl "http://localhost:8000/braincore/sources?domain=acu&limit=20"
curl "http://localhost:8000/braincore/metrics"
curl "http://localhost:8000/system/metrics"
curl "http://localhost:8000/api/access-log?limit=20"
```

Crear una clave API gestionada:

```bash
curl -X POST http://localhost:8000/api/keys ^
  -H "Content-Type: application/json" ^
  -H "X-ACU-API-Key: clave_admin" ^
  -d "{\"name\":\"cliente chat\",\"roles\":[\"chat\"]}"
```

La respuesta incluye `api_key` una sola vez. ACU guarda solo el hash y la huella.
`expires_at` es opcional; si se envia, debe ser una fecha futura en formato ISO 8601 o `YYYY-MM-DD HH:MM:SS`.

## Pruebas

Ejecuta la suite local:

```bash
python -m pytest
```

La configuracion de `pytest.ini` ya fija `tests/` como ruta de pruebas y desactiva el cacheprovider para evitar fallos de permisos en entornos restringidos.

Las pruebas de integracion reales con MySQL son opt-in y se omiten por defecto:

```powershell
docker compose -f docker/docker-compose.yml up -d mysql
$env:ACU_RUN_MYSQL_INTEGRATION = "true"
python -m pytest -m integration_mysql
Remove-Item Env:\ACU_RUN_MYSQL_INTEGRATION
```

Por defecto usan el MySQL de Docker (`root`/`root`, `acu_reader`/`acu_secure_read_only`). Para apuntar a otra instancia usa `ACU_TEST_MYSQL_HOST`, `ACU_TEST_MYSQL_PORT`, `ACU_TEST_MYSQL_DATABASE`, `ACU_TEST_MYSQL_USER`, `ACU_TEST_MYSQL_PASSWORD`, `ACU_TEST_MYSQL_READ_ONLY_USER` y `ACU_TEST_MYSQL_READ_ONLY_PASSWORD`.

Si el puerto local `3306` ya esta ocupado, publica MySQL en otro puerto y apunta la prueba ahi:

```powershell
$env:MYSQL_HOST_PORT = "3307"
docker compose -f docker/docker-compose.yml up -d mysql
$env:ACU_RUN_MYSQL_INTEGRATION = "true"
$env:ACU_TEST_MYSQL_PORT = "3307"
python -m pytest -m integration_mysql
```

## Variables principales

```env
# Ollama
OLLAMA_HOST=http://localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=mistral

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=acu_db
MYSQL_READ_ONLY_USER=acu_reader
MYSQL_READ_ONLY_PASSWORD=
MYSQL_USER=root
MYSQL_PASSWORD=

# Agente
AGENT_MAX_ITERATIONS=10
AGENT_TEMPERATURE=0.3
AGENT_TOP_P=0.9

# API
ACU_API_AUTH_REQUIRED=false
ACU_API_KEY=
ACU_API_KEYS=chat_key=chat;monitor_key=monitoring;brain_key=braincore_read,braincore_write

# Busqueda documental
VECTOR_SEARCH_ENABLED=false
VECTOR_DB_ENGINE=chromadb  # chromadb o faiss
VECTOR_DB_PATH=./data/vectors
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

## Herramientas disponibles

### 1. `ejecutar_sql_lectura(query_sql)`

Ejecuta `SELECT` en MySQL y rechaza cualquier operacion que no sea de lectura.

```json
{
  "tool": "ejecutar_sql_lectura",
  "parameters": {
    "query_sql": "SELECT COUNT(*) AS total FROM usuarios WHERE activo = 1"
  }
}
```

### 2. `buscar_documentos(consulta_semantica, top_k=5)`

Busca fragmentos relevantes dentro de la documentacion local del proyecto. Hoy usa ranking textual sobre archivos como `README.md`, `ARCHITECTURE.md`, `USAGE.md`, `.sql` y notas tecnicas del repo.

```json
{
  "tool": "buscar_documentos",
  "parameters": {
    "consulta_semantica": "como configurar autenticacion LDAP",
    "top_k": 3
  }
}
```

### 3. `buscar_contexto_braincore(consulta, top_k=5, domain="generic", source_type="")`

Busca contexto en BrainCore: ADRs, wiki, codigo y fuentes ingeridas.

```json
{
  "tool": "buscar_contexto_braincore",
  "parameters": {
    "consulta": "decision arquitectura fastapi",
    "domain": "acu",
    "top_k": 3
  }
}
```

### 4. `registrar_leccion(categoria_sugerida, descripcion_regla)`

Guarda una leccion en la tabla `memoria_evolutiva`.

```json
{
  "tool": "registrar_leccion",
  "parameters": {
    "categoria_sugerida": "error_handling",
    "descripcion_regla": "Error 1054 suele indicar columnas o aliases invalidos en el SELECT"
  }
}
```

### 5. `consultar_lecciones_aprendidas(terminos_busqueda)`

Consulta lecciones persistidas en `memoria_evolutiva`.

```json
{
  "tool": "consultar_lecciones_aprendidas",
  "parameters": {
    "terminos_busqueda": "error 1054"
  }
}
```

## Base de datos

`docker/init.sql` crea las tablas base:

- `memoria_evolutiva`
- `tool_execution_log`
- `api_access_log`
- `api_keys`
- `agent_sessions`
- `conversation_context`
- `brain_decisions`
- `brain_sources`
- `brain_chunks`

La memoria evolutiva ya se usa de forma real para registrar y consultar lecciones.
`tool_execution_log` se usa para auditar cada invocacion de herramienta sin interrumpir el flujo si la auditoria falla.
`api_access_log` registra accesos autorizados y rechazados cuando la API key esta habilitada.
`api_keys` almacena claves gestionadas como hash, con roles, estado, expiracion y revocacion.
`agent_sessions` y `conversation_context` registran el ciclo de vida de cada sesion y sus intercambios.
El scheduler puede podar auditoria y contexto con `ACU_AUDIT_RETENTION_DAYS` y `ACU_CONVERSATION_RETENTION_DAYS`.
`brain_decisions` registra ADRs inteligentes para preservar el por que de decisiones tecnicas.
`brain_sources` y `brain_chunks` registran fuentes locales ingeridas y fragmentos hashados para recuperacion posterior.

## Alcance real de la busqueda documental

`buscar_documentos` trabaja en dos modos:

- por defecto indexa archivos locales, divide contenido en secciones y rankea por coincidencia textual
- si `VECTOR_SEARCH_ENABLED=true`, usa ChromaDB persistente con embeddings de `sentence-transformers`
- si el backend vectorial no esta disponible, vuelve automaticamente al ranking textual

En ambos casos devuelve snippets con metadata de origen.

BrainCore puede usar `VECTOR_DB_ENGINE=chromadb` o `VECTOR_DB_ENGINE=faiss`. Para FAISS instala la dependencia opcional `faiss-cpu`; el indice y su metadata se guardan en `VECTOR_DB_PATH`.

## Seguridad

- SQL del agente limitado a `SELECT`.
- Credenciales aisladas en `.env`.
- Separacion entre acceso read-only y read-write en MySQL.
- API key admin opcional con `ACU_API_KEY`.
- API keys por rol con `ACU_API_KEYS`, formato `clave=rol1,rol2;otra=admin`.
- API keys gestionadas en BD con `/api/keys`; se almacenan como hash y pueden revocarse.
- `ACU_API_AUTH_REQUIRED=true` mantiene la API protegida aunque solo uses claves gestionadas en BD.
- CORS configurable con `ACU_API_CORS_ORIGINS`; vacio mantiene CORS desactivado.
- Limite de payload configurable con `ACU_API_MAX_REQUEST_BODY_BYTES`; `0` lo desactiva.
- Rate limiting en memoria configurable con `ACU_API_RATE_LIMIT_REQUESTS`; `0` lo desactiva.
- `expires_at` de API keys gestionadas se valida y normaliza antes de persistir.
- Roles disponibles: `admin`, `chat`, `braincore_read`, `braincore_write`, `monitoring`.
- `braincore_read` permite listar decisiones, listar fuentes, consultar metricas y buscar contexto BrainCore.
- `braincore_write` permite registrar decisiones, ingerir fuentes, eliminar fuentes y tambien leer BrainCore.
- `monitoring` permite sesiones, contexto, auditoria de herramientas, auditoria API y metricas de sistema.
- HITL (`/tools/pending/*`) queda reservado a `admin`.
- `/`, `HEAD /`, `/health` y `/system/readiness` quedan publicos con respuesta minima/sanitizada.
- `/dashboard`, `/api/version` y OpenAPI requieren API key cuando la autenticacion esta activa; solo pueden quedar publicos con `ACU_ALLOW_OPERATIONAL_PUBLIC_ROUTES=true` en desarrollo local controlado.
- El dashboard muestra mensajes claros para errores de auth, payload, rate limit y validacion.
- La auditoria de acceso guarda huella de clave, roles, ruta, estado HTTP, IP y user-agent; no guarda la clave completa.
- Runbook de produccion: [wiki/04-decisiones/seguridad-operativa.md](wiki/04-decisiones/seguridad-operativa.md).
- Timeout configurable para llamadas al LLM.

## Contrato API

- La superficie REST actual se publica como contrato `v1`.
- `GET /api/version` devuelve version runtime, version de API, estabilidad y URL OpenAPI.
- Cada respuesta incluye `X-ACU-API-Version` y `X-ACU-API-Stability`.
- `/openapi.json` incluye metadata de versionado y politica de breaking changes.

## Gobierno BrainCore

- `GET /braincore/domains/{domain}/export` exporta decisiones, fuentes y chunks por dominio.
- `DELETE /braincore/domains/{domain}` elimina fuentes/chunks del dominio con `confirm={domain}`.
- `delete_decisions=true` elimina tambien decisiones del dominio; por defecto se conservan.
- Las limpiezas de fuente/dominio intentan limpiar tambien el vector store por `source_path`.

## Roadmap

- Fase 9.5 en curso: modularizacion de `app.py`/`mysql_manager.py` y pruebas funcionales de journeys criticos.
- Fase 10 propuesta: Prometheus/Grafana opt-in para historicos y alertas operativas.

## Referencias

- ReAct Pattern: https://arxiv.org/abs/2210.03629
- Ollama: https://ollama.ai
- MySQL: https://mysql.com
- ChromaDB: https://docs.trychroma.com
- FAISS: https://faiss.ai

## Licencia

Propiedad de RevoxeTech Software.

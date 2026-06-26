# Guia de Uso - ACU Agent

## Inicio rapido

### 1. Verifica dependencias

Ollama:

```bash
ollama serve
```

MySQL:

- debe existir la base `acu_db`
- debe existir `memoria_evolutiva`
- el `.env` debe incluir credenciales de lectura y escritura

### 2. Instala y configura

```bash
pip install -r requirements/dev.txt
copy .env.example .env
```

Para runtime minimo usa `requirements/base.txt`. Para capacidades vectoriales usa
`requirements/vector.txt` o `requirements/vector-faiss.txt`. Para telemetria usa
`requirements/observability.txt`. `requirements.txt` instala todos los perfiles.

### 3. Ejecuta

```bash
python main.py
```

Para levantar la API REST:

```bash
uvicorn src.api.app:app --reload
```

Si defines `ACU_API_KEY` o `ACU_API_KEYS` en `.env`, los endpoints operativos requieren:

```bash
X-ACU-API-Key: tu_clave
```

`ACU_API_KEY` otorga rol `admin`. Para multiples claves usa:

```env
ACU_API_KEYS=chat_key=chat;monitor_key=monitoring;brain_key=braincore_read,braincore_write
```

Para crear claves gestionadas en BD usa una clave `admin`:

```bash
curl -X POST http://localhost:8000/api/keys ^
  -H "Content-Type: application/json" ^
  -H "X-ACU-API-Key: clave_admin" ^
  -d "{\"name\":\"cliente monitoreo\",\"roles\":[\"monitoring\"]}"
```

Con expiracion:

```bash
curl -X POST http://localhost:8000/api/keys ^
  -H "Content-Type: application/json" ^
  -H "X-ACU-API-Key: clave_admin" ^
  -d "{\"name\":\"cliente temporal\",\"roles\":[\"chat\"],\"expires_at\":\"2099-06-01T00:00:00Z\"}"
```

La clave generada aparece como `api_key` solo en esa respuesta. Para revocarla:

```bash
curl -X POST http://localhost:8000/api/keys/{key_id}/revoke ^
  -H "X-ACU-API-Key: clave_admin"
```

Health check:

```bash
curl http://localhost:8000/health
```

Dashboard de monitoreo:

```text
http://localhost:8000/dashboard
```

Enviar mensaje al agente:

```bash
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -H "X-ACU-API-Key: tu_clave_si_aplica" ^
  -d "{\"message\":\"Cuantos usuarios activos tenemos?\", \"domain\":\"generic\"}"
```

Registrar una decision BrainCore:

```bash
curl -X POST http://localhost:8000/braincore/decisions ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Usar FastAPI\",\"context\":\"Necesitamos exponer ACU por API\",\"decision\":\"FastAPI sera el puente REST principal\",\"alternatives\":[\"Flask\"],\"impact\":\"Permite integracion con clientes externos\",\"domain\":\"acu\",\"tags\":[\"api\",\"braincore\"]}"
```

Listar decisiones BrainCore:

```bash
curl "http://localhost:8000/braincore/decisions?domain=acu&limit=10"
```

Ingerir una carpeta o archivo local en BrainCore:

```bash
curl -X POST http://localhost:8000/braincore/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"path\":\"wiki\",\"source_type\":\"auto\",\"domain\":\"acu\"}"
```

Listar fuentes BrainCore indexadas:

```bash
curl "http://localhost:8000/braincore/sources?domain=acu&source_type=markdown&limit=10"
```

Consultar metricas BrainCore:

```bash
curl "http://localhost:8000/braincore/metrics"
```

Consultar metricas de sistema y vector store:

```bash
curl "http://localhost:8000/system/metrics"
```

Validar readiness operativa:

```bash
python scripts/readiness_gate.py ^
  --url http://localhost:8000/system/readiness ^
  --api-key tu_clave_monitoring
```

El gate falla con `not_ready`. Para bloquear tambien `warning`, agrega `--strict`.

Eliminar una fuente BrainCore indexada:

```bash
curl -X DELETE http://localhost:8000/braincore/sources/3
```

Buscar contexto ingerido:

```bash
curl -X POST http://localhost:8000/braincore/search ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"arquitectura fastapi\",\"domain\":\"acu\",\"top_k\":5}"
```

Para usar retrieval semantico BrainCore, activa:

```env
VECTOR_SEARCH_ENABLED=True
VECTOR_DB_ENGINE=chromadb
```

Tambien puedes usar FAISS local:

```env
VECTOR_SEARCH_ENABLED=True
VECTOR_DB_ENGINE=faiss
```

FAISS requiere instalar la dependencia opcional `faiss-cpu`. Si ChromaDB, FAISS o el modelo de embeddings no estan disponibles, la API mantiene el fallback textual.

Monitoreo de sesiones y herramientas:

```bash
http://localhost:8000/dashboard
curl -H "X-ACU-API-Key: tu_clave_si_aplica" "http://localhost:8000/sessions?domain=acu&limit=10"
curl -H "X-ACU-API-Key: tu_clave_si_aplica" "http://localhost:8000/sessions/{session_id}/context?limit=20"
curl -H "X-ACU-API-Key: tu_clave_si_aplica" "http://localhost:8000/tools/executions?tool_name=buscar_contexto_braincore&limit=20"
curl -H "X-ACU-API-Key: tu_clave_si_aplica" "http://localhost:8000/braincore/sources?domain=acu&limit=20"
curl -H "X-ACU-API-Key: tu_clave_si_aplica" "http://localhost:8000/braincore/metrics"
curl -H "X-ACU-API-Key: tu_clave_si_aplica" "http://localhost:8000/system/metrics"
curl -H "X-ACU-API-Key: tu_clave_si_aplica" "http://localhost:8000/api/access-log?limit=20"
```

## Pruebas de integracion MySQL

La suite normal omite las pruebas reales contra MySQL. Para ejecutarlas con Docker:

```powershell
docker compose -f docker/docker-compose.yml up -d mysql
$env:ACU_RUN_MYSQL_INTEGRATION = "true"
python -m pytest -m integration_mysql
Remove-Item Env:\ACU_RUN_MYSQL_INTEGRATION
```

Credenciales por defecto del compose:

```text
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=acu_db
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_READ_ONLY_USER=acu_reader
MYSQL_READ_ONLY_PASSWORD=acu_secure_read_only
```

Para otra instancia real, define variables `ACU_TEST_MYSQL_*` equivalentes antes de ejecutar pytest.

Si el puerto `3306` ya esta ocupado:

```powershell
$env:MYSQL_HOST_PORT = "3307"
docker compose -f docker/docker-compose.yml up -d mysql
$env:ACU_RUN_MYSQL_INTEGRATION = "true"
$env:ACU_TEST_MYSQL_PORT = "3307"
python -m pytest -m integration_mysql
```

## Interaccion basica

```text
Tu: Cuantos usuarios activos tenemos?

Agente:
- observa el contexto
- decide ejecutar SQL
- consulta la base
- responde con el resultado
```

## Ejemplos utiles

### Ejemplo 1: inspeccion SQL

```text
Tu: Muestrame la estructura de la tabla usuarios
Agente -> ejecutar_sql_lectura(...)
```

### Ejemplo 2: tarea de varios pasos

```text
Tu: Cual es la distribucion de usuarios por departamento y sus tendencias semanales?

Agente:
1. genera plan interno
2. ejecuta consultas SQL
3. cruza informacion
4. responde
```

### Ejemplo 3: auto-correccion

```text
Tu: Lista todos los datos de categorias

Agente:
1. intenta una consulta
2. recibe error SQL
3. consulta lecciones previas si aplica
4. corrige la query
5. responde
```

### Ejemplo 4: aprendizaje y documentacion

```text
Tu: Como optimizar queries en la tabla de ventas?

Agente:
1. consultar_lecciones_aprendidas("sql optimization ventas")
2. buscar_contexto_braincore("decisiones previas sobre optimizacion ventas")
3. buscar_documentos("optimizacion de indices en mysql")
4. sintetizar hallazgos
5. registrar_leccion(...) si identifica una regla reusable
```

`buscar_documentos` consulta documentacion local del repositorio. Por defecto usa ranking textual. Si configuras `VECTOR_SEARCH_ENABLED=True`, usa ChromaDB con embeddings y vuelve al modo textual si el backend vectorial no esta disponible.
`buscar_contexto_braincore` consulta memoria agentica transversal: ADRs, fuentes ingeridas y contexto historico. BrainCore soporta `VECTOR_DB_ENGINE=chromadb` y `VECTOR_DB_ENGINE=faiss`.

## Modo demo

```bash
python main.py --demo
```

## Controles

- `salir`
- `exit`
- `quit`

## Logs

Niveles principales:

- `INFO`: eventos generales
- `DEBUG`: detalles internos
- `WARNING`: anomalías recuperables
- `ERROR`: fallos que requieren atención

Activa debug:

```env
DEBUG=True
LOG_LEVEL=DEBUG
```

## Configuracion recomendada

```env
AGENT_TEMPERATURE=0.3
AGENT_TOP_P=0.9
AGENT_MAX_ITERATIONS=10
ACU_API_KEY=
ACU_API_KEYS=
ACU_API_AUTH_REQUIRED=False
ACU_API_CORS_ORIGINS=
ACU_API_MAX_REQUEST_BODY_BYTES=0
ACU_API_RATE_LIMIT_REQUESTS=0
ACU_API_RATE_LIMIT_WINDOW_SECONDS=60
```

Si necesitas respuestas mas deterministas:

```env
AGENT_TEMPERATURE=0.1
AGENT_TOP_P=0.8
```

## Troubleshooting

### No conecta a Ollama

```text
No se pudo conectar a Ollama
```

Revisa:

- que `ollama serve` este corriendo
- que `OLLAMA_HOST` y `OLLAMA_PORT` sean correctos

### No conecta a MySQL

```text
No se pudo conectar a MySQL
```

Revisa:

- host, puerto y base en `.env`
- credenciales de lectura
- credenciales de escritura si usas memoria evolutiva

### La API responde 401

```text
API key requerida o invalida
```

Revisa:

- que `ACU_API_KEY` coincida con el header `X-ACU-API-Key`
- que si usas `ACU_API_KEYS`, el formato sea `clave=rol1,rol2;otra=admin`
- que el dashboard tenga la clave guardada en el campo `API key`
- que no estes enviando espacios antes o despues de la clave

En el dashboard, este error se muestra como una instruccion para guardar una clave valida.

### La API responde 403

```text
Rol insuficiente para este endpoint
```

Revisa:

- `chat` permite `POST /chat`
- `braincore_read` permite listar decisiones, listar fuentes, consultar metricas y buscar contexto BrainCore
- `braincore_write` permite registrar decisiones, ingerir fuentes y eliminar fuentes BrainCore
- `monitoring` permite sesiones, contexto, auditoria de herramientas, auditoria de acceso API y metricas de sistema
- `admin` permite todo

Si operas solo con claves gestionadas en BD, define `ACU_API_AUTH_REQUIRED=True` para que la API siga protegida aunque `ACU_API_KEY` y `ACU_API_KEYS` esten vacios.

En el dashboard, este error indica que la clave existe pero no tiene el rol necesario para esa seccion.

### La API responde 422 al crear una clave

Revisa:

- `roles` debe contener roles validos: `admin`, `chat`, `braincore_read`, `braincore_write`, `monitoring`
- `expires_at`, si se envia, debe ser futuro
- formatos aceptados de `expires_at`: ISO 8601 o `YYYY-MM-DD HH:MM:SS`

### La API responde 413

```text
Request body excede el limite configurado
```

Revisa:

- `ACU_API_MAX_REQUEST_BODY_BYTES`
- el tamano del JSON enviado al endpoint
- usa `0` para desactivar el limite en entornos locales controlados

### El navegador bloquea llamadas por CORS

Revisa:

- `ACU_API_CORS_ORIGINS`, por ejemplo `http://localhost:3000,http://127.0.0.1:3000`
- `ACU_API_CORS_METHODS`
- `ACU_API_CORS_HEADERS`

### La API responde 429

```text
Rate limit excedido
```

Revisa:

- `ACU_API_RATE_LIMIT_REQUESTS`
- `ACU_API_RATE_LIMIT_WINDOW_SECONDS`
- el header `Retry-After` de la respuesta
- usa `0` en `ACU_API_RATE_LIMIT_REQUESTS` para desactivar el limite en local

### La busqueda documental devuelve poco

Revisa:

- que existan archivos `.md`, `.txt` o `.sql` dentro del repo
- que la consulta use terminos concretos del dominio
- si esperas busqueda semantica, que `VECTOR_SEARCH_ENABLED=True` y que el modelo de embeddings este disponible
- si usas FAISS, que `faiss-cpu` este instalado en el entorno activo

### El agente tarda demasiado

Reduce:

```env
AGENT_MAX_ITERATIONS=5
AGENT_TEMPERATURE=0.2
```

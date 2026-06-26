# Gobierno BrainCore Por Dominio

**Fecha de actualizacion**: 2026-05-18  
**Estado**: politica operativa definida  
**Alcance**: exportacion, limpieza controlada y retencion de fuentes BrainCore.

## Objetivo

Evitar que BrainCore acumule conocimiento obsoleto sin control y, al mismo tiempo, impedir perdida accidental de memoria curada. BrainCore no usa poda automatica por fecha: se gobierna por dominio, fuente y decision explicita.

## Contrato Operativo

Endpoints:

| Endpoint | Rol | Proposito |
|----------|-----|-----------|
| `GET /braincore/domains/{domain}/export` | `braincore_read` | Exportar decisiones, fuentes y chunks de un dominio |
| `DELETE /braincore/domains/{domain}` | `braincore_write` | Eliminar fuentes de un dominio con confirmacion exacta |
| `DELETE /braincore/sources/{source_id}` | `braincore_write` | Eliminar una fuente puntual |

`DELETE /braincore/domains/{domain}` exige query param `confirm={domain}`. Sin confirmacion exacta, la API responde `422`.

## Exportacion

Ejemplo:

```bash
curl -H "X-ACU-API-Key: acu_xxx" \
  "http://localhost:8000/braincore/domains/acu/export?include_chunks=true"
```

El snapshot incluye:

- `domain`
- `decisions`
- `sources`
- `chunks`
- contadores `decisions_count`, `sources_count`, `chunks_count`

Usar `include_chunks=false` para inventario liviano antes de operar limpieza.

## Limpieza Controlada

Ejemplo:

```bash
curl -X DELETE -H "X-ACU-API-Key: acu_xxx" \
  "http://localhost:8000/braincore/domains/acu?confirm=acu&delete_decisions=false"
```

Comportamiento:

- Elimina fuentes `brain_sources` del dominio.
- Elimina chunks asociados en `brain_chunks`.
- Limpia registros vectoriales por `source_path`.
- Conserva `brain_decisions` salvo `delete_decisions=true`.

## Politica De Retencion

| Dato | Retencion | Motivo |
|------|-----------|--------|
| `brain_decisions` | Manual | Son decisiones curadas y deben sobrevivir a limpiezas de fuentes |
| `brain_sources` | Por dominio/fuente | Representan material indexado que puede quedar obsoleto |
| `brain_chunks` | Derivada de fuentes | Se elimina junto con la fuente o dominio |
| Vector store | Derivada de fuentes | Se elimina por `source_path` tras borrar fuente/dominio |

## Runbook

1. Exportar dominio con `include_chunks=true` si se necesita respaldo completo.
2. Revisar conteos de `sources_count` y `chunks_count`.
3. Eliminar fuentes puntuales si el alcance es pequeno.
4. Para limpieza masiva, ejecutar `DELETE /braincore/domains/{domain}?confirm={domain}`.
5. Usar `delete_decisions=true` solo si el dominio completo deja de existir.
6. Validar `GET /braincore/metrics` y busqueda `POST /braincore/search`.

## Riesgos

- Borrar un dominio elimina conocimiento recuperable por el agente.
- `delete_decisions=true` elimina memoria arquitectonica, no solo documentos.
- El vector store se limpia best-effort; si falla, revisar estado vectorial y reconstruir indice.
- Exportaciones con chunks pueden contener texto sensible; tratarlas como material confidencial.


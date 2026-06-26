# Versionado De Imagenes

**Fecha de actualizacion**: 2026-05-18  
**Estado**: politica operativa definida  
**Alcance**: publicacion GHCR, tags Docker y despliegues productivos.

## Objetivo

Evitar despliegues productivos ambiguos basados solo en `latest`. La imagen de ACU debe poder rastrearse hasta un commit y, para releases, hasta una version semantica.

## Politica De Tags

El workflow publica la imagen base:

```text
ghcr.io/${{ github.repository }}
```

Tags generados:

| Evento | Tags | Uso esperado |
|--------|------|--------------|
| Push a `main` | `latest`, `sha-<commit>` | Integracion continua y ambientes no criticos |
| Tag Git `vX.Y.Z` | `X.Y.Z`, `X.Y`, `X`, `sha-<commit>` | Releases productivos y rollback |

Ejemplo:

```text
git tag v1.5.0
git push origin v1.5.0
```

Publica:

```text
ghcr.io/revoxetech/acu-core:1.5.0
ghcr.io/revoxetech/acu-core:1.5
ghcr.io/revoxetech/acu-core:1
ghcr.io/revoxetech/acu-core:sha-<commit>
```

## Regla De Despliegue

Para produccion, fijar la imagen completa con `ACU_IMAGE`:

```env
ACU_IMAGE=ghcr.io/revoxetech/acu-core:1.5.0
```

`docker/docker-compose.prod.yml` y `docker/docker-stack.yml` usan esa variable en `acu-agent` y `acu-scheduler`. Si no se define, caen a:

```text
ghcr.io/revoxetech/acu-core:latest
```

Ese fallback existe para compatibilidad, no como recomendacion productiva.

## Flujo De Release

1. Ejecutar suite local: `ruff`, `mypy`, `pytest`.
2. Revisar changelog y bitacora de fase.
3. Crear tag semantico `vX.Y.Z`.
4. Empujar el tag para activar publicacion GHCR.
5. Desplegar usando `ACU_IMAGE=ghcr.io/revoxetech/acu-core:X.Y.Z`.
6. Validar `/health`.
7. Ejecutar `python scripts/readiness_gate.py --url <api>/system/readiness --api-key <monitoring_key>`.
8. Revisar `/system/metrics` si readiness devuelve `warning`.
9. Registrar version desplegada y commit SHA.

## Rollback

Rollback preferido:

```env
ACU_IMAGE=ghcr.io/revoxetech/acu-core:1.4.2
```

Usar `sha-<commit>` cuando se necesite reproducibilidad exacta de un build intermedio no promovido como release.

## Reglas Operativas

- `latest` no debe usarse como pin final de produccion.
- `sha-<commit>` es inmutable y util para diagnostico.
- `X.Y.Z` es el tag recomendado para despliegues estables.
- `X.Y` y `X` sirven para canales de compatibilidad, no para auditoria fina.
- `acu-agent` y `acu-scheduler` deben correr la misma imagen.

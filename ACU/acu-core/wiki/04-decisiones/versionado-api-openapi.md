# Versionado De API Y OpenAPI

**Fecha de actualizacion**: 2026-05-18  
**Estado**: politica operativa definida  
**Alcance**: superficie REST actual, metadata OpenAPI y compatibilidad de clientes.

## Objetivo

Fijar la superficie REST actual como contrato funcional `v1` sin duplicar rutas bajo `/v1` todavia. La API actual conserva sus rutas existentes para no romper dashboard ni clientes, pero publica explicitamente su version de contrato.

## Contrato Vigente

La API publica:

- Header `X-ACU-API-Version: v1`.
- Header `X-ACU-API-Stability: stable`.
- Endpoint publico `GET /api/version`.
- Metadata OpenAPI `info.x-acu-api-version`.
- Metadata OpenAPI `info.x-acu-api-stability`.
- Politica OpenAPI `info.x-acu-breaking-change-policy`.

`/openapi.json` es la fuente de verdad para generar clientes, validar schemas y revisar cambios de contrato.

## Politica De Compatibilidad

Cambios compatibles dentro de `v1`:

- Agregar endpoints nuevos.
- Agregar campos opcionales a respuestas.
- Agregar parametros opcionales con default.
- Ampliar enums o roles sin retirar valores existentes.
- Mejorar descripciones OpenAPI sin cambiar schema.

Cambios no compatibles:

- Eliminar endpoints o cambiar metodos HTTP.
- Renombrar campos existentes.
- Hacer requerido un campo antes opcional.
- Cambiar tipo de datos de un campo.
- Cambiar codigos HTTP esperados para flujos existentes.
- Alterar semantica de permisos por rol sin migracion.

Un cambio no compatible requiere una nueva version de contrato, por ejemplo `v2`, o un periodo de deprecacion documentado.

## Flujo De Release API

1. Ejecutar `python -m pytest`.
2. Revisar `/api/version`.
3. Revisar `/openapi.json`.
4. Comparar cambios de schema contra la version publicada anterior.
5. Documentar cambios compatibles en changelog.
6. Si hay cambio no compatible, abrir ADR de `v2`.

## Reglas Operativas

- El dashboard puede seguir usando rutas sin prefijo porque pertenecen al contrato `v1`.
- No se agrega `/v1` hasta que exista necesidad real de convivencia entre versiones.
- Las rutas publicas `/health`, `/api/version`, `/docs`, `/openapi.json`, `/redoc`, `/dashboard` y `/static/*` no deben exponer datos sensibles.
- Los clientes externos deben verificar `X-ACU-API-Version` o `GET /api/version` antes de asumir compatibilidad.
- Los tests de contrato deben fallar si desaparece metadata OpenAPI o el endpoint `/api/version`.


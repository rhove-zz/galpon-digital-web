from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_system_metrics_contract_documents_operational_fields():
    contract = (
        ROOT / "wiki/03-componentes/observabilidad-system-metrics.md"
    ).read_text(encoding="utf-8")

    assert "GET /system/metrics" in contract
    assert "X-ACU-API-Key" in contract
    for field in (
        '"vector_store"',
        '"pending_tools"',
        '"scheduler"',
        '"redis"',
        '"webhooks"',
    ):
        assert field in contract

    for threshold in (
        "vector_store.status",
        "pending_tools.pending",
        "scheduler.running",
        "redis.connected",
        "webhooks.total.rejected",
        "api_auth_required",
    ):
        assert threshold in contract


def test_wiki_links_system_metrics_contract():
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    components_readme = (ROOT / "wiki/03-componentes/README.md").read_text(
        encoding="utf-8"
    )

    assert "03-componentes/observabilidad-system-metrics.md" in wiki_readme
    assert "observabilidad-system-metrics.md" in components_readme


def test_functional_journeys_matrix_documents_critical_flows():
    matrix = (ROOT / "wiki/03-componentes/journeys-funcionales.md").read_text(
        encoding="utf-8"
    )
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    components_readme = (ROOT / "wiki/03-componentes/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "J-APIKEY-001",
        "J-BRAIN-001",
        "J-BRAIN-002",
        "J-HITL-001",
        "J-RETENTION-001",
        "J-READY-001",
        "test_api_key_functional_journey_create_use_revoke_then_rejects",
        "test_braincore_functional_journey_ingest_search_export_delete_domain",
        "test_hitl_functional_journey_reject_approve_execute_and_resume",
        "pytest -m integration_mysql",
    ):
        assert required_text in matrix

    assert "03-componentes/journeys-funcionales.md" in wiki_readme
    assert "journeys-funcionales.md" in components_readme


def test_security_runbook_documents_operational_controls():
    runbook = (ROOT / "wiki/04-decisiones/seguridad-operativa.md").read_text(
        encoding="utf-8"
    )
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    decisions_readme = (ROOT / "wiki/04-decisiones/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "ACU_API_AUTH_REQUIRED=True",
        "ACU_API_KEYS",
        "ACU_API_RATE_LIMIT_REQUESTS",
        "ACU_API_MAX_REQUEST_BODY_BYTES",
        "ACU_TELEGRAM_WEBHOOK_SECRET",
        "ACU_SLACK_SIGNING_SECRET",
        "GET /system/readiness",
        "/tools/pending/{tool_id}/approve",
        "/api/access-log",
        "admin",
        "monitoring",
        "chat",
    ):
        assert required_text in runbook

    assert "04-decisiones/seguridad-operativa.md" in wiki_readme
    assert "seguridad-operativa.md" in decisions_readme


def test_readiness_contract_documents_runtime_gate():
    contract = (ROOT / "wiki/03-componentes/readiness-operativa.md").read_text(
        encoding="utf-8"
    )
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    components_readme = (ROOT / "wiki/03-componentes/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "GET /system/readiness",
        "monitoring",
        "ready",
        "warning",
        "not_ready",
        "api_auth_required",
        "rate_limit_enabled",
        "payload_limit_enabled",
        "cors_restricted",
        "redis_connected",
        "api_contract",
        "scripts/readiness_gate.py",
        "--strict",
    ):
        assert required_text in contract

    assert "03-componentes/readiness-operativa.md" in wiki_readme
    assert "readiness-operativa.md" in components_readme


def test_retention_runbook_documents_pruning_contract():
    runbook = (ROOT / "wiki/04-decisiones/retencion-auditoria-contexto.md").read_text(
        encoding="utf-8"
    )
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    decisions_readme = (ROOT / "wiki/04-decisiones/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "ACU_AUDIT_RETENTION_DAYS",
        "ACU_CONVERSATION_RETENTION_DAYS",
        "tool_execution_log",
        "api_access_log",
        "conversation_context",
        "agent_sessions",
        "prune_logs_job",
        "ACU_SCHEDULER_MODE=worker",
    ):
        assert required_text in runbook
        assert required_text in env_example or required_text in runbook

    assert "ACU_AUDIT_RETENTION_DAYS" in env_example
    assert "ACU_CONVERSATION_RETENTION_DAYS" in env_example
    assert "04-decisiones/retencion-auditoria-contexto.md" in wiki_readme
    assert "retencion-auditoria-contexto.md" in decisions_readme


def test_api_versioning_runbook_documents_openapi_contract():
    runbook = (ROOT / "wiki/04-decisiones/versionado-api-openapi.md").read_text(
        encoding="utf-8"
    )
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    decisions_readme = (ROOT / "wiki/04-decisiones/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "GET /api/version",
        "X-ACU-API-Version: v1",
        "X-ACU-API-Stability: stable",
        "info.x-acu-api-version",
        "info.x-acu-api-stability",
        "info.x-acu-breaking-change-policy",
        "/openapi.json",
        "v2",
    ):
        assert required_text in runbook

    assert "04-decisiones/versionado-api-openapi.md" in wiki_readme
    assert "versionado-api-openapi.md" in decisions_readme


def test_multi_replica_metrics_runbook_documents_redis_contract():
    runbook = (ROOT / "wiki/04-decisiones/metricas-multireplica.md").read_text(
        encoding="utf-8"
    )
    system_metrics = (
        ROOT / "wiki/03-componentes/observabilidad-system-metrics.md"
    ).read_text(encoding="utf-8")
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    decisions_readme = (ROOT / "wiki/04-decisiones/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "webhook_metrics:{channel}",
        "GET /system/metrics",
        "ACU_REDIS_URL",
        "telegram",
        "slack",
        "Prometheus/Grafana",
    ):
        assert required_text in runbook

    assert "fallback local por proceso" in system_metrics
    assert "04-decisiones/metricas-multireplica.md" in wiki_readme
    assert "metricas-multireplica.md" in decisions_readme


def test_phase_09_closure_documents_phase_10_boundary():
    closure = (ROOT / "wiki/04-decisiones/cierre-fase-09.md").read_text(
        encoding="utf-8"
    )
    phase_09 = (
        ROOT / "wiki/02-bitacoras/fase-09-operacion-observabilidad.md"
    ).read_text(encoding="utf-8")
    phase_10 = (
        ROOT / "wiki/02-bitacoras/fase-10-observabilidad-historica.md"
    ).read_text(encoding="utf-8")
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    decisions_readme = (ROOT / "wiki/04-decisiones/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "Fase 9 se considera cerrada",
        "157 passed, 4 skipped",
        "Prometheus/Grafana no entra en Fase 9",
        "Fase 10",
        "scripts/readiness_gate.py",
    ):
        assert required_text in closure

    for required_text in (
        "Cerrada operativamente",
        "cierre-fase-09.md",
        "fase-10-observabilidad-historica.md",
    ):
        assert required_text in phase_09

    for required_text in (
        "Prometheus/Grafana",
        "Exportador Prometheus opt-in",
        "Dashboard Grafana",
        "politica de cardinalidad",
    ):
        assert required_text in phase_10

    assert "04-decisiones/cierre-fase-09.md" in wiki_readme
    assert "cierre-fase-09.md" in decisions_readme


def test_phase_09_5_documents_functional_stabilization_scope():
    phase = (
        ROOT / "wiki/02-bitacoras/fase-09-5-estabilizacion-funcional.md"
    ).read_text(encoding="utf-8")
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    bitacoras_readme = (ROOT / "wiki/02-bitacoras/README.md").read_text(
        encoding="utf-8"
    )
    project_structure = (ROOT / "PROJECT_STRUCTURE.md").read_text(encoding="utf-8")
    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")

    for required_text in (
        "Fase 09.5",
        "Cerrada funcionalmente",
        "Cierre De Fase",
        "MySQL real",
        "src/api/readiness.py",
        "src/api/security.py",
        "src/api/routes/api_keys.py",
        "src/api/routes/system.py",
        "src/api/routes/chat.py",
        "src/api/routes/braincore.py",
        "src/api/routes/monitoring.py",
        "src/api/routes/tools.py",
        "src/api/agent_runtime.py",
        "src/memory/repositories/audit.py",
        "src/memory/repositories/api_keys.py",
        "src/memory/repositories/brain_decisions.py",
        "src/memory/repositories/brain_domains.py",
        "src/memory/repositories/brain_metrics.py",
        "src/memory/repositories/brain_search.py",
        "src/memory/repositories/brain_sources.py",
        "src/memory/repositories/lessons.py",
        "src/memory/repositories/sessions.py",
        "src/memory/repositories/sql_runtime.py",
        "app.py",
        "mysql_manager.py",
        "412",
        "465",
        "Pruebas Funcionales",
        "Seguridad API y RBAC",
        "241 passed, 4 skipped",
    ):
        assert required_text in phase

    assert "02-bitacoras/fase-09-5-estabilizacion-funcional.md" in wiki_readme
    assert "fase-09-5-estabilizacion-funcional.md" in bitacoras_readme
    assert "src/api/readiness.py" in project_structure
    assert "src/api/security.py" in project_structure
    assert "src/api/routes/api_keys.py" in project_structure
    assert "src/api/routes/system.py" in project_structure
    assert "src/api/routes/chat.py" in project_structure
    assert "src/api/routes/braincore.py" in project_structure
    assert "src/api/routes/monitoring.py" in project_structure
    assert "src/api/routes/tools.py" in project_structure
    assert "src/api/agent_runtime.py" in project_structure
    assert "src/memory/repositories/audit.py" in project_structure
    assert "src/memory/repositories/api_keys.py" in project_structure
    assert "src/memory/repositories/brain_decisions.py" in project_structure
    assert "src/memory/repositories/brain_domains.py" in project_structure
    assert "src/memory/repositories/brain_metrics.py" in project_structure
    assert "src/memory/repositories/brain_search.py" in project_structure
    assert "src/memory/repositories/brain_sources.py" in project_structure
    assert "src/memory/repositories/lessons.py" in project_structure
    assert "src/memory/repositories/sessions.py" in project_structure
    assert "src/memory/repositories/sql_runtime.py" in project_structure
    assert "src/api/readiness.py" in architecture
    assert "src/api/security.py" in architecture
    assert "src/api/routes/api_keys.py" in architecture
    assert "src/api/routes/system.py" in architecture
    assert "src/api/routes/chat.py" in architecture
    assert "src/api/routes/braincore.py" in architecture
    assert "src/api/routes/monitoring.py" in architecture
    assert "src/api/routes/tools.py" in architecture
    assert "src/api/agent_runtime.py" in architecture
    assert "src/memory/repositories/audit.py" in architecture
    assert "src/memory/repositories/api_keys.py" in architecture
    assert "src/memory/repositories/brain_decisions.py" in architecture
    assert "src/memory/repositories/brain_domains.py" in architecture
    assert "src/memory/repositories/brain_metrics.py" in architecture
    assert "src/memory/repositories/brain_search.py" in architecture
    assert "src/memory/repositories/brain_sources.py" in architecture
    assert "src/memory/repositories/lessons.py" in architecture
    assert "src/memory/repositories/sessions.py" in architecture
    assert "src/memory/repositories/sql_runtime.py" in architecture


def test_braincore_governance_runbook_documents_domain_controls():
    runbook = (ROOT / "wiki/04-decisiones/gobierno-braincore.md").read_text(
        encoding="utf-8"
    )
    wiki_readme = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
    decisions_readme = (ROOT / "wiki/04-decisiones/README.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "GET /braincore/domains/{domain}/export",
        "DELETE /braincore/domains/{domain}",
        "confirm={domain}",
        "include_chunks",
        "braincore_read",
        "braincore_write",
        "delete_decisions=true",
        "brain_sources",
        "brain_chunks",
        "Vector store",
    ):
        assert required_text in runbook

    assert "04-decisiones/gobierno-braincore.md" in wiki_readme
    assert "gobierno-braincore.md" in decisions_readme

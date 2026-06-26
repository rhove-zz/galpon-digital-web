from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_dockerfile_runs_fastapi_and_checks_api_health():
    dockerfile = _read("docker/Dockerfile")
    dockerignore = _read(".dockerignore")

    assert "uvicorn" in dockerfile
    assert "src.api.app:app" in dockerfile
    assert "0.0.0.0" in dockerfile
    assert "localhost:8000/health" in dockerfile
    assert "localhost:11434/api/tags" not in dockerfile
    assert ".pytest_cache" in dockerignore
    assert "pytest-cache-files-*" in dockerignore
    assert "data" in dockerignore
    assert "logs" in dockerignore


def test_local_compose_exposes_api_and_defines_healthchecks():
    compose = _read("docker/docker-compose.yml")

    assert '"8000:8000"' in compose
    assert "condition: service_healthy" in compose
    for service in (
        "ollama:",
        "mysql:",
        "redis:",
        "jaeger:",
        "acu-agent:",
        "acu-scheduler:",
    ):
        assert service in compose
    for probe in (
        'ollama", "list',
        "mysqladmin ping",
        'redis-cli", "ping',
        "localhost:16686",
        "localhost:8000/health",
        "socket.create_connection(('mysql', 3306)",
    ):
        assert probe in compose


def test_production_compose_and_stack_define_service_healthchecks():
    prod = _read("docker/docker-compose.prod.yml")
    stack = _read("docker/docker-stack.yml")

    assert "${ACU_IMAGE:-ghcr.io/revoxetech/acu-core:latest}" in prod
    assert "${ACU_IMAGE:-ghcr.io/revoxetech/acu-core:latest}" in stack
    assert "myregistry.local/acu-agent:latest" not in stack

    for content in (prod, stack):
        assert "mysqladmin ping" in content
        assert 'redis-cli", "ping' in content
        assert 'ollama", "list' in content
        assert "localhost:8000/health" in content
        assert "socket.create_connection(('mysql', 3306)" in content
        assert "localhost:16686" in content
        assert "ACU_AUDIT_RETENTION_DAYS" in content
        assert "ACU_CONVERSATION_RETENTION_DAYS" in content


def test_ci_workflow_validates_and_publishes_docker_image():
    workflow = _read(".github/workflows/ci.yml")

    assert 'tags: ["v*.*.*"]' in workflow
    assert "docker-validation:" in workflow
    assert "docker compose -f docker/docker-compose.yml config --quiet" in workflow
    assert "docker compose -f docker/docker-compose.prod.yml config --quiet" in workflow
    assert "docker compose -f docker/docker-stack.yml config --quiet" in workflow
    assert "docker build" in workflow
    assert "acu-core:ci" in workflow
    assert "http://127.0.0.1:8000/health" in workflow
    assert "scripts/readiness_gate.py" in workflow
    assert "http://127.0.0.1:8000/system/readiness" in workflow
    assert 'ACU_API_KEYS="smoke-monitor=monitoring"' in workflow
    assert "docker/metadata-action@v5" in workflow
    assert "type=raw,value=latest,enable={{is_default_branch}}" in workflow
    assert "type=sha,format=long" in workflow
    assert "type=semver,pattern={{version}}" in workflow
    assert "type=semver,pattern={{major}}.{{minor}}" in workflow
    assert "tags: ${{ steps.meta.outputs.tags }}" in workflow
    assert "ghcr.io/${{ github.repository }}/acu-core:latest" not in workflow


def test_semantic_image_versioning_is_documented_for_deployments():
    env_example = _read(".env.example")
    runbook = _read("wiki/04-decisiones/versionado-imagenes.md")
    wiki_readme = _read("wiki/README.md")

    assert "ACU_IMAGE=ghcr.io/revoxetech/acu-core:1.5.0" in env_example
    assert "ACU_IMAGE=ghcr.io/revoxetech/acu-core:X.Y.Z" in runbook
    assert "scripts/readiness_gate.py" in runbook
    assert "git tag v1.5.0" in runbook
    assert "latest` no debe usarse como pin final de produccion" in runbook
    assert "04-decisiones/versionado-imagenes.md" in wiki_readme


def test_observability_profile_pins_opentelemetry_stack():
    requirements = _read("requirements/observability.txt")

    assert "opentelemetry-api==1.20.0" in requirements
    assert "opentelemetry-sdk==1.20.0" in requirements
    assert "opentelemetry-exporter-otlp==1.20.0" in requirements
    assert "opentelemetry-instrumentation-fastapi==0.41b0" in requirements

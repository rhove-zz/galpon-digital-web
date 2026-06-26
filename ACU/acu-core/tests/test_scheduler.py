from src.api import scheduler as scheduler_module
from src.config.settings import system_config


class FakeScheduler:
    def __init__(self, running=False):
        self.running = running
        self.jobs = []
        self.start_calls = 0
        self.shutdown_calls = 0

    def add_job(self, func, trigger, id, replace_existing):
        self.jobs.append(
            {
                "func": func,
                "trigger": trigger,
                "id": id,
                "replace_existing": replace_existing,
            }
        )

    def start(self):
        self.start_calls += 1
        self.running = True

    def shutdown(self, wait=False):
        self.shutdown_calls += 1
        self.running = False


class FakePruningConnector:
    def __init__(self, use_read_only=False):
        self.use_read_only = use_read_only
        self.calls = []
        self.disconnect_calls = 0

    def connect(self):
        return True

    def prune_tool_execution_log(self, older_than_days):
        self.calls.append(("tool_execution_log", older_than_days))
        return {"success": True, "rows_deleted": 1}

    def prune_api_access_log(self, older_than_days):
        self.calls.append(("api_access_log", older_than_days))
        return {"success": True, "rows_deleted": 2}

    def prune_conversation_context(self, older_than_days):
        self.calls.append(("conversation_context", older_than_days))
        return {"success": True, "rows_deleted": 3}

    def prune_agent_sessions(self, older_than_days):
        self.calls.append(("agent_sessions", older_than_days))
        return {"success": True, "rows_deleted": 4}

    def disconnect(self):
        self.disconnect_calls += 1


def test_scheduler_should_start_by_context(monkeypatch):
    monkeypatch.setattr(system_config, "scheduler_mode", "disabled")
    assert scheduler_module.scheduler_should_start("api") is False
    assert scheduler_module.scheduler_should_start("worker") is False

    monkeypatch.setattr(system_config, "scheduler_mode", "api")
    assert scheduler_module.scheduler_should_start("api") is True
    assert scheduler_module.scheduler_should_start("worker") is False

    monkeypatch.setattr(system_config, "scheduler_mode", "worker")
    assert scheduler_module.scheduler_should_start("api") is False
    assert scheduler_module.scheduler_should_start("worker") is True

    monkeypatch.setattr(system_config, "scheduler_mode", "all")
    assert scheduler_module.scheduler_should_start("api") is True
    assert scheduler_module.scheduler_should_start("worker") is True


def test_start_scheduler_disabled_does_not_register_jobs(monkeypatch):
    fake_scheduler = FakeScheduler()
    monkeypatch.setattr(system_config, "scheduler_mode", "disabled")
    monkeypatch.setattr(scheduler_module, "scheduler", fake_scheduler)

    started = scheduler_module.start_scheduler(context="api")

    assert started is False
    assert fake_scheduler.jobs == []
    assert fake_scheduler.start_calls == 0


def test_start_scheduler_registers_jobs_once(monkeypatch):
    fake_scheduler = FakeScheduler()
    monkeypatch.setattr(system_config, "scheduler_mode", "worker")
    monkeypatch.setattr(scheduler_module, "scheduler", fake_scheduler)

    started = scheduler_module.start_scheduler(context="worker")
    second_start = scheduler_module.start_scheduler(context="worker")

    assert started is True
    assert second_start is True
    assert fake_scheduler.start_calls == 1
    assert [job["id"] for job in fake_scheduler.jobs] == [
        "prune_logs_job",
        "braincore_sync_job",
    ]


def test_shutdown_scheduler_only_when_running(monkeypatch):
    fake_scheduler = FakeScheduler(running=True)
    monkeypatch.setattr(scheduler_module, "scheduler", fake_scheduler)

    scheduler_module.shutdown_scheduler()
    scheduler_module.shutdown_scheduler()

    assert fake_scheduler.shutdown_calls == 1


def test_run_pruning_jobs_applies_audit_and_conversation_retention(monkeypatch):
    connectors = []

    def fake_connector_factory(use_read_only=False):
        connector = FakePruningConnector(use_read_only=use_read_only)
        connectors.append(connector)
        return connector

    monkeypatch.setattr(system_config, "audit_retention_days", 30)
    monkeypatch.setattr(system_config, "conversation_retention_days", 90)
    monkeypatch.setattr(scheduler_module, "MySQLConnector", fake_connector_factory)

    scheduler_module.run_pruning_jobs()

    assert len(connectors) == 1
    assert connectors[0].use_read_only is False
    assert connectors[0].calls == [
        ("tool_execution_log", 30),
        ("api_access_log", 30),
        ("conversation_context", 90),
        ("agent_sessions", 90),
    ]
    assert connectors[0].disconnect_calls == 1

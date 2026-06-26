import json

from scripts import readiness_gate


class FakeUrlopenResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_readiness_gate_accepts_warning_by_default(monkeypatch):
    monkeypatch.setattr(
        readiness_gate.urllib.request,
        "urlopen",
        lambda request, timeout: FakeUrlopenResponse(
            {"status": "warning", "summary": {"passed": 8, "warnings": 1, "failed": 0}}
        ),
    )

    exit_code = readiness_gate.main(
        [
            "--url",
            "http://acu.local/system/readiness",
            "--api-key",
            "monitor-key",
            "--retries",
            "1",
        ]
    )

    assert exit_code == 0


def test_readiness_gate_rejects_warning_when_strict(monkeypatch):
    monkeypatch.setattr(
        readiness_gate.urllib.request,
        "urlopen",
        lambda request, timeout: FakeUrlopenResponse(
            {"status": "warning", "summary": {"passed": 8, "warnings": 1, "failed": 0}}
        ),
    )

    exit_code = readiness_gate.main(
        [
            "--url",
            "http://acu.local/system/readiness",
            "--retries",
            "1",
            "--strict",
        ]
    )

    assert exit_code == 1


def test_readiness_gate_rejects_not_ready(monkeypatch):
    monkeypatch.setattr(
        readiness_gate.urllib.request,
        "urlopen",
        lambda request, timeout: FakeUrlopenResponse(
            {
                "status": "not_ready",
                "summary": {"passed": 6, "warnings": 0, "failed": 1},
                "checks": [
                    {
                        "name": "api_auth_required",
                        "status": "fail",
                        "detail": "ACU_API_AUTH_REQUIRED debe estar habilitado",
                    }
                ],
            }
        ),
    )

    exit_code = readiness_gate.main(
        ["--url", "http://acu.local/system/readiness", "--retries", "1"]
    )

    assert exit_code == 1

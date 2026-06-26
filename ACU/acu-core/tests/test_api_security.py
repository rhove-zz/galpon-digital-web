from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api import security


def test_build_api_key_roles_merges_legacy_admin_and_role_map():
    roles = security.build_api_key_roles(
        api_key="legacy-key",
        api_keys={
            "legacy-key": ["chat"],
            "monitor-key": ["monitoring"],
        },
    )

    assert roles["legacy-key"] == {"admin", "chat"}
    assert roles["monitor-key"] == {"monitoring"}


def test_required_roles_and_role_inheritance():
    assert security.required_roles("POST", "/chat") == {"chat"}
    assert security.required_roles("GET", "/system/readiness") == {"monitoring"}
    assert security.required_roles("DELETE", "/braincore/domains/acu") == {
        "braincore_write"
    }
    assert security.required_roles("GET", "/unknown") == {"admin"}
    assert security.has_required_role({"admin"}, {"monitoring"})
    assert security.has_required_role({"braincore_write"}, {"braincore_read"})
    assert not security.has_required_role({"chat"}, {"monitoring"})


def test_extract_api_key_supports_header_and_bearer():
    header_request = SimpleNamespace(
        headers={"x-acu-api-key": "header-key", "authorization": "Bearer bearer-key"}
    )
    bearer_request = SimpleNamespace(headers={"authorization": "Bearer bearer-key"})

    assert security.extract_api_key(header_request) == "header-key"
    assert security.extract_api_key(bearer_request) == "bearer-key"


def test_hash_and_fingerprint_are_stable_without_exposing_secret():
    key_hash = security.hash_key("secret")
    fingerprint = security.fingerprint_key("secret")

    assert len(key_hash) == 64
    assert fingerprint == key_hash[:16]
    assert "secret" not in key_hash


def test_normalize_api_key_expires_at_rejects_invalid_and_past_values():
    assert security.normalize_api_key_expires_at("2999-01-01T00:00:00Z") == (
        "2999-01-01 00:00:00"
    )

    with pytest.raises(HTTPException):
        security.normalize_api_key_expires_at("not-a-date")

    with pytest.raises(HTTPException):
        security.normalize_api_key_expires_at("2000-01-01T00:00:00Z")


def test_resolve_api_key_prefers_static_keys_before_managed_lookup():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                api_keys={"static-key": {"chat"}},
                api_key_provider=lambda: None,
            )
        )
    )

    identity = security.resolve_api_key(request, "static-key")

    assert identity == {
        "roles": {"chat"},
        "fingerprint": security.fingerprint_key("static-key"),
    }

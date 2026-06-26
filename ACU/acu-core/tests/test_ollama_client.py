from unittest.mock import Mock

import requests

from src.llm import ollama_client


def test_generate_response_uses_agent_defaults(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"message": {"content": "ok"}}
        return response

    monkeypatch.setattr(ollama_client.agent_config, "temperature", 0.42)
    monkeypatch.setattr(ollama_client.agent_config, "top_p", 0.77)
    monkeypatch.setattr(ollama_client.requests, "post", fake_post)

    client = ollama_client.OllamaClient()
    result = client.generate_response(
        system_prompt="system",
        user_message="hello",
        conversation_history=[{"role": "assistant", "content": "previous"}],
    )

    assert result == "ok"
    assert captured["payload"]["options"]["temperature"] == 0.42
    assert captured["payload"]["options"]["top_p"] == 0.77
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["messages"][-1]["content"] == "hello"


def test_generate_response_returns_none_on_timeout(monkeypatch):
    def fake_post(url, json, timeout):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(ollama_client.requests, "post", fake_post)

    client = ollama_client.OllamaClient()
    result = client.generate_response(
        system_prompt="system",
        user_message="hello",
    )

    assert result is None


def test_parse_tool_calls_handles_none():
    client = ollama_client.OllamaClient()
    assert client.parse_tool_calls(None) == []


def test_parse_tool_calls_extracts_valid_json():
    response = """
Texto libre
<tool>
{"tool": "ejecutar_sql_lectura", "parameters": {"query_sql": "SELECT 1"}}
</tool>
<tool>
{invalid json}
</tool>
"""

    client = ollama_client.OllamaClient()
    tool_calls = client.parse_tool_calls(response)

    assert len(tool_calls) == 1
    assert tool_calls[0]["tool"] == "ejecutar_sql_lectura"
    assert tool_calls[0]["parameters"]["query_sql"] == "SELECT 1"

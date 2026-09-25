from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from faq_agent.api import documents
from faq_agent.api.routes import create_app


@pytest.mark.parametrize("body", [{"name": "My FAQ"}, {"name": "ab"}, {}, {"name": 123}])
def test_real_library_dependency_preserves_validation(monkeypatch, body):
    library = Mock()
    monkeypatch.setattr(documents, "Library", lambda settings: library)
    with TestClient(create_app()) as client:
        response = client.post("/collections", json=body)
    assert response.status_code == 422
    library.create.assert_not_called()
    library.close.assert_called_once()


def test_real_library_dependency_keeps_provider_errors_private(monkeypatch):
    library = Mock()
    library.create.side_effect = RuntimeError("private provider details")
    monkeypatch.setattr(documents, "Library", lambda settings: library)
    with TestClient(create_app()) as client:
        response = client.post("/collections", json={"name": "valid_name"})
    assert response.status_code == 503
    assert "private provider details" not in response.text


def test_real_library_dependency_accepts_valid_name(monkeypatch):
    library = Mock()
    library.create.return_value = {"id": "valid_name"}
    monkeypatch.setattr(documents, "Library", lambda settings: library)
    with TestClient(create_app()) as client:
        response = client.post("/collections", json={"name": "valid_name"})
    assert response.status_code == 201
    library.create.assert_called_once_with("valid_name")

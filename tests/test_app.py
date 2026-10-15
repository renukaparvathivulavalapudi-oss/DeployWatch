
import os
import sqlite3
import pytest

import app as deploywatch


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(deploywatch, "DATABASE", str(db_path))
    deploywatch.app.config["TESTING"] = True

    deploywatch.init_db()

    with deploywatch.app.test_client() as client:
        yield client


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"DeployWatch" in response.data


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "UP"


def test_invalid_url_is_down(client):
    status, code, response_time = deploywatch.check_application(
        "not-a-valid-url"
    )
    assert status == "DOWN"
    assert code is None

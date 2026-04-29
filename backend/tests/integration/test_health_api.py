from fastapi.testclient import TestClient


def test_health_returns_status(test_client: TestClient):
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"


def test_health_returns_503_when_database_check_fails(db_error_client: TestClient):
    response = db_error_client.get("/health")

    assert response.status_code == 503
    assert response.json()["services"]["database"] == "error"


def test_health_returns_503_when_database_pool_startup_fails(db_startup_error_client: TestClient):
    response = db_startup_error_client.get("/health")

    assert response.status_code == 503
    assert response.json()["services"]["database"] == "error"


def test_health_returns_503_when_llm_check_fails(llm_error_client: TestClient):
    response = llm_error_client.get("/health")

    assert response.status_code == 503
    assert response.json()["services"]["llm"] == "error"
    assert llm_error_client.app.state.test_llm.calls == 1
    response = llm_error_client.get("/health")
    assert response.status_code == 503
    assert llm_error_client.app.state.test_llm.calls == 2


def test_health_reuses_cached_llm_status(test_client: TestClient):
    first = test_client.get("/health")
    second = test_client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 200
    assert test_client.app.state.test_llm.calls == 1

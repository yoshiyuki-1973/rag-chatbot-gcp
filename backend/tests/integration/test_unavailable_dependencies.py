from fastapi.testclient import TestClient


def test_chat_returns_503_when_database_pool_startup_fails(db_startup_error_client: TestClient):
    response = db_startup_error_client.post("/chat", json={"query": "test"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable."

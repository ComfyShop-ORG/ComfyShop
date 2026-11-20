from fastapi.testclient import TestClient

from comfyshop_api.core.config import Settings, get_settings
from comfyshop_api.main import create_app


def test_health_uses_dependency_and_declares_its_schema(settings):
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: Settings(app_name="configured-service")
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "configured-service"}
        schema = client.get("/openapi.json").json()
        assert "/api/v1/health" in schema["paths"]
        assert "HealthResponse" in schema["components"]["schemas"]


def test_explicit_host_restrictions_override_global_default(settings):
    settings.allowed_hosts = ["comfyshop.example", "127.0.0.1"]
    with TestClient(create_app(settings), base_url="http://comfyshop.example") as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/health", headers={"Host": "other.example"}).status_code == 400

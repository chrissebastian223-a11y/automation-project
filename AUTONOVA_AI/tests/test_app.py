from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_index():
    r = client.get("/")
    assert r.status_code == 200
    assert "AUTONOVA AI" in r.text

def test_invalid_command_rejected():
    r = client.post("/api/command", json={"command": "LAUNCH"})
    assert r.status_code == 400
    assert "INVALID_COMMAND" in r.json()["detail"]

def test_settings_validate_confidence():
    r = client.post("/api/settings", json={
        "esp_url": "http://127.0.0.1", "camera_source": "0",
        "model_path": "yolov8n.pt", "confidence": 3.0,
        "obstacle_demo": True, "ocr_enabled": False
    })
    assert r.status_code == 422

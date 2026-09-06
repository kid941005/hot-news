import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.main import app


def test_platforms_include_realtime_flag():
    client = TestClient(app)
    response = client.get("/api/platforms")
    assert response.status_code == 200
    platforms = {p["id"]: p for p in response.json()["platforms"]}
    assert platforms["wallstreetcn"]["realtime"] is True
    assert platforms["weibo"]["realtime"] is False

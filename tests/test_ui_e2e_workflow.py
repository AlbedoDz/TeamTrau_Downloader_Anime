import json
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from ui.server import TeamTrauAPIHandler

TEST_PORT = 8773
TEST_BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


@pytest.fixture(scope="module")
def running_server():
    """Spin up a dedicated test HTTP server instance for E2E testing."""
    server = ThreadingHTTPServer(("127.0.0.1", TEST_PORT), TeamTrauAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield server
    server.shutdown()
    server.server_close()


def test_e2e_static_index_page(running_server):
    """Verify that root URL returns the static HTML UI index."""
    req = Request(f"{TEST_BASE_URL}/")
    with urlopen(req) as res:
        assert res.status == 200
        content = res.read().decode("utf-8")
        assert "TeamTrau" in content
        assert "react" in content.lower()


def test_e2e_api_tasks_endpoint(running_server):
    """Verify /api/tasks returns structured task list, counts, and queue config."""
    req = Request(f"{TEST_BASE_URL}/api/tasks")
    with urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
        assert "tasks" in data
        assert "counts" in data
        assert "config" in data


def test_e2e_api_create_and_manage_task(running_server):
    """Verify task creation, pause, resume, and per-task logs retrieval."""
    # 1. Create task
    create_req = Request(
        f"{TEST_BASE_URL}/api/tasks/create",
        data=json.dumps(
            {
                "url": "https://all-wish.me/watch/test-anime",
                "animeTitle": "E2E Test Anime",
                "episodes": ["1", "2"],
                "site": "allwish",
                "quality": "1080p",
                "downloadMode": "full",
                "targetSubLangs": ["es-LA", "en"],
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(create_req) as res:
        assert res.status == 200
        create_data = json.loads(res.read().decode("utf-8"))
        assert create_data["success"] is True
        assert len(create_data["tasks"]) == 2
        task_id = create_data["tasks"][0]["id"]

    # 2. Pause task
    pause_req = Request(
        f"{TEST_BASE_URL}/api/tasks/{task_id}/pause",
        data=json.dumps({}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(pause_req) as res:
        assert res.status == 200
        pause_data = json.loads(res.read().decode("utf-8"))
        assert pause_data["success"] is True

    # 3. Fetch task logs
    logs_req = Request(f"{TEST_BASE_URL}/api/tasks/{task_id}/logs")
    with urlopen(logs_req) as res:
        assert res.status == 200
        logs_data = json.loads(res.read().decode("utf-8"))
        assert logs_data["success"] is True
        assert isinstance(logs_data["logs"], list)

    # 4. Resume task
    resume_req = Request(
        f"{TEST_BASE_URL}/api/tasks/{task_id}/resume",
        data=json.dumps({}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(resume_req) as res:
        assert res.status == 200
        resume_data = json.loads(res.read().decode("utf-8"))
        assert resume_data["success"] is True

    # 5. Delete task
    delete_req = Request(
        f"{TEST_BASE_URL}/api/tasks/{task_id}/delete",
        data=json.dumps({"deleteFile": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(delete_req) as res:
        assert res.status == 200
        delete_data = json.loads(res.read().decode("utf-8"))
        assert delete_data["success"] is True


def test_e2e_api_parse_allwish(running_server):
    """Verify /api/parse handles AllWish URLs and returns structured series data."""
    test_url = "https://all-wish.me/watch/world-is-dancing-mof9c/ep-8"
    req = Request(
        f"{TEST_BASE_URL}/api/parse",
        data=json.dumps({"url": test_url}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
        assert data["site"] == "allwish"
        assert "World Is Dancing" in data["title"]
        assert len(data["episodes"]) > 0


def test_e2e_api_parse_animesuge(running_server):
    """Verify /api/parse handles AnimeSuge URLs and returns structured series data."""
    test_url = "https://animesuge.cz/anime/world-is-dancing-wt8rp/ep-4"
    req = Request(
        f"{TEST_BASE_URL}/api/parse",
        data=json.dumps({"url": test_url}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
        assert data["site"] == "animesuge"
        assert "World Is Dancing" in data["title"]
        assert len(data["episodes"]) > 0


def test_e2e_api_create_and_download_animesuge(running_server):
    """Verify task creation for AnimeSuge in GUI Download Manager."""
    req = Request(
        f"{TEST_BASE_URL}/api/tasks/create",
        data=json.dumps(
            {
                "url": "https://animesuge.cz/anime/world-is-dancing-wt8rp/ep-4",
                "animeTitle": "World Is Dancing",
                "episodes": ["4"],
                "site": "animesuge",
                "quality": "1080p",
                "downloadMode": "sub_only",
                "targetSubLangs": ["es-LA"],
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["site"] == "animesuge"


def test_e2e_api_create_and_download_animecube(running_server):
    """Verify task creation for AnimeCube in GUI Download Manager."""
    req = Request(
        f"{TEST_BASE_URL}/api/tasks/create",
        data=json.dumps(
            {
                "url": "https://animecube.live/watch/one-piece/ep-1",
                "animeTitle": "One Piece",
                "episodes": ["1"],
                "site": "animecube",
                "quality": "1080p",
                "downloadMode": "full",
                "targetSubLangs": ["en"],
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["site"] == "animecube"


def test_e2e_api_parse_invalid_url(running_server):
    """Verify /api/parse cleanly returns error status on unsupported/empty URL without crashing."""
    req = Request(
        f"{TEST_BASE_URL}/api/parse",
        data=json.dumps({"url": "https://unsupported-domain.xyz/test"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req) as res:
            assert res.status == 400
    except Exception as e:
        assert getattr(e, "code", None) == 400


def test_e2e_api_queue_controls(running_server):
    """Verify /api/queue/pause-all, resume-all, clear-completed endpoints."""
    req_pause = Request(
        f"{TEST_BASE_URL}/api/queue/pause-all",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_pause) as res:
        assert res.status == 200

    req_resume = Request(
        f"{TEST_BASE_URL}/api/queue/resume-all",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_resume) as res:
        assert res.status == 200

    req_clear = Request(
        f"{TEST_BASE_URL}/api/queue/clear-completed",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_clear) as res:
        assert res.status == 200

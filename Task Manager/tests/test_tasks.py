import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as service


class TaskApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "tasks.db"
        self.database_patch = patch.object(service, "DATABASE_PATH", self.database_path)
        self.key_patch = patch.object(service, "WEB_ACCESS_KEY", "test-secret")
        self.user_patch = patch.object(service, "WEB_USER_ID", 123)
        self.database_patch.start()
        self.key_patch.start()
        self.user_patch.start()
        self.client = TestClient(service.app)
        self.client.__enter__()
        self.headers = {"X-Access-Key": "test-secret"}

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self.user_patch.stop()
        self.key_patch.stop()
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_api_requires_access_key(self) -> None:
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 401)

    def test_task_can_be_created_completed_and_deleted(self) -> None:
        created = self.client.post(
            "/api/tasks",
            headers=self.headers,
            json={"title": "Sinov vazifasi"},
        )
        self.assertEqual(created.status_code, 200)
        task = created.json()

        completed = self.client.patch(
            f"/api/tasks/{task['id']}",
            headers=self.headers,
            json={"done": True},
        )
        self.assertTrue(completed.json()["done"])

        deleted = self.client.delete(
            f"/api/tasks/{task['id']}",
            headers=self.headers,
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks", headers=self.headers).json(), [])

from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

import httpx
from warehouse.api import create_app
from warehouse.db import init, ingest
from warehouse.generate import generate


def client_for(path):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(path)), base_url="http://test")


class ApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root/"warehouse.db"
        init(self.db)
        ingest(self.db, generate(self.root/"source.csv",100))
        self.client = client_for(self.db)
        self.addAsyncCleanup(self.client.aclose)

    async def test_health(self):
        self.assertEqual((await self.client.get("/health")).json(),{"status":"ready","schema_version":1})

    async def test_report(self):
        r=await self.client.get("/api/report")
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()["summary"]["sales"],100)

    async def test_filter(self):
        r=await self.client.get("/api/report",params={"country":"no match"})
        self.assertEqual(r.json()["summary"]["sales"],0)

    async def test_invalid_date(self):
        self.assertEqual((await self.client.get("/api/report?start=bad")).status_code,422)

    async def test_reverse_date(self):
        self.assertEqual((await self.client.get("/api/report?start=2025-01-01&end=2024-01-01")).status_code,400)

    async def test_quality(self):
        self.assertTrue((await self.client.get("/api/quality")).json()["passed"])

    async def test_run_history(self):
        r=await self.client.get("/api/runs")
        self.assertEqual(r.json()[0]["rows_inserted"],100)
        self.assertNotIn("source_sha256",r.json()[0])
        self.assertEqual((await self.client.get("/api/runs?limit=101")).status_code,422)

    async def test_dashboard_and_assets(self):
        self.assertIn("Sales intelligence",(await self.client.get("/")).text)
        self.assertEqual((await self.client.get("/assets/dashboard.js")).status_code,200)
        self.assertEqual((await self.client.get("/assets/style.css")).status_code,200)

    async def test_openapi(self):
        r=await self.client.get("/openapi.json")
        self.assertIn("/api/report",r.json()["paths"])

    async def test_api_has_no_write_endpoints(self):
        self.assertEqual((await self.client.post("/api/report",json={})).status_code,405)

    async def test_uninitialized_database_unavailable(self):
        async with client_for(self.root/"missing.db") as client:
            self.assertEqual((await client.get("/health")).status_code,503)
            self.assertEqual((await client.get("/api/report")).status_code,503)
            self.assertFalse((self.root/"missing.db").exists())

    async def test_no_path_traversal(self):
        r=await self.client.get("/assets/../warehouse/api.py")
        self.assertEqual(r.status_code,404)


if __name__ == "__main__":
    unittest.main()

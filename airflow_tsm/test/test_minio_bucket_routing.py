import importlib.util
import os
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path, name, stubs):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(name, None)
    return module


def minio_stubs(client, extra=None):
    boto3 = types.ModuleType("boto3")
    boto3.client = MagicMock(return_value=client)
    botocore = types.ModuleType("botocore")
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ClientError = type("ClientError", (Exception,), {})
    exceptions.NoCredentialsError = type("NoCredentialsError", (Exception,), {})
    stubs = {
        "boto3": boto3,
        "botocore": botocore,
        "botocore.exceptions": exceptions,
    }
    if extra:
        stubs.update(extra)
    return stubs


class FixedDatetime:
    @classmethod
    def now(cls):
        return datetime(2026, 7, 10, 12, 34, 56)


class MinioBucketRoutingTests(unittest.TestCase):
    def test_flood_mapping_upload_uses_flood_bucket_and_keeps_key(self):
        client = MagicMock()
        pandas = types.ModuleType("pandas")
        with patch.dict(os.environ, {"FLOOD_MINIO_BUCKET": "flood-custom"}, clear=False):
            module = load_module(
                "scripts/mapping/upload_minio.py",
                "test_mapping_upload",
                minio_stubs(client, {"pandas": pandas}),
            )

        with patch("builtins.print"), patch.object(module.os.path, "exists", return_value=True):
            result = module.run_upload(
                "/tmp/road.geojson",
                delete_local_file_after_upload=False,
                run_ts="20260710T123456",
            )

        self.assertEqual(
            client.upload_file.call_args.args,
            ("/tmp/road.geojson", "flood-custom", "20260710T123456/flood_road_20260710T123456.geojson"),
        )
        self.assertEqual(result["bucket"], "flood-custom")

    def test_initial_wl_producer_and_consumer_use_same_bucket_and_prefix(self):
        producer_client = MagicMock()
        consumer_client = MagicMock()
        requests = types.ModuleType("requests")
        environment = {
            "INITIAL_WL_MINIO_BUCKET": "initial-custom",
            "INITIAL_WL_MINIO_PREFIX": "ingest",
        }

        with patch.dict(os.environ, environment, clear=False):
            producer = load_module(
                "scripts/initial_wl/generate_initial_wl.py",
                "test_initial_wl_producer",
                minio_stubs(producer_client),
            )
            consumer = load_module(
                "scripts/initial_wl/apply_initial_wl.py",
                "test_initial_wl_consumer",
                minio_stubs(consumer_client, {"requests": requests}),
            )

        with patch("builtins.print"):
            producer.upload_to_minio("/tmp/initial_wl_20260710_123456.csv")
        self.assertEqual(
            producer_client.upload_file.call_args.args,
            ("/tmp/initial_wl_20260710_123456.csv", "initial-custom", "ingest/initial_wl_20260710_123456.csv"),
        )

        paginator = consumer_client.get_paginator.return_value
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "ingest/older.csv", "LastModified": datetime(2026, 7, 10, 12, 0, 0)},
                    {"Key": "ingest/newest.csv", "LastModified": datetime(2026, 7, 10, 12, 1, 0)},
                ]
            }
        ]
        with patch("builtins.print"):
            self.assertEqual(consumer.get_latest_csv(), "/tmp/newest.csv")
        paginator.paginate.assert_called_once_with(Bucket="initial-custom", Prefix="ingest")
        consumer_client.download_file.assert_called_once_with("initial-custom", "ingest/newest.csv", "/tmp/newest.csv")

    def test_manhole_csv_uploads_use_manhole_bucket_and_existing_keys(self):
        client = MagicMock()
        selenium = types.ModuleType("selenium")
        webdriver = types.ModuleType("selenium.webdriver")
        selenium.webdriver = webdriver
        selenium_common = types.ModuleType("selenium.webdriver.common")
        selenium_by = types.ModuleType("selenium.webdriver.common.by")
        selenium_by.By = MagicMock()
        selenium_chrome = types.ModuleType("selenium.webdriver.chrome")
        selenium_service = types.ModuleType("selenium.webdriver.chrome.service")
        selenium_service.Service = MagicMock()
        selenium_options = types.ModuleType("selenium.webdriver.chrome.options")
        selenium_options.Options = MagicMock()
        webdriver_manager = types.ModuleType("webdriver_manager")
        webdriver_manager_chrome = types.ModuleType("webdriver_manager.chrome")
        webdriver_manager_chrome.ChromeDriverManager = MagicMock()
        pytesseract = types.ModuleType("pytesseract")
        pytesseract.pytesseract = MagicMock()
        extra = {
            "pytesseract": pytesseract,
            "cv2": types.ModuleType("cv2"),
            "numpy": types.ModuleType("numpy"),
            "requests": types.ModuleType("requests"),
            "selenium": selenium,
            "selenium.webdriver": webdriver,
            "selenium.webdriver.common": selenium_common,
            "selenium.webdriver.common.by": selenium_by,
            "selenium.webdriver.chrome": selenium_chrome,
            "selenium.webdriver.chrome.service": selenium_service,
            "selenium.webdriver.chrome.options": selenium_options,
            "webdriver_manager": webdriver_manager,
            "webdriver_manager.chrome": webdriver_manager_chrome,
        }

        with patch.dict(os.environ, {"MANHOLES_MINIO_BUCKET": "manholes-custom"}, clear=False):
            module = load_module("scripts/manholes/XuLyTramDo.py", "test_manhole_upload", minio_stubs(client, extra))

        module.datetime = FixedDatetime
        uploaded = module.upload_all_to_minio(
            {"waterlevel_file": "water_levels.csv", "rain_file": "rain_levels.csv"}
        )

        self.assertEqual(uploaded, {
            "waterlevel": "20260710_123456/waterlevel_20260710_123456.csv",
            "rain": "20260710_123456/rain_20260710_123456.csv",
        })
        self.assertEqual(client.upload_file.call_count, 2)
        self.assertEqual(client.upload_file.call_args_list[0].args[:3], (
            "water_levels.csv", "manholes-custom", "20260710_123456/waterlevel_20260710_123456.csv",
        ))
        self.assertEqual(client.upload_file.call_args_list[1].args[:3], (
            "rain_levels.csv", "manholes-custom", "20260710_123456/rain_20260710_123456.csv",
        ))

    def test_compose_initializes_and_routes_named_buckets(self):
        compose = (ROOT.parent / "compose.yml").read_text(encoding="utf-8")
        floodmap_server = (ROOT.parent / "floodmap/valhalla-flood-road-test/backend/server.py").read_text(encoding="utf-8")
        self.assertIn('bucket = os.environ.get("FLOOD_MINIO_BUCKET")', floodmap_server)
        self.assertIn('INITIAL_WL_MINIO_BUCKET: ${INITIAL_WL_MINIO_BUCKET:-initial-wl}', compose)
        self.assertIn('MANHOLES_MINIO_BUCKET: ${MANHOLES_MINIO_BUCKET:-manholes-data}', compose)
        self.assertIn('mc mb --ignore-existing "local/$${FLOOD_MINIO_BUCKET}"', compose)
        self.assertIn('mc mb --ignore-existing "local/$${INITIAL_WL_MINIO_BUCKET}"', compose)
        self.assertIn('mc mb --ignore-existing "local/$${MANHOLES_MINIO_BUCKET}"', compose)
        self.assertIn('FLOOD_MINIO_BUCKET: ${FLOOD_MINIO_BUCKET:-flood-results-full}', compose)


if __name__ == "__main__":
    unittest.main()

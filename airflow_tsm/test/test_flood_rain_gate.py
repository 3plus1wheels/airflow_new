import importlib.util
import os
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_create_simulation(environment=None):
    requests = types.ModuleType("requests")
    requests.get = MagicMock()
    requests.post = MagicMock()
    fiona = types.ModuleType("fiona")
    fiona_vfs = types.ModuleType("fiona.vfs")
    fiona.vfs = fiona_vfs
    spec = importlib.util.spec_from_file_location(
        "test_create_simulation_rain_gate",
        ROOT / "scripts/create_simulation.py",
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {"requests": requests, "fiona": fiona, "fiona.vfs": fiona_vfs},
    ), patch.dict(os.environ, environment or {}, clear=False):
        spec.loader.exec_module(module)
    return module


class FloodRainGateTests(unittest.TestCase):
    def test_gate_requires_any_interval_at_or_above_five_mm_hr(self):
        module = load_create_simulation()
        below = [
            {"values": {"precipitationIntensity": 4.9}},
            {"values": {"precipitationIntensity": 0}},
        ]
        at_threshold = below + [{"values": {"precipitationIntensity": 5.0}}]

        self.assertFalse(module.evaluate_rain_gate(below, 5)["should_run"])
        decision = module.evaluate_rain_gate(at_threshold, 5)
        self.assertTrue(decision["should_run"])
        self.assertEqual(decision["max_intensity_mm_hr"], 5.0)

    def test_test_override_builds_two_hour_fifteen_minute_forecast(self):
        module = load_create_simulation()

        with patch.dict(os.environ, {"FLOOD_TEST_RAIN_MM_HR": "6.25"}, clear=False), patch("builtins.print"):
            intervals = module.get_rain_forecast()

        self.assertEqual(len(intervals), 9)
        self.assertTrue(module.evaluate_rain_gate(intervals, 5)["should_run"])
        self.assertTrue(all(module.rain_intensity_mm_hr(item) == 6.25 for item in intervals))

    def test_live_forecast_uses_exact_two_hour_fifteen_minute_query(self):
        module = load_create_simulation()

        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

        response = MagicMock()
        response.json.return_value = {"data": {"timelines": [{"intervals": [{"startTime": "now"}]}]}}
        module.requests.get.return_value = response
        module.datetime = FixedDatetime

        with patch.dict(os.environ, {"FLOOD_TEST_RAIN_MM_HR": ""}, clear=False), patch("builtins.print"):
            intervals = module.get_rain_forecast()

        self.assertEqual(intervals, [{"startTime": "now"}])
        _, kwargs = module.requests.get.call_args
        self.assertEqual(kwargs["params"]["fields"], ["precipitationIntensity"])
        self.assertEqual(kwargs["params"]["timesteps"], "15m")
        self.assertEqual(kwargs["params"]["startTime"], "2026-07-20T12:00:00Z")
        self.assertEqual(kwargs["params"]["endTime"], "2026-07-20T14:00:00Z")

    def test_rain_values_use_actual_fifteen_minute_offsets(self):
        module = load_create_simulation()
        intervals = [
            {"startTime": "2026-07-20T00:00:00Z", "values": {"precipitationIntensity": 3.6}},
            {"startTime": "2026-07-20T00:15:00Z", "values": {"precipitationIntensity": 7.2}},
        ]

        values = module.build_rain_values(intervals)

        self.assertEqual([item[0] for item in values], [0, 900])
        self.assertAlmostEqual(values[0][1], 0.000001)
        self.assertAlmostEqual(values[1][1], 0.000002)

    def test_main_dag_is_continuous_and_has_successful_dry_branch(self):
        dag_source = (ROOT / "dags/flood_mapping_dag.py").read_text(encoding="utf-8")
        compose = (ROOT.parent / "compose.yml").read_text(encoding="utf-8")

        self.assertIn('schedule="@continuous"', dag_source)
        self.assertIn('return "wait_before_next_rain_check"', dag_source)
        self.assertIn('mode="reschedule"', dag_source)
        self.assertNotIn('schedule="*/30 * * * *"', dag_source)
        self.assertNotIn('airflow dags trigger --run-id', compose)
        self.assertIn('FLOOD_RAIN_THRESHOLD_MM_HR: ${FLOOD_RAIN_THRESHOLD_MM_HR:-5}', compose)
        self.assertIn('FLOOD_RAIN_TIMESTEP_MINUTES: ${FLOOD_RAIN_TIMESTEP_MINUTES:-15}', compose)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_netcdf_input():
    spec = importlib.util.spec_from_file_location(
        "test_netcdf_input",
        ROOT / "scripts/netcdf_input.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModelNetcdfInputTests(unittest.TestCase):
    def setUp(self):
        self.module = load_netcdf_input()
        self.ti = MagicMock()
        self.ti.xcom_pull.side_effect = ["simulation-83022", "/data/current-model.nc"]
        self.calculate_depth = MagicMock(return_value="/data/depth/run-1")

    def run_depth(self):
        return self.module.calculate_depth_from_download(
            ti=self.ti,
            calculate_depth_fn=self.calculate_depth,
            grid_path="/data/gridadmin.h5",
            dem_path="/data/dem.tif",
            output_dir="/data/depth",
            model_id="83022",
        )

    @patch("os.path.isfile", return_value=True)
    def test_passes_exact_downloaded_netcdf_to_depth_calculation(self, _isfile):
        with patch("builtins.print") as output:
            result = self.run_depth()

        self.assertEqual(result, "/data/depth/run-1")
        self.assertEqual(
            self.calculate_depth.call_args.kwargs,
            {
                "grid_path": "/data/gridadmin.h5",
                "nc_path": "/data/current-model.nc",
                "dem_path": "/data/dem.tif",
                "output_dir": "/data/depth",
            },
        )
        self.assertIn("model_id=83022", output.call_args.args[0])
        self.assertIn("simulation_id=simulation-83022", output.call_args.args[0])

    def test_rejects_missing_xcom_path(self):
        self.ti.xcom_pull.side_effect = ["simulation-83022", None]

        with self.assertRaisesRegex(ValueError, "missing from task 2_download_results XCom"):
            self.run_depth()
        self.calculate_depth.assert_not_called()

    def test_rejects_non_netcdf_download(self):
        self.ti.xcom_pull.side_effect = ["simulation-83022", "/data/result.zip"]

        with self.assertRaisesRegex(ValueError, "not a NetCDF file"):
            self.run_depth()
        self.calculate_depth.assert_not_called()

    @patch("os.path.isfile", return_value=False)
    def test_rejects_missing_downloaded_file(self, _isfile):
        with self.assertRaisesRegex(FileNotFoundError, "does not exist"):
            self.run_depth()
        self.calculate_depth.assert_not_called()


if __name__ == "__main__":
    unittest.main()

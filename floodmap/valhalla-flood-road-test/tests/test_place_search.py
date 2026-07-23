import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import place_search  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def vietnam_feature(name="Hồ Hoàn Kiếm"):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [105.8522, 21.0287]},
        "properties": {
            "name": name,
            "district": "Hoàn Kiếm",
            "city": "Hà Nội",
            "country": "Việt Nam",
            "countrycode": "VN",
            "osm_type": "N",
            "osm_id": 123,
            "osm_value": "locality",
        },
    }


class PlaceSearchTests(unittest.TestCase):
    def test_vietnam_filters_bias_and_normalized_result(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse({"features": [vietnam_feature()]})

        with patch.object(place_search, "urlopen", side_effect=fake_urlopen):
            results = place_search.search_places("Hồ Hoàn Kiếm", "21.02", "105.85", "15")

        self.assertIn("countrycode=VN", captured["url"])
        self.assertIn("lang=default", captured["url"])
        self.assertIn("limit=6", captured["url"])
        self.assertIn("lat=21.02", captured["url"])
        self.assertIn("lon=105.85", captured["url"])
        self.assertIn("zoom=15", captured["url"])
        self.assertEqual(captured["timeout"], 5)
        self.assertEqual(results, [{
            "id": "N:123",
            "name": "Hồ Hoàn Kiếm",
            "address": "Hoàn Kiếm, Hà Nội, Việt Nam",
            "kind": "locality",
            "lat": 21.0287,
            "lon": 105.8522,
        }])

    def test_non_vietnam_and_malformed_features_are_ignored(self):
        outside = vietnam_feature("Outside")
        outside["properties"]["countrycode"] = "US"
        payload = {"features": [outside, {"bad": "feature"}, vietnam_feature("Huế")]}
        with patch.object(place_search, "urlopen", return_value=FakeResponse(payload)):
            results = place_search.search_places("Huế")
        self.assertEqual([item["name"] for item in results], ["Huế"])

    def test_invalid_query_and_bias_are_rejected(self):
        with self.assertRaises(place_search.PlaceSearchValidationError):
            place_search.search_places("H")
        with self.assertRaises(place_search.PlaceSearchValidationError):
            place_search.search_places("Hà Nội", "21", None, "15")
        with self.assertRaises(place_search.PlaceSearchValidationError):
            place_search.search_places("Hà Nội", "91", "105", "15")
        with self.assertRaises(place_search.PlaceSearchValidationError):
            place_search.search_places("Hà Nội", "21", "105", "15.5")

    def test_timeout_is_distinct_from_provider_failure(self):
        with patch.object(place_search, "urlopen", side_effect=TimeoutError):
            with self.assertRaises(place_search.PlaceSearchTimeout):
                place_search.search_places("Bến Thành")
        with patch.object(place_search, "urlopen", side_effect=URLError("offline")):
            with self.assertRaises(place_search.PlaceSearchUnavailable):
                place_search.search_places("Bến Thành")

    def test_invalid_provider_payload_is_rejected(self):
        with patch.object(place_search, "urlopen", return_value=FakeResponse({"features": "bad"})):
            with self.assertRaises(place_search.PlaceSearchUnavailable):
                place_search.search_places("Đà Nẵng")

    def test_base_url_can_be_configured(self):
        original = place_search.PHOTON_BASE_URL
        try:
            place_search.PHOTON_BASE_URL = "http://photon.internal:2322"
            with patch.object(place_search, "urlopen", return_value=FakeResponse({"features": []})) as mocked:
                place_search.search_places("Hà Nội")
            self.assertTrue(mocked.call_args.args[0].full_url.startswith("http://photon.internal:2322/api?"))
        finally:
            place_search.PHOTON_BASE_URL = original


if __name__ == "__main__":
    unittest.main()

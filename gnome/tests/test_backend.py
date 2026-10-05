import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "praybar@diea-abdeltwab.github.io" / "backend" / "praybar_backend.py"
spec = importlib.util.spec_from_file_location("praybar_backend", SRC)
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)
REAL_GEOCLUE = pb._geoclue_geolocate   # setUp replaces pb._geoclue_geolocate with a mock

TIMINGS = {"Fajr": "04:54 (EET)", "Sunrise": "06:27", "Dhuhr": "13:01", "Asr": "16:36",
           "Maghrib": "19:34", "Isha": "20:56", "Imsak": "04:44"}
D1, D2 = date(2026, 10, 4), date(2026, 10, 5)
CITY_A = (30.0, 31.0, "City A")
CITY_B = (40.0, 20.0, "City B")


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        for target, value in (("CACHE_DIR", base), ("LOCATION_CACHE", base / "location.json"),
                              ("TIMINGS_CACHE", base / "timings.json")):
            p = mock.patch.object(pb, target, value)
            p.start()
            self.addCleanup(p.stop)
        # Never touch the real GeoClue/D-Bus in tests; individual tests opt in.
        geoclue = mock.patch.object(pb, "_geoclue_geolocate", return_value=None)
        self.geoclue = geoclue.start()
        self.addCleanup(geoclue.stop)
        self.addCleanup(self.tmp.cleanup)

    def api(self, fail=False):
        calls = []

        def get(url, timeout, headers=None):
            calls.append(url)
            if fail:
                raise OSError("offline")
            return {"data": {"timings": dict(TIMINGS)}}
        return get, calls

    # ── timings ──
    def test_fetches_today_and_tomorrow_and_trims(self):
        get, calls = self.api()
        with mock.patch.object(pb, "_get_json", get), mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_A):
            r = pb.build_result(5, today=D1)
        self.assertTrue(r["ok"])
        self.assertEqual(r["timings"]["Fajr"], "04:54")
        self.assertNotIn("Imsak", r["timings"])
        self.assertEqual(r["tomorrow_fajr"], "04:54")
        self.assertEqual(r["city"], "City A")
        self.assertEqual(r["source"], "wttr")
        self.assertIn("04-10-2026", calls[0])
        self.assertIn("05-10-2026", calls[1])

    def test_second_call_same_day_uses_cache_and_skips_location_lookup(self):
        get, calls = self.api()
        with mock.patch.object(pb, "_get_json", get), mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_A) as loc:
            pb.build_result(5, today=D1)
            pb.build_result(5, today=D1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(loc.call_count, 1)

    def test_changing_method_invalidates_timings_cache(self):
        get, calls = self.api()
        with mock.patch.object(pb, "_get_json", get), mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_A):
            pb.build_result(5, today=D1)
            pb.build_result(3, today=D1)
        self.assertEqual(len(calls), 4)

    def test_offline_with_cache_returns_stale(self):
        get, _ = self.api()
        with mock.patch.object(pb, "_get_json", get), mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_A):
            pb.build_result(5, today=D1)
        bad, _ = self.api(fail=True)
        with mock.patch.object(pb, "_get_json", bad), mock.patch.object(pb, "_wttr_geolocate", return_value=None), \
                mock.patch.object(pb, "_ip_geolocate", return_value=None):
            r = pb.build_result(5, today=date(2026, 10, 6))
        self.assertTrue(r["ok"])
        self.assertTrue(r["stale"])

    # ── location ──
    def test_location_is_redetected_on_a_new_day(self):
        get, _ = self.api()
        with mock.patch.object(pb, "_get_json", get), \
                mock.patch.object(pb, "_wttr_geolocate", side_effect=[CITY_A, CITY_B]) as loc:
            first = pb.build_result(5, today=D1)
            second = pb.build_result(5, today=D2)
        self.assertEqual(loc.call_count, 2)           # looked up again after "midnight"
        self.assertEqual(first["city"], "City A")
        self.assertEqual(second["city"], "City B")    # equal-tier disagreement = genuine move

    def test_no_location_and_no_history_is_an_error_not_a_guess(self):
        with mock.patch.object(pb, "_wttr_geolocate", return_value=None), \
                mock.patch.object(pb, "_ip_geolocate", return_value=None):
            self.assertIsNone(pb.resolve_location(D1))
            with self.assertRaises(RuntimeError):
                pb.build_result(5, today=D1)

    def test_lookup_failure_reuses_last_known_city(self):
        with mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_A):
            pb.resolve_location(D1)
        with mock.patch.object(pb, "_wttr_geolocate", return_value=None), \
                mock.patch.object(pb, "_ip_geolocate", return_value=None):
            lat, lon, city, source = pb.resolve_location(D2)
        self.assertEqual((lat, lon, city, source), (30.0, 31.0, "City A", "cache"))

    def test_main_prints_json_error_instead_of_traceback(self):
        out = mock.MagicMock()
        with mock.patch.object(pb, "_wttr_geolocate", return_value=None), \
                mock.patch.object(pb, "_ip_geolocate", return_value=None), mock.patch.object(sys, "stdout", out):
            pb.main([])
        printed = "".join(c.args[0] for c in out.write.call_args_list)
        self.assertFalse(json.loads(printed)["ok"])

    def test_no_hardcoded_default_location_in_source(self):
        text = SRC.read_text().lower()
        for needle in ("fallback", "manual"):
            self.assertNotIn(needle, text)

    # ── GeoClue tier ──
    WHERE_AM_I_OUTPUT = """Client object: /org/freedesktop/GeoClue2/Client/2

New location:
Latitude:    12.345600°
Longitude:   34.567800°
Accuracy:    25000 meters
Description: GeoIP (ichnaea)
Timestamp:   Tue 06 Oct 2026 02:18:57 AM EEST (1791242337 seconds since the Epoch)
"""

    def test_parse_where_am_i_real_output_shape(self):
        lat, lon, acc = pb.parse_where_am_i(self.WHERE_AM_I_OUTPUT)
        self.assertEqual((lat, lon, acc), (12.3456, 34.5678, 25000.0))

    def test_parse_where_am_i_takes_the_last_location(self):
        two = self.WHERE_AM_I_OUTPUT + self.WHERE_AM_I_OUTPUT.replace("12.345600", "13.000000").replace("25000", "1500")
        lat, _, acc = pb.parse_where_am_i(two)
        self.assertEqual((lat, acc), (13.0, 1500.0))

    def test_parse_where_am_i_tolerates_locale_commas(self):
        out = self.WHERE_AM_I_OUTPUT.replace("12.345600", "12,345600").replace("34.567800", "34,567800")
        self.assertEqual(pb.parse_where_am_i(out)[:2], (12.3456, 34.5678))

    def test_parse_where_am_i_rejects_country_level_and_garbage(self):
        coarse = self.WHERE_AM_I_OUTPUT.replace("25000 meters", "300000 meters")
        self.assertIsNone(pb.parse_where_am_i(coarse))
        self.assertIsNone(pb.parse_where_am_i("Failed to connect to GeoClue2 service"))
        self.assertIsNone(pb.parse_where_am_i(""))

    def test_geoclue_is_preferred_over_wttr(self):
        self.geoclue.return_value = (12.3456, 34.5678, "Near Town, XX")
        with mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_A) as wttr:
            lat, lon, city, source = pb.resolve_location(D1)
        self.assertEqual((lat, lon, city, source), (12.3456, 34.5678, "Near Town, XX", "geoclue"))
        wttr.assert_not_called()

    def test_falls_back_to_wttr_when_geoclue_unavailable(self):
        self.geoclue.return_value = None
        with mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_A):
            self.assertEqual(pb.resolve_location(D1)[3], "wttr")

    def test_a_later_wttr_reading_cannot_override_a_geoclue_fix(self):
        self.geoclue.return_value = (12.3456, 34.5678, "Near Town, XX")
        pb.resolve_location(D1)
        self.geoclue.return_value = None           # GeoClue hiccup the next night
        with mock.patch.object(pb, "_wttr_geolocate", return_value=CITY_B):
            lat, lon, city, source = pb.resolve_location(D2)
        self.assertEqual((city, source), ("Near Town, XX", "geoclue"))

    def test_geoclue_tier_without_the_tool_returns_none(self):
        with mock.patch.object(pb, "_find_where_am_i", return_value=None):
            self.assertIsNone(REAL_GEOCLUE())

    def test_geoclue_tier_runs_the_tool_and_labels_the_result(self):
        done = mock.Mock(stdout=self.WHERE_AM_I_OUTPUT)
        with mock.patch.object(pb, "_find_where_am_i", return_value="/x/where-am-i"), \
                mock.patch.object(pb.subprocess, "run", return_value=done) as run, \
                mock.patch.object(pb, "_reverse_geocode", return_value="Near Town, XX"):
            self.assertEqual(REAL_GEOCLUE(), (12.3456, 34.5678, "Near Town, XX"))
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")   # locale-proof decimals

    def test_geoclue_tier_falls_back_to_coordinates_when_reverse_geocoding_fails(self):
        done = mock.Mock(stdout=self.WHERE_AM_I_OUTPUT)
        with mock.patch.object(pb, "_find_where_am_i", return_value="/x/where-am-i"), \
                mock.patch.object(pb.subprocess, "run", return_value=done), \
                mock.patch.object(pb, "_reverse_geocode", return_value=None):
            self.assertEqual(REAL_GEOCLUE()[2], "12.35, 34.57")

    def test_geoclue_tier_survives_a_hung_or_missing_binary(self):
        for error in (pb.subprocess.TimeoutExpired("x", 1), OSError("boom")):
            with mock.patch.object(pb, "_find_where_am_i", return_value="/x/where-am-i"), \
                    mock.patch.object(pb.subprocess, "run", side_effect=error):
                self.assertIsNone(REAL_GEOCLUE())

    # ── jitter / confidence guard ──
    def test_accept_reading_jitter_keeps_old_coordinates(self):
        cached = {"lat": 30.00, "lon": 31.00, "city": "City A", "source": "wttr"}
        lat, lon, city, _ = pb.accept_reading(30.02, 31.01, "City A2", "wttr", cached)
        self.assertEqual((lat, lon, city), (30.00, 31.00, "City A"))

    def test_accept_reading_rejects_weaker_tier_disagreement(self):
        cached = {"lat": 30.00, "lon": 31.00, "city": "City A", "source": "wttr"}
        lat, _, city, src = pb.accept_reading(40.0, 20.0, "City B", "ip", cached)
        self.assertEqual((lat, city, src), (30.00, "City A", "wttr"))

    def test_accept_reading_accepts_real_move_from_equal_tier(self):
        cached = {"lat": 30.00, "lon": 31.00, "city": "City A", "source": "wttr"}
        lat, _, city, _ = pb.accept_reading(40.0, 20.0, "City B", "wttr", cached)
        self.assertEqual((lat, city), (40.0, "City B"))


if __name__ == "__main__":
    unittest.main()

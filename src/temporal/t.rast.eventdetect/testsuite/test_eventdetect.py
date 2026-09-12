"""Test t.rast.eventdetect on a synthetic strds with two known drops.

The series (5-day spacing, 2021) rises, drops sharply (event 1), recovers,
rises again, drops (event 2) and recovers:

    DOY 100 105 110 115 |120| 125 130 |135| 140 |145| 150 |155|
    NDVI .60 .65 .70 .72 .50  .55 .62  .70  .72  .48  .55  .68
                         ^event1        ^rec1  ^event2      ^rec2

Expected: 2 events, first at DOY 120, both recovered (target 0.8),
recovery times 15 and 10 days.
"""

import grass.script as gs
from grass.gunittest.case import TestCase
from grass.gunittest.main import test


class TestEventDetect(TestCase):
    strds = "evt_ndvi"
    prefix = "evt_out"

    # (date, value); DOY of 2021-04-30 is 120, 2021-05-25 is 145
    series = [
        ("2021-04-10", 0.60),
        ("2021-04-15", 0.65),
        ("2021-04-20", 0.70),
        ("2021-04-25", 0.72),
        ("2021-04-30", 0.50),
        ("2021-05-05", 0.55),
        ("2021-05-10", 0.62),
        ("2021-05-15", 0.70),
        ("2021-05-20", 0.72),
        ("2021-05-25", 0.48),
        ("2021-05-30", 0.55),
        ("2021-06-04", 0.68),
    ]

    @classmethod
    def setUpClass(cls):
        cls.use_temp_region()
        cls.runModule("g.region", n=3, s=0, e=3, w=0, res=1)
        register = []
        for i, (date, value) in enumerate(cls.series):
            name = f"evt_{i:02d}"
            cls.runModule("r.mapcalc", expression=f"{name} = {value}", overwrite=True)
            register.append(f"{name}|{date}")
        cls.runModule("t.create", type="strds", temporaltype="absolute",
                      output=cls.strds, title="evt", description="evt",
                      overwrite=True)
        import grass.script as gs
        reg_file = gs.tempfile()
        with open(reg_file, "w") as fh:
            fh.write("\n".join(register) + "\n")
        cls.runModule("t.register", input=cls.strds, file=reg_file,
                      overwrite=True)

    @classmethod
    def tearDownClass(cls):
        cls.runModule("t.remove", flags="df", type="strds", inputs=cls.strds)
        cls.del_temp_region()

    def _const(self, raster):
        """Return the (single) constant value of a raster."""
        info = gs.raster_info(raster)
        self.assertAlmostEqual(info["min"], info["max"], places=4,
                               msg=f"{raster} is not constant")
        return info["min"]

    def test_counts_and_recovery(self):
        self.assertModule(
            "t.rast.eventdetect", input=self.strds, year=2021,
            output=self.prefix, direction="drop", threshold=0.2,
            threshold_type="absolute", lookback=2, min_separation=10,
            recovery_target=0.8, overwrite=True,
        )
        for suffix in ("count", "first_doy", "last_doy", "n_recovered",
                       "frac_recovered", "mean_recovery_days"):
            self.assertRasterExists(f"{self.prefix}_{suffix}")

        self.assertEqual(self._const(f"{self.prefix}_count"), 2)
        self.assertEqual(self._const(f"{self.prefix}_first_doy"), 120)
        self.assertEqual(self._const(f"{self.prefix}_last_doy"), 145)
        self.assertEqual(self._const(f"{self.prefix}_n_recovered"), 2)
        self.assertAlmostEqual(
            self._const(f"{self.prefix}_frac_recovered"), 1.0, places=4)
        # recovery times 15 and 10 days -> mean 12.5
        self.assertAlmostEqual(
            self._const(f"{self.prefix}_mean_recovery_days"), 12.5, places=3)

    def test_parcel_mode(self):
        # A single parcel covering the whole region. Because the input rasters
        # are spatially constant, the per-parcel median equals the pixel value,
        # so detection over the parcel reproduces the per-pixel result.
        self.runModule("v.in.region", output="evt_parcel", overwrite=True)
        self.assertModule(
            "t.rast.eventdetect", input=self.strds, year=2021,
            output="evt_pout", vector="evt_parcel", direction="drop",
            threshold=0.2, threshold_type="absolute", lookback=2,
            min_separation=10, recovery_target=0.8, overwrite=True,
        )
        self.assertRasterExists("evt_pout_count")
        self.assertEqual(self._const("evt_pout_count"), 2)
        self.assertEqual(self._const("evt_pout_first_doy"), 120)
        self.assertEqual(self._const("evt_pout_last_doy"), 145)
        self.assertAlmostEqual(
            self._const("evt_pout_mean_recovery_days"), 12.5, places=3)

    def _make_strds(self, strds, series):
        """Build a constant-value strds; a value of None registers a NULL map."""
        register = []
        for i, (date, value) in enumerate(series):
            name = f"{strds}_{i:02d}"
            expr = "null()" if value is None else f"{value}"
            self.runModule("r.mapcalc", expression=f"{name} = {expr}",
                           overwrite=True)
            register.append(f"{name}|{date}")
        self.runModule("t.create", type="strds", temporaltype="absolute",
                       output=strds, title=strds, description=strds,
                       overwrite=True)
        reg_file = gs.tempfile()
        with open(reg_file, "w") as fh:
            fh.write("\n".join(register) + "\n")
        self.runModule("t.register", input=strds, file=reg_file, overwrite=True)
        self.addCleanup(self.runModule, "t.remove", flags="df",
                        type="strds", inputs=strds)

    def test_baseline_gap_guard(self):
        # A high value (0.90) sits before a long cloud gap. The baseline window
        # must not reach back across the gap, so the magnitude is measured from
        # the post-gap plateau (0.72 - 0.50 = 0.22), not from 0.90 (0.40).
        self._make_strds("evt_gap", [
            ("2021-04-01", 0.90),
            ("2021-06-01", 0.70),
            ("2021-06-06", 0.72),
            ("2021-06-11", 0.50),
        ])
        self.assertModule(
            "t.rast.eventdetect", input="evt_gap", year=2021,
            output="evt_gapout", direction="drop", threshold=0.2,
            lookback=2, baseline_window=3, step=5, overwrite=True,
        )
        self.assertEqual(self._const("evt_gapout_count"), 1)
        self.assertAlmostEqual(
            self._const("evt_gapout_mean_magnitude"), 0.22, places=4)

    def test_baseline_contiguous_window(self):
        # With no gaps and no earlier event, the full window is used: the
        # magnitude is measured from the recent plateau top (0.80 - 0.50 = 0.30).
        self._make_strds("evt_cont", [
            ("2021-05-01", 0.80),
            ("2021-05-06", 0.78),
            ("2021-05-11", 0.72),
            ("2021-05-16", 0.50),
        ])
        self.assertModule(
            "t.rast.eventdetect", input="evt_cont", year=2021,
            output="evt_contout", direction="drop", threshold=0.2,
            lookback=2, baseline_window=3, step=5, overwrite=True,
        )
        self.assertEqual(self._const("evt_contout_count"), 1)
        self.assertAlmostEqual(
            self._const("evt_contout_mean_magnitude"), 0.30, places=4)

    def test_baseline_prev_event_bound(self):
        # Two drops with no cloud gap between them. The baseline window for the
        # second drop must stop at the first event, so its magnitude is measured
        # from the middle plateau (0.50 - 0.28 = 0.22), not from the pre-first-
        # drop level (0.80 - 0.28 = 0.52), even with a large baseline_window.
        # magnitudes: drop1 = 0.30, drop2 = 0.22 -> mean 0.26, max 0.30.
        self._make_strds("evt_two", [
            ("2021-05-01", 0.80),
            ("2021-05-02", 0.80),
            ("2021-05-03", 0.80),
            ("2021-05-04", 0.50),
            ("2021-05-05", 0.50),
            ("2021-05-06", 0.50),
            ("2021-05-07", 0.50),
            ("2021-05-08", 0.28),
        ])
        self.assertModule(
            "t.rast.eventdetect", input="evt_two", year=2021,
            output="evt_twoout", direction="drop", threshold=0.2,
            lookback=2, baseline_window=6, step=1, overwrite=True,
        )
        self.assertEqual(self._const("evt_twoout_count"), 2)
        self.assertAlmostEqual(
            self._const("evt_twoout_mean_magnitude"), 0.26, places=4)
        self.assertAlmostEqual(
            self._const("evt_twoout_max_magnitude"), 0.30, places=4)


if __name__ == "__main__":
    test()

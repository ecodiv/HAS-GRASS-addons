"""Test t.rast.event on synthetic strds with known events.

The main series (5-day spacing, 2021) rises, drops sharply (event 1),
recovers, rises again, drops (event 2) and recovers:

    DOY 100 105 110 115 |120| 125 130 135 140 |145| 150 155
    NDVI .60 .65 .70 .72 .50  .55 .62 .70 .72  .48  .55 .68
                         ^event1              ^event2

Each drop is one continuous descent, so the peak-to-trough method reports
2 events, first at DOY 120 (the first trough), both recovered (target 0.8),
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

    def _datatype(self, raster):
        """Return the storage type (CELL/FCELL/DCELL) of a raster."""
        return gs.raster_info(raster)["datatype"]

    def _doy_label(self, raster, value):
        """Return the category label attached to an integer value."""
        txt = gs.read_command("r.category", map=raster, values=value,
                              separator="tab")
        return txt.strip().split("\t")[1]

    def _make_strds(self, strds, series):
        """Build a constant-value strds; a value of None registers a NULL map."""
        register = []
        for i, (date, value) in enumerate(series):
            name = f"{strds}_{i:02d}"
            expr = "double(null())" if value is None else f"double({value})"
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

    def test_counts_and_recovery(self):
        self.assertModule(
            "t.rast.event", input=self.strds, year=2021,
            output=self.prefix, direction="drop", threshold=0.2,
            threshold_type="absolute", recovery_target=0.8, overwrite=True,
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
            "t.rast.event", input=self.strds, year=2021,
            output="evt_pout", vector="evt_parcel", direction="drop",
            threshold=0.2, threshold_type="absolute", recovery_target=0.8,
            overwrite=True,
        )
        self.assertRasterExists("evt_pout_count")
        self.assertEqual(self._const("evt_pout_count"), 2)
        self.assertEqual(self._const("evt_pout_first_doy"), 120)
        self.assertEqual(self._const("evt_pout_last_doy"), 145)
        self.assertAlmostEqual(
            self._const("evt_pout_mean_recovery_days"), 12.5, places=3)

    def test_null_not_read_as_zero(self):
        # A NULL (cloud) observation must not be read as 0 and mistaken for a
        # drop. A flat clear series with one NULL in the middle has no events.
        self._make_strds("evt_null", [
            ("2021-05-01", 0.70),
            ("2021-05-06", 0.70),
            ("2021-05-11", None),
            ("2021-05-16", 0.70),
            ("2021-05-21", 0.70),
        ])
        self.assertModule(
            "t.rast.event", input="evt_null", year=2021,
            output="evt_nullout", direction="drop", threshold=0.2, step=5,
            overwrite=True,
        )
        self.assertEqual(self._const("evt_nullout_count"), 0)

    def test_single_multistep_decline(self):
        # A multi-step decline is one event, with magnitude measured
        # peak-to-trough (0.80 - 0.40 = 0.40).
        self._make_strds("evt_prom", [
            ("2021-05-01", 0.80),
            ("2021-05-06", 0.80),
            ("2021-05-11", 0.70),
            ("2021-05-16", 0.55),
            ("2021-05-21", 0.40),
            ("2021-05-26", 0.55),
            ("2021-05-31", 0.75),
            ("2021-06-05", 0.80),
        ])
        self.assertModule(
            "t.rast.event", input="evt_prom", year=2021,
            output="evt_promout", direction="drop", threshold=0.2, step=5,
            overwrite=True,
        )
        self.assertEqual(self._const("evt_promout_count"), 1)
        self.assertAlmostEqual(
            self._const("evt_promout_max_magnitude"), 0.40, places=4)

    def test_noise_tolerance(self):
        # A rebound part-way down the decline: with the default tolerance it is
        # one event; a smaller tolerance splits it into two.
        self._make_strds("evt_nt", [
            ("2021-05-01", 0.80),
            ("2021-05-06", 0.55),
            ("2021-05-11", 0.57),
            ("2021-05-16", 0.35),
            ("2021-05-21", 0.70),
        ])
        self.assertModule(
            "t.rast.event", input="evt_nt", year=2021, output="evt_ntA",
            direction="drop", threshold=0.2, step=5, overwrite=True,
        )
        self.assertEqual(self._const("evt_ntA_count"), 1)
        self.assertModule(
            "t.rast.event", input="evt_nt", year=2021, output="evt_ntB",
            direction="drop", threshold=0.2, step=5, noise_tolerance=0.05,
            overwrite=True,
        )
        self.assertEqual(self._const("evt_ntB_count"), 2)

    def test_amplitude_at_threshold(self):
        # A drop whose amplitude equals the threshold exactly (0.80 - 0.60 =
        # 0.20) must be counted (a small epsilon absorbs float rounding).
        self._make_strds("evt_thr", [
            ("2021-05-01", 0.80),
            ("2021-05-06", 0.60),
            ("2021-05-11", 0.80),
        ])
        self.assertModule(
            "t.rast.event", input="evt_thr", year=2021,
            output="evt_throut", direction="drop", threshold=0.2, step=5,
            overwrite=True,
        )
        self.assertEqual(self._const("evt_throut_count"), 1)

    def test_cell_types_and_doy_labels(self):
        # Integer counts and day-of-year outputs are CELL; continuous outputs
        # stay DCELL. The day-of-year rasters carry the calendar date as the
        # category label of each value.
        self.assertModule(
            "t.rast.event", input=self.strds, year=2021,
            output="evt_types", direction="drop", threshold=0.2,
            recovery_target=0.8, overwrite=True,
        )
        for suffix in ("count", "first_doy", "last_doy", "n_recovered",
                       "n_incomplete"):
            self.assertEqual(self._datatype(f"evt_types_{suffix}"), "CELL",
                             msg=f"{suffix} should be CELL")
        for suffix in ("mean_magnitude", "frac_recovered",
                       "mean_recovery_days"):
            self.assertEqual(self._datatype(f"evt_types_{suffix}"), "DCELL",
                             msg=f"{suffix} should be DCELL")
        self.assertEqual(self._doy_label("evt_types_first_doy", 120),
                         "2021-04-30")

    def test_multi_year(self):
        # A two-year strds run without year= is analyzed per calendar year.
        # Each metric becomes one strds with a year-suffixed raster per year,
        # and the day-of-year labels use each raster's own year.
        series = []
        for yr in (2021, 2022):
            series += [(f"{yr}-04-25", 0.72), (f"{yr}-04-30", 0.50),
                       (f"{yr}-05-05", 0.72)]
        self._make_strds("evt_my", series)
        self.assertModule(
            "t.rast.event", input="evt_my", output="evt_myout",
            direction="drop", threshold=0.2, step=5, overwrite=True,
        )
        metrics = ("count", "first_doy", "last_doy", "mean_magnitude",
                   "max_magnitude", "n_recovered", "frac_recovered",
                   "mean_recovery_days", "mean_percent_restored",
                   "n_incomplete")
        for suffix in metrics:
            self.addCleanup(self.runModule, "t.remove", flags="df",
                            type="strds", inputs=f"evt_myout_{suffix}")
        for yr in (2021, 2022):
            self.assertRasterExists(f"evt_myout_count_{yr}")
            self.assertEqual(self._const(f"evt_myout_count_{yr}"), 1)
            self.assertEqual(self._const(f"evt_myout_first_doy_{yr}"), 120)
            self.assertEqual(self._doy_label(f"evt_myout_first_doy_{yr}", 120),
                             f"{yr}-04-30")
        # the per-metric strds holds one layer per year
        names = gs.read_command(
            "t.rast.list", input="evt_myout_count", columns="name", flags="u",
        ).split()
        self.assertEqual(sorted(names),
                         ["evt_myout_count_2021", "evt_myout_count_2022"])

    def test_streaming_matches_single_strip(self):
        # Pixel mode streams the region in row strips sized from memory=. A run
        # forced into many strips (tiny memory, wide region) must give exactly
        # the same rasters as a single-strip run. The event pattern varies by
        # row (even rows drop, odd rows do not), so the strips carry different
        # results and a broken strip loop would show up.
        self.runModule("g.region", n=20, s=0, e=4000, w=0, res=1)
        self.addCleanup(self.runModule, "g.region", n=3, s=0, e=3, w=0, res=1)
        self._make_strds("evt_strm", [
            ("2021-05-01", "0.80"),
            ("2021-05-06", "0.80"),
            ("2021-05-11", "if(row()%2==0, 0.50, 0.80)"),
            ("2021-05-16", "0.80"),
            ("2021-05-21", "0.80"),
        ])
        common = dict(input="evt_strm", year=2021, direction="drop",
                      threshold=0.2, step=5, overwrite=True)
        # memory=2000 -> one strip (20 rows); memory=1 -> one row per strip.
        self.assertModule("t.rast.event", output="evt_strmA",
                          memory=2000, **common)
        self.assertModule("t.rast.event", output="evt_strmB",
                          memory=1, **common)
        for suffix in ("count", "first_doy", "n_recovered"):
            self.assertRastersNoDifference(
                f"evt_strmA_{suffix}", f"evt_strmB_{suffix}", precision=0)
        self.assertRastersNoDifference(
            "evt_strmA_mean_recovery_days", "evt_strmB_mean_recovery_days",
            precision=1e-6)
        # sanity: some pixels have an event and some none
        info = gs.raster_info("evt_strmA_count")
        self.assertEqual(info["min"], 0)
        self.assertEqual(info["max"], 1)

    def test_recovery_invariant(self):
        # An event awaiting recovery while a new, still-subthreshold descent is
        # active at series end must be resolved as incomplete, so that
        # count = n_recovered + interrupted + n_incomplete holds.
        self._make_strds("evt_inv", [
            ("2021-05-01", 0.80),
            ("2021-05-06", 0.40),
            ("2021-05-11", 0.60),
            ("2021-05-16", 0.55),
        ])
        self.assertModule(
            "t.rast.event", input="evt_inv", year=2021,
            output="evt_invout", direction="drop", threshold=0.2, step=5,
            overwrite=True,
        )
        self.assertEqual(self._const("evt_invout_count"), 1)
        self.assertEqual(self._const("evt_invout_n_recovered"), 0)
        self.assertEqual(self._const("evt_invout_n_incomplete"), 1)

    def test_groupby_none_annual(self):
        # One value per year, analyzed as a single continuous series. A one-year
        # drop (0.80 -> 0.40) recovers over the following years, so it is one
        # recovered event. In groupby=none the day-of-year outputs hold the days
        # since the first observation, with the calendar date as the label.
        self._make_strds("evt_ann", [
            ("2015-01-01", 0.70),
            ("2016-01-01", 0.80),
            ("2017-01-01", 0.40),
            ("2018-01-01", 0.60),
            ("2019-01-01", 0.80),
            ("2020-01-01", 0.80),
        ])
        self.assertModule(
            "t.rast.event", input="evt_ann", groupby="none",
            output="evt_annout", direction="drop", threshold=0.2,
            recovery_target=0.8, overwrite=True,
        )
        self.assertEqual(self._const("evt_annout_count"), 1)
        self.assertEqual(self._const("evt_annout_n_recovered"), 1)
        self.assertAlmostEqual(
            self._const("evt_annout_max_magnitude"), 0.40, places=4)
        # trough at 2017-01-01 = 731 days after the first observation
        self.assertEqual(self._const("evt_annout_first_doy"), 731)
        self.assertEqual(self._doy_label("evt_annout_first_doy", 731),
                         "2017-01-01")
        # recovered at 2019-01-01, 730 days after the trough
        self.assertAlmostEqual(
            self._const("evt_annout_mean_recovery_days"), 730, places=1)

    def test_year_start_monsoon(self):
        # A December drop that recovers the next January-February. With a
        # July-anchored year (year_start=07-01) the drop and its recovery fall in
        # one cycle and the event is recovered. With the default calendar year
        # they are split, so the 2020 cycle sees only an incomplete event.
        series = [
            ("2020-11-01", 0.80),
            ("2020-12-01", 0.40),
            ("2021-01-01", 0.60),
            ("2021-02-01", 0.80),
        ]
        self._make_strds("evt_mon", series)
        self.assertModule(
            "t.rast.event", input="evt_mon", year_start="07-01",
            output="evt_monout", direction="drop", threshold=0.2,
            recovery_target=0.8, overwrite=True,
        )
        self.assertEqual(self._const("evt_monout_count"), 1)
        self.assertEqual(self._const("evt_monout_n_recovered"), 1)
        self.assertEqual(self._const("evt_monout_n_incomplete"), 0)
        # the trough is 2020-12-01 (calendar day-of-year 336 in a leap year)
        self.assertEqual(self._const("evt_monout_first_doy"), 336)
        self.assertEqual(self._doy_label("evt_monout_first_doy", 336),
                         "2020-12-01")

        # default calendar-year grouping splits the drop from its recovery
        self.assertModule(
            "t.rast.event", input="evt_mon", output="evt_calout",
            direction="drop", threshold=0.2, recovery_target=0.8,
            overwrite=True,
        )
        metrics = ("count", "first_doy", "last_doy", "mean_magnitude",
                   "max_magnitude", "n_recovered", "frac_recovered",
                   "mean_recovery_days", "mean_percent_restored",
                   "n_incomplete")
        for suffix in metrics:
            self.addCleanup(self.runModule, "t.remove", flags="df",
                            type="strds", inputs=f"evt_calout_{suffix}")
        self.assertEqual(self._const("evt_calout_count_2020"), 1)
        self.assertEqual(self._const("evt_calout_n_incomplete_2020"), 1)
        self.assertEqual(self._const("evt_calout_n_recovered_2020"), 0)

    def test_gap_diagnostics(self):
        # The -g flag writes n_obs / mean_gap / max_gap_obs from the in-season
        # observations (spacings here are 5, 15, 5 days).
        self._make_strds("evt_gaps", [
            ("2021-05-01", 0.50),
            ("2021-05-06", 0.50),
            ("2021-05-21", 0.50),
            ("2021-05-26", 0.50),
        ])
        self.assertModule(
            "t.rast.event", input="evt_gaps", year=2021,
            output="evt_gapsout", direction="drop", threshold=0.2, step=5,
            flags="g", overwrite=True,
        )
        self.assertEqual(self._const("evt_gapsout_n_obs"), 4)
        self.assertEqual(self._datatype("evt_gapsout_n_obs"), "CELL")
        self.assertAlmostEqual(
            self._const("evt_gapsout_max_gap_obs"), 15, places=4)


if __name__ == "__main__":
    test()

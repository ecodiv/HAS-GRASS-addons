#!/usr/bin/env python3

############################################################################
#
# MODULE:       test_r_histogram
# AUTHOR:       Paulo van Breugel
# PURPOSE:      Tests for r.histogram.
#
# SPDX-FileCopyrightText: 2026 Paulo van Breugel
# SPDX-FileCopyrightText: Other GRASS authors
# SPDX-License-Identifier: GPL-2.0-or-later
#
#############################################################################

import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import grass.script as gs
from grass.gunittest.case import TestCase
from grass.gunittest.main import test


def load_r_histogram():
    """Load the module source so its computational helpers can be tested."""
    source = Path(__file__).resolve().parents[1] / "r.histogram.py"
    spec = importlib.util.spec_from_file_location("r_histogram", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRHistogram(TestCase):
    value_raster = "test_histogram_values"
    null_raster = "test_histogram_null"

    @classmethod
    def setUpClass(cls):
        cls.use_temp_region()
        cls.runModule("g.region", n=10, s=0, w=0, e=10, res=1)
        cls.runModule(
            "r.mapcalc",
            expression=f"{cls.value_raster} = (row() - 1) * 10 + col()",
            overwrite=True,
        )
        cls.runModule(
            "r.mapcalc",
            expression=f"{cls.null_raster} = null()",
            overwrite=True,
        )
        gs.write_command(
            "r.colors",
            map=cls.value_raster,
            rules="-",
            stdin="1 red\n100 blue\n",
            quiet=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.del_temp_region()
        cls.runModule(
            "g.remove",
            flags="f",
            type="raster",
            name=[cls.value_raster, cls.null_raster],
        )

    def test_equal_width_bin_counts(self):
        """The GRASS aggregation returns the expected equal-width counts."""
        module = load_r_histogram()
        try:
            counts, edges, centers = module.histogram_data(self.value_raster, 5)
            self.assertEqual(counts, [20, 20, 20, 20, 20])
            self.assertEqual(len(edges), 6)
            self.assertEqual(len(centers), 5)
            self.assertAlmostEqual(edges[0], 1)
            self.assertAlmostEqual(edges[-1], 100)
        finally:
            module.cleanup()

    def test_raster_colors_follow_color_table(self):
        """Bin colors are queried from the raster color table."""
        module = load_r_histogram()
        colors = module.raster_colors(self.value_raster, [1, 100])
        self.assertGreater(colors[0][0], colors[0][2])
        self.assertGreater(colors[1][2], colors[1][0])

    def test_raster_colors_with_text_mode_process(self):
        """Color lookup supports GRASS subprocesses opened in text mode."""
        module = load_r_histogram()

        class TextProcess:
            stdin = SimpleNamespace(encoding="UTF-8")
            returncode = 0
            received = None

            def communicate(self, input):
                self.received = input
                return "1: 255:0:0\n", ""

        process = TextProcess()
        with patch.object(module.gs, "pipe_command", return_value=process):
            colors = module.raster_colors(self.value_raster, [1])
        self.assertIsInstance(process.received, str)
        self.assertEqual(colors, [[1, 0, 0]])

    def test_mask_is_respected(self):
        """Histogram ranges and counts reflect the active raster mask."""
        module = load_r_histogram()
        try:
            self.runModule(
                "r.mapcalc",
                expression=f"MASK = if({self.value_raster} <= 50, 1, null())",
            )
            counts, edges, _centers = module.histogram_data(self.value_raster, 5)
            self.assertEqual(counts, [10, 10, 10, 10, 10])
            self.assertAlmostEqual(edges[0], 1)
            self.assertAlmostEqual(edges[-1], 50)
        finally:
            self.runModule("r.mask", flags="r")
            module.cleanup()

    def test_output_file_created(self):
        """The module writes a non-empty image file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as stream:
            output = stream.name
        try:
            self.assertModule(
                "r.histogram",
                map=self.value_raster,
                bins=5,
                output=output,
                overwrite=True,
            )
            self.assertTrue(os.path.isfile(output))
            self.assertGreater(os.path.getsize(output), 0)
        finally:
            if os.path.exists(output):
                os.remove(output)

    def test_raster_colors_and_horizontal_output(self):
        """Raster colors and horizontal layout can be used together."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as stream:
            output = stream.name
        try:
            self.assertModule(
                "r.histogram",
                map=self.value_raster,
                bins=7,
                output=output,
                flags="chg",
                overwrite=True,
            )
            self.assertTrue(os.path.isfile(output))
            self.assertGreater(os.path.getsize(output), 0)
        finally:
            if os.path.exists(output):
                os.remove(output)

    def test_fails_for_null_raster(self):
        """A raster without non-NULL cells fails with a clean error."""
        output = os.path.join(tempfile.gettempdir(), "r_histogram_null.png")
        try:
            self.assertModuleFail("r.histogram", map=self.null_raster, output=output)
        finally:
            if os.path.exists(output):
                os.remove(output)

    def test_fails_for_zero_bins(self):
        """The number of bins must be positive."""
        output = os.path.join(tempfile.gettempdir(), "r_histogram_bins.png")
        try:
            self.assertModuleFail(
                "r.histogram", map=self.value_raster, bins=0, output=output
            )
        finally:
            if os.path.exists(output):
                os.remove(output)


if __name__ == "__main__":
    test()

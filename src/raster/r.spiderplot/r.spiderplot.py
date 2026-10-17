#!/usr/bin/env python3

############################################################################
#
# MODULE:       r.spiderplot
# AUTHOR:       Paulo van Breugel
# PURPOSE:      Draws a spider (radar) plot of the values of two or more
#               raster layers sampled at a point. Each raster provides one
#               axis; the axis range is user-defined or computed from the
#               raster. Launched from a Map Display, the point can be
#               selected by clicking in the display.
#
# SPDX-FileCopyrightText: 2026 Paulo van Breugel
# SPDX-FileCopyrightText: Other GRASS authors
# SPDX-License-Identifier: GPL-2.0-or-later
#
#############################################################################

# %module
# % description: Draws a spider (radar) plot of the values of two or more rasters at a point or vector features.
# % keyword: display
# % keyword: raster
# % keyword: plot
# % keyword: spiderplot
# % keyword: radar
# %end

# %option G_OPT_R_INPUTS
# % key: input
# % label: Input rasters
# % description: Two or more raster maps. Each raster becomes one axis of the spider plot.
# % required: yes
# % guisection: Input
# %end

# %option G_OPT_M_COORDS
# % key: coordinates
# % required: no
# % label: Point coordinates (east,north)
# % description: Comma separated pair of map coordinates of the point to sample. In the GUI (launched from a Map Display) the value can be filled by clicking in the display.
# % guisection: Input
# %end

# %option G_OPT_V_MAP
# % key: map
# % required: no
# % label: Vector points or areas to sample
# % description: Sample the rasters at the features of this vector map instead of a single coordinate. Points are drawn as separate lines; areas are aggregated per class into a mean plus standard-deviation band.
# % guisection: Input
# %end

# %option G_OPT_DB_COLUMN
# % key: group_column
# % required: no
# % label: Grouping column
# % description: Attribute column whose value defines the classes. Features sharing a value are aggregated into one class (one facet). Without it, areas are grouped by category and points are drawn as separate lines.
# % guisection: Input
# %end

# %option G_OPT_V_CATS
# % key: cats
# % required: no
# % label: Category subset
# % description: Only sample features with these categories (vector input).
# % guisection: Input
# %end

# %option G_OPT_DB_WHERE
# % key: where
# % required: no
# % label: WHERE subset
# % description: Only sample features matching this SQL WHERE condition (vector input).
# % guisection: Input
# %end

# %option
# % key: minimum
# % type: string
# % multiple: yes
# % label: Axis minima
# % description: Lower end of each axis, one value per input raster (same order). Leave an entry empty to compute it from the raster. Omit the option to compute all minima.
# % required: no
# % guisection: Input
# %end

# %option
# % key: maximum
# % type: string
# % multiple: yes
# % label: Axis maxima
# % description: Upper end of each axis, one value per input raster (same order). Leave an entry empty to compute it from the raster. Omit the option to compute all maxima.
# % required: no
# % guisection: Input
# %end

# %option
# % key: labels
# % type: string
# % multiple: yes
# % label: Axis labels
# % description: Label for each axis, one per input raster (same order). Defaults to the raster names.
# % required: no
# % guisection: Input
# %end

# %option G_OPT_F_OUTPUT
# % key: output
# % required: no
# % label: Output image file
# % description: Output image file. The format is taken from the extension (e.g. .png, .pdf, .svg). If omitted, the plot is shown in an interactive window.
# % guisection: Output
# %end

# %option
# % key: plot_dimensions
# % type: string
# % label: Plot dimensions (width,height)
# % description: Width and height of the plot in inches. Default is 7,7.
# % required: no
# % guisection: Output
# %end

# %option
# % key: dpi
# % type: integer
# % label: DPI
# % description: Resolution of the output image in dots per inch.
# % required: no
# % guisection: Output
# %end

# %option
# % key: title
# % type: string
# % label: Plot title
# % description: Optional title above the plot.
# % required: no
# % guisection: Plot format
# %end

# %option
# % key: fontsize
# % type: integer
# % label: Font size
# % description: Base font size.
# % answer: 10
# % required: no
# % guisection: Plot format
# %end

# %option
# % key: title_fontsize
# % type: integer
# % label: Title font size
# % description: Font size of the title. Defaults to the base font size.
# % required: no
# % guisection: Plot format
# %end

# %option
# % key: font
# % type: string
# % label: Font family
# % description: Font family for all text (e.g. sans-serif, serif, DejaVu Sans).
# % required: no
# % guisection: Plot format
# %end

# %option
# % key: style
# % type: string
# % label: Matplotlib style
# % description: Matplotlib style sheet, see https://matplotlib.org/stable/gallery/style_sheets/style_sheets_reference.html
# % required: no
# % guisection: Plot format
# % options: _mpl-gallery,_mpl-gallery-nogrid,bmh,classic,dark_background,fast,fivethirtyeight,ggplot,grayscale,seaborn-v0_8,seaborn-v0_8-bright,seaborn-v0_8-colorblind,seaborn-v0_8-dark,seaborn-v0_8-dark-palette,seaborn-v0_8-darkgrid,seaborn-v0_8-deep,seaborn-v0_8-muted,seaborn-v0_8-notebook,seaborn-v0_8-paper,seaborn-v0_8-pastel,seaborn-v0_8-poster,seaborn-v0_8-talk,seaborn-v0_8-ticks,seaborn-v0_8-white,seaborn-v0_8-whitegrid,Solarize_Light2,tableau-colorblind10
# %end

# %flag
# % key: l
# % label: Label grid rings
# % description: Print the value of each grid ring (as a fraction of each axis range) along the reference axis.
# % guisection: Plot format
# %end

# %flag
# % key: n
# % label: Show values
# % description: Print the sampled value at each axis vertex.
# % guisection: Plot format
# %end

# %flag
# % key: r
# % label: Show axis ranges
# % description: Append the [min, max] range to each axis label.
# % guisection: Plot format
# %end

# %option G_OPT_CN
# % key: color
# % label: Color
# % description: Color of the plotted line (and fill). Defaults to the style palette. See manual for color notation.
# % required: no
# % answer:
# % guisection: Spider format
# %end

# %option
# % key: line_width
# % type: double
# % label: Line width
# % description: Width of the plotted line.
# % answer: 1.5
# % required: no
# % guisection: Spider format
# %end

# %option
# % key: fill_alpha
# % type: double
# % options: 0-1
# % label: Fill transparency
# % description: Opacity of the filled polygon. Set to 0 for no fill.
# % answer: 0.25
# % required: no
# % guisection: Spider format
# %end

# %option
# % key: band_alpha
# % type: double
# % options: 0-1
# % label: Band transparency
# % description: Opacity of the standard-deviation band drawn for aggregated (class) inputs.
# % answer: 0.15
# % required: no
# % guisection: Spider format
# %end

# %option G_OPT_M_NPROCS
# %end

# %option G_OPT_MEMORYMB
# %end

# %rules
# % required: coordinates,map
# % exclusive: coordinates,map
# % requires: group_column,map
# % requires: cats,map
# % requires: where,map
# %end

import atexit
import os
import sys
from collections import namedtuple

import grass.script as gs
from grass.script import RegionManager
from grass.tools import Tools

# A single spider outline. ``values`` are the raw (un-normalized) values, one
# per input raster. ``lower``/``upper`` hold the raw band bounds (e.g.
# mean +/- stddev) and are None for a plain point. ``color`` is an optional
# per-series color; None lets Matplotlib pick from the palette.
Series = namedtuple("Series", ["name", "values", "lower", "upper", "color"])

clean_layers = []


def create_temporary_name(prefix):
    """Create a temporary map name and register it for cleanup."""
    tmpf = gs.append_node_pid(prefix)
    clean_layers.append(tmpf)
    return tmpf


def cleanup():
    """Remove temporary maps."""
    mapset = gs.gisenv()["MAPSET"]
    for name in reversed(clean_layers):
        for element in ("raster", "vector"):
            if gs.find_file(name=name, element=element, mapset=mapset)["file"]:
                gs.run_command(
                    "g.remove", flags="f", type=element, name=name, quiet=True
                )


def lazy_import_py_modules(to_file):
    """Lazy import matplotlib, using a non-interactive backend when saving.

    :param bool to_file: True when the plot is written to an image file
    """
    global mpl
    global plt
    try:
        import matplotlib as mpl

        mpl.use("Agg" if to_file else "WXAgg")
        from matplotlib import pyplot as plt
    except ModuleNotFoundError:
        gs.fatal(_("Matplotlib is not installed. Please, install it."))


def strip_mapset(name, join_char="@"):
    """Strip the mapset suffix from a map name."""
    return name.split(join_char)[0] if join_char in name else name


def check_map_exists(name):
    """Fail with a clean message if the raster map does not exist.

    :param str name: name of the raster map
    """
    if not gs.find_file(name=name, element="cell")["file"]:
        gs.fatal(_("Raster map <{}> not found").format(name))


def get_valid_color(color):
    """Return a Matplotlib-compatible color from a GRASS color notation.

    :param str color: color as name, hex or R:G:B

    :return str|list: color usable by Matplotlib
    """
    if ":" in color:
        color = [int(x) / 255 for x in color.split(":")]
    if not mpl.colors.is_color_like(color):
        gs.fatal(_("{} is not a valid color.").format(color))
    return color


def format_value(value):
    """Format a value for display on the plot or in an axis label."""
    return f"{value:g}"


def coords_from_option(coordinates):
    """Parse the coordinates= option into an (east, north) float pair.

    :param str coordinates: "east,north" as given on the command line

    :return tuple: (east, north) as floats
    """
    parts = coordinates.split(",")
    if len(parts) != 2:
        gs.fatal(_("The coordinates option must be a single 'east,north' pair."))
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        gs.fatal(_("Could not parse coordinates '{}' as numbers.").format(coordinates))


def parse_bound_list(option, n, name):
    """Parse a per-raster bound option into a list of floats or None.

    An empty option yields all-None (compute every bound). Otherwise the
    number of entries must match the number of rasters; an empty entry means
    "compute this one".

    :param str option: raw comma-separated option value
    :param int n: number of input rasters
    :param str name: option name, for error messages

    :return list: list of length n with floats or None
    """
    if not option:
        return [None] * n
    parts = option.split(",")
    if len(parts) != n:
        gs.fatal(
            _(
                "The '{name}' option has {got} values but there are {n} input "
                "rasters. Provide one value per raster (an entry may be left "
                "empty to compute it)."
            ).format(name=name, got=len(parts), n=n)
        )
    bounds = []
    for part in parts:
        part = part.strip()
        bounds.append(float(part) if part else None)
    return bounds


def raster_range(tools, raster, nprocs):
    """Return the (min, max) value range of a raster.

    Uses the cached range from r.info and falls back to r.univar when the
    raster has no range recorded yet. Both are read as JSON.

    :param Tools tools: the grass.tools session runner
    :param str raster: name of the raster map
    :param int nprocs: number of r.univar threads for the fallback

    :return tuple: (minimum, maximum) as floats
    """
    info = tools.r_info(map=raster, format="json").json
    low, high = info.get("min"), info.get("max")
    if low is None or high is None:
        stats = tools.r_univar(map=raster, format="json", nprocs=nprocs).json
        if isinstance(stats, list):
            stats = stats[0]
        low, high = stats["min"], stats["max"]
    return float(low), float(high)


def resolve_ranges(tools, rasters, minima, maxima, nprocs):
    """Resolve the (min, max) range for every axis.

    User-provided bounds win; missing ones are computed from the raster.

    :param Tools tools: the grass.tools session runner
    :param list rasters: input raster names
    :param list minima: per-raster minima (floats or None)
    :param list maxima: per-raster maxima (floats or None)
    :param int nprocs: number of r.univar threads when a bound is computed

    :return list: list of (low, high) tuples aligned with rasters
    """
    ranges = []
    for raster, low, high in zip(rasters, minima, maxima):
        if low is None or high is None:
            data_low, data_high = raster_range(tools, raster, nprocs)
            low = data_low if low is None else low
            high = data_high if high is None else high
        if high < low:
            gs.fatal(
                _("Axis range for <{r}> is inverted (min {lo} > max {hi}).").format(
                    r=strip_mapset(raster), lo=low, hi=high
                )
            )
        if high == low:
            gs.warning(
                _(
                    "Raster <{r}> has a zero-width range ({v}); its axis will "
                    "be drawn at the center."
                ).format(r=strip_mapset(raster), v=low)
            )
        ranges.append((low, high))
    return ranges


def normalize(value, axis_range):
    """Scale a raw value to [0, 1] along its axis range, clamped.

    :param float value: raw value (or None for a NULL sample)
    :param tuple axis_range: (low, high) for the axis

    :return float: value in [0, 1]
    """
    if value is None:
        return 0.0
    low, high = axis_range
    if high == low:
        return 0.5
    return min(1.0, max(0.0, (value - low) / (high - low)))


def sample_point(tools, rasters, east, north):
    """Sample every raster at a single point with r.what.

    :param Tools tools: the grass.tools session runner
    :param list rasters: input raster names
    :param float east: easting of the point
    :param float north: northing of the point

    :return list: one Series with the sampled values (NULLs as None)
    """
    # r.what JSON: a list with one object per point, holding the coordinates
    # and, per raster, a {"value": <number|null>} entry keyed by the exact
    # raster name that was passed in.
    data = tools.r_what(
        map=rasters,
        coordinates=[east, north],
        format="json",
    ).json
    if not data:
        gs.fatal(_("The point does not fall within the current region."))
    point = data[0]
    values = [point[raster]["value"] for raster in rasters]
    if all(v is None for v in values):
        gs.fatal(_("All rasters are NULL at this point; nothing to plot."))
    for raster, value in zip(rasters, values):
        if value is None:
            gs.warning(
                _("Raster <{}> is NULL at this point.").format(strip_mapset(raster))
            )
    name = "{}, {}".format(format_value(east), format_value(north))
    return [Series(name=name, values=values, lower=None, upper=None, color=None)]


# ---------------------------------------------------------------------------
# Vector data sources. A vector map is sampled at its features instead of a
# single coordinate. Point maps without a grouping column become one line per
# point; otherwise features are aggregated into classes (one Series each, with
# a mean line and a +/- stddev band) and drawn as facets.
# ---------------------------------------------------------------------------


def vector_geometry(tools, vector):
    """Return 'area' or 'point' for a vector map based on its topology.

    :param Tools tools: the grass.tools session runner
    :param str vector: name of the vector map

    :return str: "area" if it has areas, otherwise "point"
    """
    topology = tools.v_info(map=vector, flags="t").keyval
    if int(topology.get("areas", 0)) > 0:
        return "area"
    if int(topology.get("points", 0)) > 0:
        return "point"
    gs.fatal(_("Vector map <{}> has no points or areas to sample.").format(vector))


def subset_vector(tools, vector, cats, where):
    """Return a temporary vector limited to cats/where, or the input map.

    :param Tools tools: the grass.tools session runner
    :param str vector: name of the vector map
    :param str cats: category subset, or ""
    :param str where: SQL WHERE subset, or ""

    :return str: the (possibly temporary) vector map to sample
    """
    if not cats and not where:
        return vector
    selected = create_temporary_name("spider_sel_")
    kwargs = {}
    if cats:
        kwargs["cats"] = cats
    if where:
        kwargs["where"] = where
    tools.v_extract(input=vector, output=selected, **kwargs)
    return selected


def group_map(tools, vector, group_column):
    """Map each category to its class value from an attribute column.

    :param Tools tools: the grass.tools session runner
    :param str vector: name of the vector map
    :param str group_column: attribute column defining the classes

    :return dict: {cat: class_value}
    """
    records = tools.v_db_select(
        map=vector, columns="cat,{}".format(group_column), format="json"
    ).json["records"]
    return {rec["cat"]: rec[group_column] for rec in records}


def pool(stats):
    """Pool per-cat (n, mean, stddev) triples into one (mean, stddev).

    Reconstructs the population mean and standard deviation of the union of
    all cells from the per-cat counts, means and (population) standard
    deviations.

    :param list stats: list of (n, mean, stddev) triples

    :return tuple: (mean, stddev) of the pooled cells, or (None, None)
    """
    total = sum(n for n, _, _ in stats if n)
    if not total:
        return None, None
    sum_x = sum(n * mean for n, mean, _ in stats)
    sum_x2 = sum(n * (sd * sd + mean * mean) for n, mean, sd in stats)
    mean = sum_x / total
    variance = max(0.0, sum_x2 / total - mean * mean)
    return mean, variance**0.5


def sample_point_lines(tools, rasters, vector):
    """Sample every raster at each point of a vector points map.

    :param Tools tools: the grass.tools session runner
    :param list rasters: input raster names
    :param str vector: name of the vector points map

    :return list: one Series per point (no band)
    """
    data = tools.r_what(map=rasters, points=vector, format="json").json
    series = []
    for point in data:
        values = [point[raster]["value"] for raster in rasters]
        label = point.get("site_name") or "{}, {}".format(
            point["easting"], point["northing"]
        )
        series.append(
            Series(name=label, values=values, lower=None, upper=None, color=None)
        )
    return series


def sample_point_classes(tools, rasters, vector, group_column):
    """Aggregate points into classes: mean and stddev per raster per class.

    :param Tools tools: the grass.tools session runner
    :param list rasters: input raster names
    :param str vector: name of the vector points map
    :param str group_column: attribute column defining the classes

    :return list: one Series per class, with a mean line and +/- stddev band
    """
    # Sample the points, and read the class value for each cat. r.what keeps
    # the input feature order and reports each point's category.
    data = tools.r_what(
        map=rasters, points=vector, flags="v", format="json"
    ).json
    classes = group_map(tools, vector, group_column)
    # class value -> per raster list of sampled values
    buckets = {}
    for point in data:
        cls = classes.get(point.get("cat"))
        if cls is None:
            continue
        rows = buckets.setdefault(cls, [[] for _ in rasters])
        for index, raster in enumerate(rasters):
            value = point[raster]["value"]
            if value is not None:
                rows[index].append(value)
    return [
        _series_from_columns(str(cls), buckets[cls]) for cls in sorted(buckets)
    ]


def _series_from_columns(name, columns):
    """Build a mean +/- stddev Series from per-axis lists of raw values.

    :param str name: class label
    :param list columns: per-axis list of sampled values

    :return Series: mean line with a +/- (population) stddev band
    """
    means, lowers, uppers = [], [], []
    for values in columns:
        if values:
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            sd = variance**0.5
        else:
            mean = sd = None
        means.append(mean)
        lowers.append(None if mean is None else mean - sd)
        uppers.append(None if mean is None else mean + sd)
    return Series(name=name, values=means, lower=lowers, upper=uppers, color=None)


# Only bother subdividing when the whole-layer box is genuinely large, and
# only when the classes together cover clearly less than the union box (so the
# saved gap-scanning outweighs the per-class rasterization and re-scanned
# borders). Below the cell threshold a single pass is already fast enough that
# the extra per-class process launches would not pay off.
_SUBDIVIDE_MIN_CELLS = 10_000_000
_SUBDIVIDE_FILL_FACTOR = 0.5


def feature_bboxes(tools, vector):
    """Return the bounding box of every feature: {cat: (n, s, e, w)}.

    Uses a single v.to.db pass (no rasterization), so per-class extents can be
    derived cheaply for the aggregation heuristic.

    :param Tools tools: the grass.tools session runner
    :param str vector: name of the vector map

    :return dict: {cat: (north, south, east, west)}
    """
    records = tools.v_to_db(
        map=vector, option="bbox", flags="p", format="json"
    ).json["records"]
    return {
        rec["category"]: (rec["north"], rec["south"], rec["east"], rec["west"])
        for rec in records
    }


def bbox_union(boxes):
    """Return the enclosing (n, s, e, w) of a list of bounding boxes."""
    return (
        max(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        min(b[3] for b in boxes),
    )


def bbox_cells(box, nsres, ewres):
    """Approximate cell count of a bounding box at the given resolution."""
    north, south, east, west = box
    return ((north - south) / nsres) * ((east - west) / ewres)


def zonal_stats(tools, rasters, zones, nprocs, keep=None):
    """Collect per-cat (n, mean, stddev) per raster from a zones raster.

    :param Tools tools: the grass.tools session runner
    :param list rasters: input raster names
    :param str zones: zones raster (cat values)
    :param int nprocs: number of r.univar threads
    :param set keep: only keep these zone ids, or None for all

    :return dict: {cat: [ (n, mean, stddev), ... ] aligned with rasters}
    """
    stats = {}
    for index, raster in enumerate(rasters):
        for row in tools.r_univar(
            map=raster, zones=zones, format="json", nprocs=nprocs
        ).json:
            cat = row["zone"]
            if keep is not None and cat not in keep:
                continue
            stats.setdefault(cat, [None] * len(rasters))[index] = (
                row["n"], row["mean"], row["stddev"]
            )
    return stats


def sample_area_classes(tools, rasters, vector, group_column, nprocs, memory):
    """Aggregate area features into classes: mean and stddev per raster.

    Areas are rasterized by category (so features sharing a category merge) and
    summarized with zonal r.univar; categories are then pooled into classes,
    either by category (default) or by a grouping column. Two strategies are
    chosen automatically from the feature bounding boxes: a single pass over the
    whole-layer box (best when the classes fill it), or one zoomed pass per
    class (best when the classes are compact and scattered over a large box).

    :param Tools tools: the grass.tools session runner
    :param list rasters: input raster names
    :param str vector: name of the vector areas map
    :param str group_column: attribute column defining the classes, or ""
    :param int nprocs: number of r.univar threads
    :param int memory: memory in MB for v.to.rast

    :return list: one Series per class, with a mean line and +/- stddev band
    """
    classes = group_map(tools, vector, group_column) if group_column else None
    bboxes = feature_bboxes(tools, vector)
    reg = gs.region()
    nsres, ewres = reg["nsres"], reg["ewres"]

    # Group categories into classes and get each class's combined bounding box.
    cats_by_class = {}
    for cat in bboxes:
        cls = classes.get(cat, cat) if classes else cat
        cats_by_class.setdefault(cls, []).append(cat)
    class_box = {
        cls: bbox_union([bboxes[c] for c in cats])
        for cls, cats in cats_by_class.items()
    }

    # Heuristic: subdivide only for a large union box that the classes leave
    # mostly empty.
    union_cells = bbox_cells(bbox_union(list(bboxes.values())), nsres, ewres)
    class_cells = sum(bbox_cells(b, nsres, ewres) for b in class_box.values())
    subdivide = (
        union_cells >= _SUBDIVIDE_MIN_CELLS
        and class_cells < _SUBDIVIDE_FILL_FACTOR * union_cells
    )

    zones = create_temporary_name("spider_zones_")
    # class value -> per raster list of (n, mean, stddev) triples to pool.
    buckets = {cls: [[] for _ in rasters] for cls in cats_by_class}

    if subdivide:
        gs.verbose(
            _("Aggregating {n} area classes one bounding box at a time.").format(
                n=len(cats_by_class)
            )
        )
        for cls, cats in cats_by_class.items():
            members = set(cats)
            with RegionManager():
                # Zoom to this class only; -a keeps the current resolution and
                # grid alignment. Other classes poking into the box are ignored.
                tools.g_region(
                    n=class_box[cls][0], s=class_box[cls][1],
                    e=class_box[cls][2], w=class_box[cls][3],
                    nsres=nsres, ewres=ewres, flags="a",
                )
                tools.v_to_rast(
                    input=vector, output=zones, use="cat", memory=memory,
                    overwrite=True,
                )
                stats = zonal_stats(tools, rasters, zones, nprocs, keep=members)
            for cat in cats:
                for index in range(len(rasters)):
                    triple = stats.get(cat, [None] * len(rasters))[index]
                    if triple is not None:
                        buckets[cls][index].append(triple)
    else:
        gs.verbose(_("Aggregating all area classes in a single pass."))
        with RegionManager():
            # Restrict to the whole-layer box; -a keeps resolution and grid
            # alignment and grows the box to include the whole vector.
            tools.g_region(vector=vector, flags="a")
            tools.v_to_rast(
                input=vector, output=zones, use="cat", memory=memory, overwrite=True
            )
            stats = zonal_stats(tools, rasters, zones, nprocs)
        for cat, triples in stats.items():
            cls = classes.get(cat, cat) if classes else cat
            for index in range(len(rasters)):
                if triples[index] is not None:
                    buckets[cls][index].append(triples[index])

    series = []
    for cls in sorted(buckets):
        means, lowers, uppers = [], [], []
        for stats_list in buckets[cls]:
            mean, sd = pool(stats_list)
            means.append(mean)
            lowers.append(None if mean is None else mean - sd)
            uppers.append(None if mean is None else mean + sd)
        series.append(
            Series(name=str(cls), values=means, lower=lowers, upper=uppers, color=None)
        )
    return series


def axis_angles(n):
    """Return the n evenly spaced axis angles, plus the closing angle.

    :param int n: number of axes

    :return list: n+1 angles in radians (last equals the first)
    """
    from math import pi

    angles = [2 * pi * i / n for i in range(n)]
    return angles + angles[:1]


def setup_polar_ax(ax, angles, labels, grid_labels):
    """Configure a polar axes: spoke labels, ranged grid rings.

    :param ax: the polar Axes to configure
    :param list angles: axis angles (n+1, closed)
    :param list labels: axis labels
    :param bool grid_labels: label each grid ring with its axis fraction
    """
    ax.set_theta_offset(3.14159265 / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    # The grid rings are drawn at fixed fractions of every axis range. The
    # grid is always shown; the ring labels are optional.
    rings = [0.2, 0.4, 0.6, 0.8, 1.0]
    ax.set_yticks(rings)
    if grid_labels:
        ax.set_yticklabels(
            [format_value(r) for r in rings], fontsize="small", color="gray"
        )
    else:
        ax.set_yticklabels([])
    ax.grid(True)


def draw_series(ax, angles, series, ranges, show_values, line_width, fill, band, color):
    """Draw one Series (line, optional fill, optional stddev band) on an axes.

    :param ax: the polar Axes to draw on
    :param list angles: axis angles (n+1, closed)
    :param Series series: the series to draw
    :param list ranges: (low, high) per axis
    :param bool show_values: annotate the raw value at each vertex
    :param float line_width: line width
    :param float fill: fill opacity (0 disables the fill)
    :param float band: opacity of the standard-deviation band
    :param color: line color, or None for the palette
    """
    norm = [normalize(v, ranges[i]) for i, v in enumerate(series.values)]
    norm_closed = norm + norm[:1]
    line = ax.plot(
        angles, norm_closed, linewidth=line_width, label=series.name, color=color
    )[0]
    drawn = line.get_color()
    if fill > 0:
        ax.fill(angles, norm_closed, color=drawn, alpha=fill)
    if series.lower is not None and series.upper is not None:
        low = [normalize(v, ranges[i]) for i, v in enumerate(series.lower)]
        high = [normalize(v, ranges[i]) for i, v in enumerate(series.upper)]
        ax.fill_between(
            angles, low + low[:1], high + high[:1], color=drawn, alpha=band
        )
    if show_values:
        for angle, radius, value in zip(angles, norm_closed, series.values):
            if value is not None:
                ax.annotate(
                    format_value(value), (angle, radius), fontsize="small", ha="center"
                )


def palette_colors(n):
    """Return n colors from the active Matplotlib property cycle."""
    cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0"])
    return [cycle[i % len(cycle)] for i in range(n)]


def finish_figure(output, dpi):
    """Save the current figure to a file, or show it interactively."""
    if output:
        plt.savefig(output, bbox_inches="tight", dpi=dpi)
        plt.close()
        path = os.path.split(output)
        gs.message(
            _("File {name} written to {path}").format(name=path[1], path=path[0] or ".")
        )
    else:
        gs.message(_("\n> Close the figure window to finish the script.\n"))
        plt.tight_layout()
        plt.show()
        plt.close()


def plot_spider(
    series_list,
    ranges,
    labels,
    facet,
    output,
    dimensions,
    dpi,
    title,
    title_fontsize,
    grid_labels,
    show_values,
    line_width,
    fill_alpha,
    band_alpha,
    color,
):
    """Draw the spider plot as a single radar or as one facet per class.

    Facets are used for several classes; otherwise every series is overlaid on
    one radar (a single class collapses to one radar either way).

    :param list series_list: Series to draw (raw values; optional band)
    :param list ranges: (low, high) per axis
    :param list labels: axis labels
    :param bool facet: draw one subplot per series when more than one
    :param str output: image path, or empty to show an interactive window
    :param list dimensions: (width, height) in inches, or None to auto-size
    :param float dpi: output resolution
    :param str title: optional plot title
    :param int title_fontsize: title font size
    :param bool grid_labels: label each grid ring with its axis fraction
    :param bool show_values: annotate the raw value at each vertex
    :param float line_width: line width
    :param float fill_alpha: fill opacity (0 disables the fill)
    :param float band_alpha: opacity of the standard-deviation band
    :param color: line color, or None for the palette
    """
    from math import ceil

    angles = axis_angles(len(labels))
    colors = palette_colors(len(series_list))

    if facet and len(series_list) > 1:
        ncols = ceil(len(series_list) ** 0.5)
        nrows = ceil(len(series_list) / ncols)
        figsize = dimensions or [4 * ncols, 4 * nrows]
        fig, axes = plt.subplots(
            nrows, ncols, subplot_kw={"polar": True}, figsize=figsize
        )
        axes = list(fig.axes)
        for index, series in enumerate(series_list):
            ax = axes[index]
            setup_polar_ax(ax, angles, labels, grid_labels)
            pen = color or series.color or colors[index]
            draw_series(
                ax, angles, series, ranges, show_values, line_width,
                fill_alpha, band_alpha, pen,
            )
            ax.set_title(series.name, fontsize=title_fontsize)
        for ax in axes[len(series_list):]:
            ax.set_visible(False)
        if title:
            fig.suptitle(title, fontsize=title_fontsize)
    else:
        fig, ax = plt.subplots(
            subplot_kw={"polar": True}, figsize=dimensions or [7, 7]
        )
        setup_polar_ax(ax, angles, labels, grid_labels)
        for index, series in enumerate(series_list):
            pen = series.color or color or colors[index]
            draw_series(
                ax, angles, series, ranges, show_values, line_width,
                fill_alpha, band_alpha, pen,
            )
        if len(series_list) > 1:
            ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize="small")
        if title:
            ax.set_title(title, fontsize=title_fontsize)

    finish_figure(output, dpi)


def main(options, flags):
    """Draw a spider plot of raster values sampled at a point."""

    output = options["output"]
    lazy_import_py_modules(bool(output))

    tools = Tools()

    rasters = options["input"].split(",")
    if len(rasters) < 2:
        gs.fatal(_("At least two input rasters are required."))
    if len(rasters) < 3:
        gs.warning(_("A spider plot is more meaningful with three or more axes."))
    for raster in rasters:
        check_map_exists(raster)

    nprocs = int(options["nprocs"])
    memory = int(options["memory"])

    # Axis labels default to the (mapset-stripped) raster names.
    if options["labels"]:
        labels = options["labels"].split(",")
        if len(labels) != len(rasters):
            gs.fatal(
                _("Got {a} labels for {b} rasters.").format(
                    a=len(labels), b=len(rasters)
                )
            )
    else:
        labels = [strip_mapset(r) for r in rasters]

    # Axis ranges: user bounds win, missing ones come from the raster.
    minima = parse_bound_list(options["minimum"], len(rasters), "minimum")
    maxima = parse_bound_list(options["maximum"], len(rasters), "maximum")
    ranges = resolve_ranges(tools, rasters, minima, maxima, nprocs)

    if flags["r"]:
        labels = [
            "{lab}\n[{lo}, {hi}]".format(
                lab=lab, lo=format_value(low), hi=format_value(high)
            )
            for lab, (low, high) in zip(labels, ranges)
        ]

    # Data source: a single coordinate, or the features of a vector map. For a
    # vector, points are drawn as separate lines unless a grouping column
    # aggregates them into classes; areas are always aggregated into classes
    # (by category, or by the grouping column). Several classes are faceted.
    vector = options["map"]
    if vector:
        vector = subset_vector(tools, vector, options["cats"], options["where"])
        group_column = options["group_column"]
        geometry = vector_geometry(tools, vector)
        if geometry == "area":
            gs.message(_("Aggregating raster values per area class..."))
            series_list = sample_area_classes(
                tools, rasters, vector, group_column, nprocs, memory
            )
            facet = True
        elif group_column:
            gs.message(_("Aggregating raster values per point class..."))
            series_list = sample_point_classes(tools, rasters, vector, group_column)
            facet = True
        else:
            gs.message(_("Sampling rasters at each point..."))
            series_list = sample_point_lines(tools, rasters, vector)
            facet = False
        if not series_list:
            gs.fatal(_("No features to plot after applying the selection."))
    else:
        east, north = coords_from_option(options["coordinates"])
        gs.message(_("Sampling at (east, north) = ({}, {})").format(east, north))
        series_list = sample_point(tools, rasters, east, north)
        facet = False

    # Appearance.
    color = get_valid_color(options["color"]) if options["color"] else None
    line_width = float(options["line_width"])
    fill_alpha = float(options["fill_alpha"])
    band_alpha = float(options["band_alpha"])

    dpi = float(options["dpi"]) if options["dpi"] else 300
    if options["plot_dimensions"]:
        dimensions = [float(x) for x in options["plot_dimensions"].split(",")]
    else:
        dimensions = None

    if options["style"]:
        if options["style"] not in plt.style.available:
            gs.fatal(
                _("Unknown style '{}'. Available styles: {}").format(
                    options["style"], ", ".join(plt.style.available)
                )
            )
        plt.style.use(options["style"])
    plt.rcParams["font.size"] = int(options["fontsize"])
    if options["font"]:
        plt.rcParams["font.family"] = options["font"]
    title_fontsize = (
        int(options["title_fontsize"])
        if options["title_fontsize"]
        else int(options["fontsize"])
    )

    plot_spider(
        series_list=series_list,
        ranges=ranges,
        labels=labels,
        facet=facet,
        output=output,
        dimensions=dimensions,
        dpi=dpi,
        title=options["title"],
        title_fontsize=title_fontsize,
        grid_labels=flags["l"],
        show_values=flags["n"],
        line_width=line_width,
        fill_alpha=fill_alpha,
        band_alpha=band_alpha,
        color=color,
    )


if __name__ == "__main__":
    atexit.register(cleanup)
    sys.exit(main(*gs.parser()))

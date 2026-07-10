#!/usr/bin/env python

############################################################################
#
# MODULE:       t.rast.scatter
# AUTHOR:       Paulo van Breugel
# PURPOSE:      Draws a scatterplot of the values of two space-time raster
#               datasets (strds), sampled at a user-provided set of points.
#               Optional OLS, LOWESS and monotone-GAM fits are overlaid.
#
# COPYRIGHT:    (c) 2026 Paulo van Breugel and the GRASS Development Team
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################

# %module
# % description: Scatterplot of two space-time raster datasets sampled at user-defined points.
# % keyword: temporal
# % keyword: raster
# % keyword: time series
# % keyword: scatterplot
# % keyword: regression
# % keyword: plot
# % keyword: display
# %end

# %option G_OPT_STRDS_INPUT
# % key: xstrds
# % label: STRDS for the x axis
# % guisection: Input
# %end

# %option G_OPT_STRDS_INPUT
# % key: ystrds
# % label: STRDS for the y axis
# % description: Second strds, plotted on the y axis against 'xstrds'. Both datasets must use absolute time. How their timesteps are paired is controlled by the 'method' option.
# % guisection: Input
# %end

# %option G_OPT_V_INPUT
# % key: points
# % label: Point vector map with sample locations
# % description: Vector map of points at which both datasets are sampled at every timestep.
# % guisection: Input
# %end

# %option G_OPT_T_WHERE
# % key: where
# % guisection: Selection
# %end

# %option
# % key: method
# % type: string
# % label: Temporal pairing method
# % description: How to pair the timesteps of the two datasets. 'nearest' matches each map to the closest-in-time map of the other dataset within 'tolerance', preserving individual observations. The aggregate methods (mean, median, sum, min, max) first bin both datasets to 'frequency' and pair the per-period summaries.
# % options: nearest,mean,median,sum,min,max
# % answer: nearest
# % required: no
# % guisection: Pairing
# %end

# %option
# % key: tolerance
# % type: string
# % label: Time-matching tolerance (method=nearest)
# % description: Maximum allowed time difference for a nearest match, as a duration (e.g. '1 day', '6 hours', '30 minutes'). Maps with no counterpart within this window are dropped. Used only when method=nearest.
# % required: no
# % guisection: Pairing
# %end

# %option
# % key: frequency
# % type: string
# % label: Aggregation frequency (aggregate methods)
# % description: Target frequency to bin both datasets to before pairing, as a pandas offset alias (e.g. 'D' daily, 'W' weekly, 'MS' month-start, 'YS' year-start). Used only with the aggregate methods (mean, median, sum, min, max).
# % required: no
# % guisection: Pairing
# %end

# %option
# % key: lag
# % type: string
# % label: Lag of the x (driver) dataset
# % description: Shift the x (driver) dataset in time before pairing, to test a delayed response (e.g. vegetation reacting to earlier rainfall). A duration like '1 months', '30 days' or '2 weeks'. A positive lag means the driver precedes the response: an x map at time t is paired with the y map at t + lag. Negative values are allowed. Combine with 'lag_window' for an accumulated/averaged driver instead of a single shifted value.
# % required: no
# % guisection: Lag
# %end

# %option
# % key: lag_window
# % type: string
# % label: Accumulation window for the driver
# % description: If set, the driver value paired with a response at time t is not a single shifted map but the reduction (see 'lag_stat') of all x maps falling in the preceding window [t - lag - lag_window, t - lag]. Use for variables the vegetation integrates over time, e.g. rainfall accumulated over the previous 60 days. A duration like '60 days' or '2 months'.
# % required: no
# % guisection: Lag
# %end

# %option
# % key: lag_stat
# % type: string
# % label: Window reduction
# % description: How to reduce the x maps inside 'lag_window' to a single driver value. 'sum' suits fluxes such as rainfall; 'mean' suits states such as temperature or soil moisture. Used only when 'lag_window' is set.
# % options: sum,mean,median,min,max
# % answer: sum
# % required: no
# % guisection: Lag
# %end

# %flag
# % key: o
# % label: OLS regression line
# % description: Add the ordinary least-squares regression line (slope, intercept and R^2) to the scatterplot.
# % guisection: Regression
# %end

# %flag
# % key: l
# % label: LOWESS smoother
# % description: Add a LOWESS (locally weighted) smoother to the scatterplot. Requires the 'statsmodels' package.
# % guisection: Regression
# %end

# %flag
# % key: g
# % label: GAM curve
# % description: Add a Generalized Additive Model (smooth spline) curve to the scatterplot. Requires the 'pygam' package.
# % guisection: Regression
# %end

# %option
# % key: lowess_frac
# % type: double
# % label: LOWESS span
# % description: Fraction of the data used when estimating each LOWESS value (statsmodels lowess 'frac'), between 0 and 1. Larger is smoother.
# % answer: 0.3
# % required: no
# % guisection: Regression
# %end

# %flag
# % key: t
# % label: Regression statistics in plot
# % description: Show the fit statistics (OLS slope, R^2, etc.) in the plot legend. They are always printed to the terminal regardless of this flag.
# % guisection: Regression
# %end

# %flag
# % key: c
# % label: Color points by time (absolute)
# % description: Color the scatter points by their absolute timestep, with a colorbar, to reveal temporal structure. Note that the same season in different years gets a different color; for a seasonal loop use -y (cyclic) instead. Mutually exclusive with -y and -D.
# % guisection: Optional
# %end

# %flag
# % key: y
# % label: Color points by season (cyclic)
# % description: Color the scatter points by their position within the year (day-of-year) using a cyclic colormap, so the same season in different years shares a color and a recurring seasonal loop becomes visible. Mutually exclusive with -c and -D.
# % guisection: Optional
# %end

# %flag
# % key: D
# % label: Density plot
# % description: Render the points as a 2D density (hexagonal/grid binning colored by count) instead of individual dots, useful when overplotting hides structure. Mutually exclusive with -c and -y (a density bin aggregates points of different times, so per-point time coloring does not apply).
# % guisection: Optional
# %end

# %option
# % key: bins
# % type: string
# % label: Density bins (x,y)
# % description: Number of bins along the x and y axes for the density plot (-D), as 'nx,ny'.
# % answer: 30,30
# % required: no
# % guisection: Optional
# %end

# %option
# % key: density_colormap
# % type: string
# % label: Density colormap
# % description: Matplotlib colormap for the density plot (-D).
# % answer: viridis
# % required: no
# % guisection: Optional
# %end

# %flag
# % key: d
# % label: Add grid lines
# % description: Add grid lines.
# % guisection: Aesthetics
# %end

# %option G_OPT_F_OUTPUT
# % key: output
# % required: no
# % label: Name of output plot file
# % description: Output image file. The format is taken from the extension (e.g. .png, .pdf, .svg). If omitted, the plot is shown in an interactive window.
# % guisection: Output
# %end

# %option G_OPT_F_OUTPUT
# % key: csv
# % required: no
# % label: Name of output CSV file
# % description: Optional CSV file with the paired (x, y) samples, one row per point and timestep, with coordinates and date.
# % guisection: Output
# %end

# %option
# % key: backend
# % type: string
# % label: Matplotlib backend
# % description: Matplotlib rendering backend. WXAgg (default) opens an interactive window. Agg is non-interactive and used automatically when saving to a file.
# % options: WXAgg,TkAgg,Qt5Agg,GTK3Agg,Agg
# % required: no
# % guisection: Output
# %end

# %option
# % key: dpi
# % type: integer
# % label: DPI
# % description: Plot resolution in DPI.
# % answer: 300
# % required: no
# % guisection: Output
# %end

# %option
# % key: plot_dimensions
# % type: string
# % label: Plot dimensions (width,height)
# % description: Dimensions (width,height) of the figure in inches.
# % required: no
# % guisection: Output
# %end

# %option
# % key: title
# % type: string
# % label: Plot title
# % description: The title of the plot. If left empty, no title is drawn.
# % required: no
# % guisection: Aesthetics
# %end

# %option
# % key: x_label
# % type: string
# % label: x-axis label
# % description: Label for the x-axis. If left empty, the name of the x dataset (xstrds) is used.
# % required: no
# % guisection: Aesthetics
# %end

# %option
# % key: y_label
# % type: string
# % label: y-axis label
# % description: Label for the y-axis. If left empty, the name of the y dataset (ystrds) is used.
# % required: no
# % guisection: Aesthetics
# %end

# %option G_OPT_CN
# % key: color
# % type: string
# % label: Point color
# % description: Color of the scatter points. Accepts a GRASS color name, an R:G:B triplet, or any matplotlib color (hex code or 'tab:' name). Ignored when -c (color by time) is set.
# % required: no
# % answer: 51:125:255
# % guisection: Aesthetics
# %end

# %option
# % key: s
# % type: double
# % label: Point size
# % description: Size of the scatter points (matplotlib marker area).
# % answer: 12
# % required: no
# % guisection: Aesthetics
# %end

# %option
# % key: marker
# % type: string
# % label: Point marker
# % description: Marker used for the scatter points (see https://matplotlib.org/stable/api/markers_api.html for options).
# % answer: o
# % required: no
# % guisection: Aesthetics
# %end

# %option
# % key: point_alpha
# % type: double
# % label: Point transparency
# % description: Opacity of the scatter points, between 0 (fully transparent) and 1 (opaque).
# % answer: 0.6
# % options: 0-1
# % required: no
# % guisection: Aesthetics
# %end

# %option
# % key: fontsize
# % type: double
# % label: Font size
# % description: Base font size of plot text.
# % answer: 10
# % required: no
# % guisection: Aesthetics
# %end

# %option
# % key: line_width
# % type: double
# % label: Line width
# % description: Width of the regression/smoother fit lines (OLS, LOWESS, GAM).
# % answer: 1.5
# % required: no
# % guisection: Aesthetics
# %end

# %option G_OPT_M_NPROCS
# %end

# %rules
# % requires: lowess_frac, -l
# %end


import sys

import grass.script as gs
from grass.exceptions import CalledModuleError

if not callable(globals().get("_")):
    from gettext import gettext as _


MIN_PANDAS_VERSION = (2, 0)


def check_dependencies(backend, need_lowess, need_gam):
    """Import and validate every third-party dependency, up front.

    Optional dependencies are only required when the
    corresponding flag is set: statsmodels for the LOWESS smoother
    (-l) and pygam for the GAM curve (-g).

    :param str backend: matplotlib backend to activate before importing pyplot
    :param bool need_lowess: whether the LOWESS smoother was requested (-l)
    :param bool need_gam: whether the GAM curve was requested (-g)
    """
    global np
    global pd
    global linregress
    global mpl
    global plt
    global lowess
    global LinearGAM
    global gam_s

    # Always-required scientific stack.
    try:
        import numpy as np
        import pandas as pd
    except ModuleNotFoundError as e:
        gs.fatal(
            _(
                "The Python package '{pkg}' is required but not installed. "
                "Install it with e.g. 'pip install numpy pandas'."
            ).format(pkg=e.name)
        )

    # Minimum pandas version. The timestamp parsing relies on the 'ISO8601'
    # format token introduced in pandas 2.0.
    try:
        pandas_version = tuple(int(p) for p in pd.__version__.split(".")[:2])
    except (ValueError, AttributeError):
        pandas_version = None
    if pandas_version is None or pandas_version < MIN_PANDAS_VERSION:
        gs.fatal(
            _(
                "pandas >= {req} is required (found {found}). Please upgrade, "
                "e.g. 'pip install -U pandas'."
            ).format(
                req=".".join(str(v) for v in MIN_PANDAS_VERSION),
                found=getattr(pd, "__version__", "unknown"),
            )
        )

    try:
        from scipy.stats import linregress as _linregress
    except ModuleNotFoundError:
        gs.fatal(
            _(
                "The Python package 'scipy' is required for the OLS "
                "regression but is not installed. Install it with e.g. "
                "'pip install scipy'."
            )
        )
    linregress = _linregress

    try:
        import matplotlib as _mpl

        _mpl.use(backend)
        from matplotlib import pyplot as _plt
    except ModuleNotFoundError:
        gs.fatal(_("Matplotlib is required but not installed. Please install it."))
    mpl = _mpl
    plt = _plt

    # Optional dependencies, required only when their flag is set.
    lowess = None
    if need_lowess:
        try:
            from statsmodels.nonparametric.smoothers_lowess import lowess as _lowess
        except ImportError as e:
            gs.fatal(
                _(
                    "The Python package 'statsmodels' is required for the "
                    "LOWESS smoother (flag -l) but could not be imported "
                    "({err}). Install it with e.g. 'pip install statsmodels', "
                    "or drop the -l flag."
                ).format(err=e)
            )
        lowess = _lowess

    LinearGAM = None
    gam_s = None
    if need_gam:
        try:
            from pygam import LinearGAM as _LinearGAM, s as _gam_s
        except ImportError as e:
            gs.fatal(
                _(
                    "The Python package 'pygam' is required for the GAM curve "
                    "(flag -g) but could not be imported ({err}). Install it "
                    "with e.g. 'pip install pygam', or drop the -g flag."
                ).format(err=e)
            )
        LinearGAM = _LinearGAM
        gam_s = _gam_s


def grass_color_to_mpl(value):
    """Convert a GRASS color spec to a matplotlib-usable color.

    Accepts an ``R:G:B`` triplet (0-255 components) or anything matplotlib
    already understands (name, hex, 'tab:' name).
    """
    if not value:
        return None
    value = value.strip()
    if value.lower() == "none":
        return None
    if ":" in value:
        parts = value.split(":")
        if all(p.strip().lstrip("-").isdigit() for p in parts):
            if len(parts) not in (3, 4):
                raise ValueError("expected R:G:B or R:G:B:A")
            comps = []
            for p in parts:
                c = int(p)
                if not 0 <= c <= 255:
                    raise ValueError("each component must be in 0-255")
                comps.append(c / 255.0)
            return tuple(comps)
    return value


def parse_tolerance(value):
    """Parse a tolerance duration string into a pandas Timedelta.

    Accepts anything pandas.Timedelta understands, e.g. '1 day', '6 hours',
    '30 minutes', '1.5 days', '90min'.

    :param str value: the tolerance= option value
    :return pandas.Timedelta: the parsed tolerance (always positive)
    """
    try:
        td = pd.Timedelta(value)
    except (ValueError, TypeError):
        gs.fatal(
            _(
                "Could not parse tolerance '{}' as a duration. Use forms like "
                "'1 day', '6 hours' or '30 minutes'."
            ).format(value)
        )
    if td <= pd.Timedelta(0):
        gs.fatal(_("Tolerance must be a positive duration."))
    return td


def pair_nearest(xdf, ydf, tolerance):
    """Pair two long sample frames by nearest timestamp, per point.

    Each frame has columns [cat, east, north, date, value]. For every sample
    point (identified by cat), maps from the two datasets are matched on the
    closest 'date' within 'tolerance', one-to-one: pandas.merge_asof with
    direction='nearest' assigns each x-row its nearest y-row within tolerance.
    Rows with no counterpart inside the window are dropped.

    :param pandas.DataFrame xdf: x-dataset samples (column 'value' -> x)
    :param pandas.DataFrame ydf: y-dataset samples (column 'value' -> y)
    :param pandas.Timedelta tolerance: maximum allowed time difference
    :return pandas.DataFrame: columns [cat, east, north, date, x, y]
    """
    pieces = []
    # merge_asof requires each side sorted by the join key ('date').
    for cat, xg in xdf.groupby("cat", sort=False):
        yg = ydf[ydf["cat"] == cat]
        if yg.empty:
            continue
        xg = xg.sort_values("date")
        yg = yg.sort_values("date")
        merged = pd.merge_asof(
            xg.rename(columns={"value": "x", "date": "date"}),
            yg[["date", "value"]].rename(columns={"value": "y"}),
            on="date",
            direction="nearest",
            tolerance=tolerance,
        )
        # Unmatched x-rows get NaN y; drop them.
        merged = merged.dropna(subset=["y"])
        if not merged.empty:
            pieces.append(merged[["cat", "east", "north", "date", "x", "y"]])

    if not pieces:
        gs.fatal(
            _(
                "No point/timestep pairs fell within the tolerance window. "
                "Increase 'tolerance', or check that the two datasets overlap "
                "in time."
            )
        )
    return pd.concat(pieces, ignore_index=True)


def pair_aggregate(xdf, ydf, frequency, method):
    """Pair two long sample frames by aggregating each to a common frequency.

    Each frame has columns [cat, east, north, date, value]. Both datasets are
    binned to 'frequency' (a pandas offset alias) per point and reduced with
    'method' (mean/median/sum/min/max). A scatter point is then the pair of
    per-period summaries for one point and one period present in both.

    :param pandas.DataFrame xdf: x-dataset samples
    :param pandas.DataFrame ydf: y-dataset samples
    :param str frequency: pandas offset alias (e.g. 'D', 'W', 'MS', 'YS')
    :param str method: 'mean', 'median', 'sum', 'min' or 'max'
    :return pandas.DataFrame: columns [cat, east, north, period, x, y]
    """

    def binned(df, valname):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        # Bin each point's series to the target frequency.
        g = (
            df.set_index("date")
            .groupby([pd.Grouper(freq=frequency), "cat"])["value"]
            .agg(method)
            .rename(valname)
            .reset_index()
            .rename(columns={"date": "period"})
        )
        return g

    bx = binned(xdf, "x")
    by = binned(ydf, "y")

    # Carry coordinates along (one per cat) for optional CSV / vector output.
    coords = xdf[["cat", "east", "north"]].drop_duplicates("cat")

    merged = bx.merge(by, on=["period", "cat"], how="inner")
    if merged.empty:
        gs.fatal(
            _(
                "After aggregating to frequency '{}', the two datasets share "
                "no common point/period bins. Try a coarser frequency."
            ).format(frequency)
        )
    merged = merged.merge(coords, on="cat", how="left")
    return merged[["cat", "east", "north", "period", "x", "y"]]


def parse_lag(value, allow_negative=True):
    """Parse a lag duration string into a signed pandas Timedelta.

    :param str value: the lag= option value (e.g. '1 months', '30 days')
    :param bool allow_negative: whether a negative lag is permitted
    :return pandas.Timedelta: the parsed offset
    """
    try:
        td = pd.Timedelta(value)
    except (ValueError, TypeError):
        gs.fatal(
            _(
                "Could not parse lag '{}' as a duration. Use forms like "
                "'1 months', '30 days', '2 weeks' or '6 hours'."
            ).format(value)
        )
    if td < pd.Timedelta(0) and not allow_negative:
        gs.fatal(_("Lag must be a non-negative duration."))
    return td


def apply_lag(xdf, lag, lag_window=None, lag_stat="sum"):
    """Lag the x (driver) dataset in time before pairing.

    Two modes:

    * Instantaneous shift (lag_window is None): every x sample is relabelled
      from its own time t to t + lag, so it subsequently pairs with the y
      (response) sample at t + lag. A positive lag means the driver precedes
      the response.

    * Accumulation window (lag_window set): for each y (response) time the
      driver value is the reduction (lag_stat) of all x samples whose ORIGINAL
      time falls in the preceding window [t - lag - lag_window, t - lag]. This
      is computed per point (cat) here as a relabelling: each x sample is
      assigned to the response times whose window contains it. Because the
      response grid is not known at this stage, the accumulation is instead
      realised by shifting and then letting the downstream nearest/aggregate
      pairing match; see note below.

    For the accumulation mode we cannot know the response timestamps here
    (pairing happens later), so this function only performs the instantaneous
    shift. The accumulation mode is handled in apply_lag_accumulate(), which
    needs both frames. apply_lag() therefore implements ONLY the shift; callers
    select between the two.

    :param pandas.DataFrame xdf: x-dataset samples [cat,east,north,date,value]
    :param pandas.Timedelta lag: time offset to add to each x date
    :return pandas.DataFrame: xdf with shifted 'date'
    """
    out = xdf.copy()
    out["date"] = pd.to_datetime(out["date"]) + lag
    return out


def apply_lag_accumulate(xdf, ydf, lag, lag_window, lag_stat="sum"):
    """Build a lagged, accumulated driver frame aligned to response times.

    For every response (y) sample at time t and point cat, reduce all x samples
    of the same point whose original time falls in the window
    [t - lag - lag_window, t - lag] using 'lag_stat'. The result is a driver
    frame with one row per response time/point, carrying the accumulated value
    under 'value' and the response time under 'date', so it can be paired with
    the response one-to-one downstream (method=nearest, tolerance=0-ish) or
    merged directly.

    :param pandas.DataFrame xdf: driver samples [cat,east,north,date,value]
    :param pandas.DataFrame ydf: response samples [cat,east,north,date,value]
    :param pandas.Timedelta lag: leading-edge offset of the window
    :param pandas.Timedelta lag_window: window length
    :param str lag_stat: 'sum','mean','median','min','max'
    :return pandas.DataFrame: accumulated driver [cat,east,north,date,value]
    """
    xx = xdf.copy()
    xx["date"] = pd.to_datetime(xx["date"])
    yy = ydf.copy()
    yy["date"] = pd.to_datetime(yy["date"])

    reducer = {
        "sum": np.sum,
        "mean": np.mean,
        "median": np.median,
        "min": np.min,
        "max": np.max,
    }.get(lag_stat)
    if reducer is None:
        gs.fatal(_("Unknown lag_stat '{}'.").format(lag_stat))

    pieces = []
    empty_windows = 0
    total_windows = 0
    for cat, yg in yy.groupby("cat", sort=False):
        xg = xx[xx["cat"] == cat]
        if xg.empty:
            continue
        xt = xg["date"].to_numpy()
        xv = xg["value"].to_numpy(dtype="float64")
        for _, yrow in yg.iterrows():
            t = yrow["date"]
            hi = t - lag
            lo = hi - lag_window
            mask = (xt > np.datetime64(lo)) & (xt <= np.datetime64(hi))
            total_windows += 1
            if not mask.any():
                empty_windows += 1
                continue
            val = float(reducer(xv[mask]))
            pieces.append(
                {
                    "cat": cat,
                    "east": yrow["east"],
                    "north": yrow["north"],
                    "date": t,
                    "value": val,
                }
            )

    if empty_windows and total_windows:
        gs.warning(
            _(
                "{e} of {n} accumulation windows contained no driver maps; "
                "those response times were dropped. Consider a longer "
                "'lag_window' or a denser driver dataset."
            ).format(e=empty_windows, n=total_windows)
        )
    if not pieces:
        gs.fatal(
            _(
                "The accumulation window captured no driver maps for any "
                "response time. Check 'lag', 'lag_window', and that the two "
                "datasets overlap in time."
            )
        )
    return pd.DataFrame(pieces)


def sample_long(strds, points_map, where=None, nprocs=1):
    """Sample one strds at the points of a vector map across all timesteps.

    Returns a long DataFrame with one row per (point, timestep) where the
    value is non-null. Pairing of the two datasets happens afterwards in
    pair_nearest() / pair_aggregate(), so this function does NOT filter by the
    other dataset.

    :param str strds: the space-time raster dataset to sample
    :param str points_map: name of the input point vector map
    :param str where: optional t.rast.what 'where' clause to restrict timesteps
    :param int nprocs: number of parallel r.what processes for t.rast.what
    :return pandas.DataFrame: columns [cat, east, north, date, value]
    """
    kwargs = {
        "strds": strds,
        "points": points_map,
        "layout": "row",
        "null_value": "nan",
        "separator": "pipe",
        "nprocs": nprocs,
        "flags": "v",  # include the vector point category as a stable id
        "quiet": True,
    }
    if where:
        kwargs["where"] = where

    try:
        out = gs.read_command("t.rast.what", **kwargs)
    except CalledModuleError:
        gs.fatal(_("Sampling '{}' with t.rast.what failed.").format(strds))

    # layout=row with -v columns (no header requested):
    #     cat|x|y|start_time|end_time|value
    good_lines = []
    for line in out.splitlines():
        line = line.strip()
        if line and line.count("|") >= 5:
            good_lines.append(line)

    if not good_lines:
        gs.fatal(
            _(
                "Sampling '{}' returned no records. Check the points map and "
                "any 'where' clause."
            ).format(strds)
        )

    from io import StringIO

    raw = pd.read_csv(
        StringIO("\n".join(good_lines)),
        sep="|",
        header=None,
        dtype=str,
        na_filter=False,  # keep "nan"/"", dealt with below
        engine="c",
    )

    df = pd.DataFrame(
        {
            "cat": raw.iloc[:, 0],
            "east": raw.iloc[:, 1],
            "north": raw.iloc[:, 2],
            "date": raw.iloc[:, 3],
            "value": raw.iloc[:, -1],
        }
    )
    df["cat"] = pd.to_numeric(df["cat"], errors="coerce").astype("Int64")
    df["east"] = pd.to_numeric(df["east"], errors="coerce")
    df["north"] = pd.to_numeric(df["north"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    # Parse the timestamps. GRASS absolute time is written as
    # 'YYYY-MM-DD HH:MM:SS', optionally with fractional seconds, which the
    # 'ISO8601' format accepts (pandas >= 2.0 is enforced in
    # check_dependencies). Parse with an explicit format and treat a
    # parse failure as an ERROR to report
    raw_date = df["date"].astype(str).str.strip()
    parsed = pd.to_datetime(raw_date, format="ISO8601", errors="coerce")
    bad = parsed.isna() & (raw_date != "") & (raw_date.str.lower() != "nan")
    if bad.any():
        example = raw_date[bad].iloc[0]
        gs.fatal(
            _(
                "Could not parse {n} timestamp(s) from t.rast.what output for "
                "'{strds}'; the date format was not understood (e.g. '{ex}'). "
                "This is unexpected for absolute-time data and would otherwise "
                "drop those records silently."
            ).format(n=int(bad.sum()), strds=strds, ex=example)
        )
    df["date"] = parsed

    # Drop genuine NULL samples (null_value='nan' -> NaN value), rows with no
    # usable point category, and rows with an empty/missing timestamp.
    df = df.dropna(subset=["value", "date", "cat"])
    # After dropping NaN cats, downcast to a plain int.
    df["cat"] = df["cat"].astype("int64")

    return df[["cat", "east", "north", "date", "value"]].reset_index(drop=True)


def fit_ols(x, y):
    """Ordinary least-squares fit of y on x. Returns a dict or None."""
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 2:
        return None
    reg = linregress(x[mask], y[mask])
    return {
        "slope": float(reg.slope),
        "intercept": float(reg.intercept),
        "r2": float(reg.rvalue) ** 2,
        "pvalue": float(reg.pvalue),
        "n": int(mask.sum()),
    }


def fit_lowess(x, y, frac):
    """LOWESS smoother. Returns sorted (xs, ys) arrays or None.

    Relies on 'lowess' having been imported by check_dependencies (-l flag).
    """
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 2:
        return None
    out = lowess(y[mask], x[mask], frac=float(frac), return_sorted=True)
    return out[:, 0], out[:, 1]


def fit_gam_curve(x, y):
    """Smooth (unconstrained) GAM curve. Returns sorted (xs, ys) or None.

    Relies on 'LinearGAM'/'gam_s' having been imported by check_dependencies
    (-g flag).
    """
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 2:
        return None
    xm = x[mask]
    ym = y[mask]
    try:
        gam = LinearGAM(gam_s(0)).fit(xm.reshape(-1, 1), ym)
    except Exception as e:
        gs.warning(_("GAM fit failed ({}); skipping the GAM curve.").format(e))
        return None
    xs = np.linspace(np.nanmin(xm), np.nanmax(xm), 200)
    ys = np.asarray(gam.predict(xs.reshape(-1, 1)), dtype="float64")
    return xs, ys


def plot_scatter(
    df,
    xstrds,
    ystrds,
    date_col,
    output,
    dpi,
    dimensions,
    point_color,
    color_by_time,
    fits,
    show_stats,
    color_by_season=False,
    density=False,
    bins=(30, 30),
    density_colormap="viridis",
    fontsize=10,
    line_width=1.5,
    title=None,
    x_label=None,
    y_label=None,
    grid=False,
    point_size=12,
    marker="o",
    point_alpha=0.6,
):
    """Draw the scatterplot with the requested regression overlays."""
    plt.rcParams["font.size"] = fontsize
    fig, ax = plt.subplots(figsize=dimensions)

    x = df["x"].to_numpy(dtype="float64")
    y = df["y"].to_numpy(dtype="float64")

    if density:
        # 2D histogram density: count of points per bin.
        nx, ny = bins
        hb = ax.hist2d(x, y, bins=(nx, ny), cmap=density_colormap)
        cbar = fig.colorbar(hb[3], ax=ax)
        cbar.set_label(_("count"))
    elif color_by_season:
        # Cyclic coloring by day-of-year on a cyclic colormap, so the same
        # season in different years shares a color. Map DOY -> [0,1) and use
        # 'twilight' (a cyclic colormap whose ends meet).
        t = pd.to_datetime(df[date_col])
        doy = t.dt.dayofyear.to_numpy(dtype="float64")
        frac = (doy - 1.0) / 366.0  # [0,1); 366 keeps leap-day inside range
        sc = ax.scatter(
            x,
            y,
            c=frac,
            s=point_size,
            alpha=point_alpha,
            marker=marker,
            cmap="twilight",
            vmin=0.0,
            vmax=1.0,
        )
        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_label(_("month"))
        # Tick the colorbar at month boundaries, labelled by month name. The
        # bar is cyclic, so Jan appears at both ends (the ends meet).
        import datetime as _dt

        month_starts = [
            ((_dt.date(2001, m, 1) - _dt.date(2001, 1, 1)).days) / 366.0
            for m in range(1, 13)
        ]
        month_labels = [
            _dt.date(2001, m, 1).strftime("%b") for m in range(1, 13)
        ]
        cbar.set_ticks(month_starts)
        cbar.set_ticklabels(month_labels)
    elif color_by_time:
        # Encode the absolute timestamp as an ordinal for the colormap, then
        # relabel the colorbar ticks with readable dates.
        t = pd.to_datetime(df[date_col])
        tnum = mpl.dates.date2num(t.dt.to_pydatetime())
        sc = ax.scatter(
            x, y, c=tnum, s=point_size, alpha=point_alpha, marker=marker, cmap="viridis"
        )
        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_label(_("time"))
        loc = mpl.dates.AutoDateLocator()
        cbar.ax.yaxis.set_major_locator(loc)
        cbar.ax.yaxis.set_major_formatter(mpl.dates.ConciseDateFormatter(loc))
    else:
        ax.scatter(
            x,
            y,
            s=point_size,
            alpha=point_alpha,
            marker=marker,
            color=point_color or "tab:blue",
        )

    if fits.get("ols"):
        f = fits["ols"]
        xx = np.array([np.nanmin(x), np.nanmax(x)])
        label = "OLS"
        if show_stats:
            label = _("OLS: slope={s:.3g}, R^2={r:.3f}").format(s=f["slope"], r=f["r2"])
        ax.plot(
            xx,
            f["slope"] * xx + f["intercept"],
            color="black",
            lw=line_width,
            label=label,
        )

    if fits.get("lowess"):
        xs, ys = fits["lowess"]
        ax.plot(xs, ys, color="tab:red", lw=line_width, label="LOWESS")

    if fits.get("gam"):
        xs, ys = fits["gam"]
        ax.plot(xs, ys, color="tab:green", lw=line_width, label="GAM")

    ax.set_xlabel(x_label or xstrds)
    ax.set_ylabel(y_label or ystrds)
    if title:
        ax.set_title(title)
    if grid:
        ax.grid(True)
    if fits.get("ols") or fits.get("lowess") or fits.get("gam"):
        ax.legend(loc="best", fontsize=fontsize * 0.9)

    fig.tight_layout()
    if output:
        fig.savefig(output, dpi=dpi)
        gs.message(_("Plot written to {}").format(output))
    else:
        plt.show()


def write_csv(df, csv_path):
    """Write the paired samples to CSV."""
    df.to_csv(csv_path, index=False)
    gs.message(_("Samples written to {}").format(csv_path))


def main(options, flags):
    xstrds = options["xstrds"]
    ystrds = options["ystrds"]
    points_map = options["points"]
    where = options["where"]
    method = options["method"] or "nearest"
    tolerance_opt = options["tolerance"]
    frequency = options["frequency"]
    lag_opt = options["lag"]
    lag_window_opt = options["lag_window"]
    lag_stat = options["lag_stat"] or "sum"
    nprocs = int(options["nprocs"]) if options["nprocs"] else 0
    if nprocs <= 0:
        import multiprocessing
        nprocs = multiprocessing.cpu_count()
    lowess_frac = float(options["lowess_frac"]) if options["lowess_frac"] else 0.3
    output = options["output"]
    csv = options["csv"]
    backend_opt = options["backend"]
    dpi = float(options["dpi"]) if options["dpi"] else 300
    plot_dimensions = options["plot_dimensions"]
    fontsize = float(options["fontsize"]) if options["fontsize"] else 10
    line_width = float(options["line_width"]) if options["line_width"] else 1.5
    title = options["title"]
    x_label = options["x_label"]
    y_label = options["y_label"]
    point_color = grass_color_to_mpl(options["color"]) if options["color"] else None
    point_size = float(options["s"]) if options["s"] else 12
    marker = options["marker"] or "o"
    point_alpha = float(options["point_alpha"]) if options["point_alpha"] else 0.6

    show_ols = flags["o"]
    show_lowess = flags["l"]
    show_gam = flags["g"]
    show_stats = flags["t"]
    color_by_time = flags["c"]
    color_by_season = flags["y"]
    density = flags["D"]
    grid = flags["d"]
    bins_opt = options["bins"] or "30,30"
    density_colormap = options["density_colormap"] or "viridis"

    # Mutually exclusive rendering modes: absolute-time color, cyclic-season
    # color, and density are three alternative renderings of the same cloud.
    chosen = [
        name
        for name, on in (("-c", color_by_time), ("-y", color_by_season), ("-D", density))
        if on
    ]
    if len(chosen) > 1:
        gs.fatal(
            _(
                "Flags {a} are mutually exclusive; choose at most one rendering "
                "mode (absolute-time color, cyclic-season color, or density)."
            ).format(a=", ".join(chosen))
        )

    backend = backend_opt or ("Agg" if output else "WXAgg")
    check_dependencies(backend, need_lowess=show_lowess, need_gam=show_gam)

    # Absolute-time guard. Relative time is not supported
    try:
        tx = gs.parse_command("t.info", flags="g", input=xstrds)
    except CalledModuleError:
        gs.fatal(_("Space-time raster dataset '{}' not found.").format(xstrds))
    try:
        ty = gs.parse_command("t.info", flags="g", input=ystrds)
    except CalledModuleError:
        gs.fatal(_("Space-time raster dataset '{}' not found.").format(ystrds))
    for name, info in ((xstrds, tx), (ystrds, ty)):
        if info.get("temporal_type") != "absolute":
            gs.fatal(
                _(
                    "Dataset '{}' does not use absolute time. t.rast.scatter "
                    "only supports absolute-time datasets."
                ).format(name)
            )

    # Validate the method / tolerance / frequency combination.
    aggregate_methods = ("mean", "median", "sum", "min", "max")
    if method == "nearest":
        if frequency:
            gs.fatal(
                _(
                    "'frequency' applies only to the aggregate methods, not "
                    "method=nearest."
                )
            )
        if not tolerance_opt:
            gs.fatal(
                _("method=nearest requires a 'tolerance' (e.g. tolerance='1 day').")
            )
        tolerance = parse_tolerance(tolerance_opt)
    elif method in aggregate_methods:
        if tolerance_opt:
            gs.fatal(
                _(
                    "'tolerance' applies only to method=nearest, not the "
                    "aggregate methods."
                )
            )
        if not frequency:
            gs.fatal(
                _("method={m} requires a 'frequency' (e.g. frequency='MS').").format(
                    m=method
                )
            )
        tolerance = None
    else:
        gs.fatal(_("Unknown method '{}'.").format(method))

    # Parse and validate lag options.
    lag = parse_lag(lag_opt) if lag_opt else None
    lag_window = None
    if lag_window_opt:
        lag_window = parse_lag(lag_window_opt, allow_negative=False)
        if lag_window <= pd.Timedelta(0):
            gs.fatal(_("'lag_window' must be a positive duration."))
        if lag is None:
            # Window with no explicit lag: window ends at the response time.
            lag = pd.Timedelta(0)
    if lag_window_opt and method != "nearest":
        gs.fatal(
            _(
                "Accumulation lag ('lag_window') is currently supported only "
                "with method=nearest."
            )
        )

    # Sample each dataset at the vector's points across all its own timesteps.
    gs.message(_("Sampling '{}' at the sample points...").format(xstrds))
    xdf = sample_long(xstrds, points_map, where=where, nprocs=nprocs)
    gs.message(_("Sampling '{}' at the sample points...").format(ystrds))
    ydf = sample_long(ystrds, points_map, where=where, nprocs=nprocs)

    # Apply lag to the x (driver) dataset before pairing.
    if lag_window is not None:
        # Accumulation mode: reduce driver maps in the preceding window per
        # response time. Produces a driver frame already aligned to response
        # dates, so it pairs exactly (nearest with a tiny tolerance).
        gs.message(
            _("Accumulating driver over {w} (lag {l}, {s})...").format(
                w=lag_window, l=lag, s=lag_stat
            )
        )
        xdf = apply_lag_accumulate(xdf, ydf, lag, lag_window, lag_stat)
    elif lag is not None:
        # Instantaneous shift: relabel driver dates by +lag.
        gs.message(_("Shifting driver by lag {} ...").format(lag))
        xdf = apply_lag(xdf, lag)

    # Pair the two datasets according to the chosen method.
    if method == "nearest":
        gs.message(_("Pairing by nearest timestamp within {} ...").format(tolerance))
        df = pair_nearest(xdf, ydf, tolerance)
        date_col = "date"
    else:
        gs.message(
            _("Aggregating to '{f}' ({m}) and pairing...").format(f=frequency, m=method)
        )
        df = pair_aggregate(xdf, ydf, frequency, method)
        date_col = "period"

    gs.message(_("Collected {} paired (x, y) observations.").format(len(df)))
    if len(df) < 2:
        gs.fatal(_("Too few paired observations to plot or fit."))

    # Fits.
    x = df["x"].to_numpy(dtype="float64")
    y = df["y"].to_numpy(dtype="float64")
    fits = {}
    if show_ols:
        fits["ols"] = fit_ols(x, y)
        if fits["ols"]:
            gs.message(
                _(
                    "OLS: slope={s:.4g}, intercept={i:.4g}, R^2={r:.3f}, "
                    "p={p:.3g}, n={n}"
                ).format(
                    s=fits["ols"]["slope"],
                    i=fits["ols"]["intercept"],
                    r=fits["ols"]["r2"],
                    p=fits["ols"]["pvalue"],
                    n=fits["ols"]["n"],
                )
            )
    if show_lowess:
        fits["lowess"] = fit_lowess(x, y, lowess_frac)
    if show_gam:
        fits["gam"] = fit_gam_curve(x, y)

    if csv:
        write_csv(df, csv)

    gs.message(_("Creating the figure..."))
    dimensions = (
        [float(v) for v in plot_dimensions.split(",")] if plot_dimensions else [7, 7]
    )
    # Parse density bins.
    try:
        bx, by = (int(v) for v in bins_opt.split(","))
        bins_tuple = (bx, by)
    except (ValueError, TypeError):
        gs.fatal(_("Could not parse bins '{}'; use 'nx,ny' (e.g. '30,30').").format(bins_opt))

    plot_scatter(
        df=df,
        xstrds=xstrds,
        ystrds=ystrds,
        date_col=date_col,
        output=output,
        dpi=dpi,
        dimensions=dimensions,
        point_color=point_color,
        color_by_time=color_by_time,
        fits=fits,
        show_stats=show_stats,
        color_by_season=color_by_season,
        density=density,
        bins=bins_tuple,
        density_colormap=density_colormap,
        fontsize=fontsize,
        line_width=line_width,
        title=title,
        x_label=x_label,
        y_label=y_label,
        grid=grid,
        point_size=point_size,
        marker=marker,
        point_alpha=point_alpha,
    )


if __name__ == "__main__":
    sys.exit(main(*gs.parser()))

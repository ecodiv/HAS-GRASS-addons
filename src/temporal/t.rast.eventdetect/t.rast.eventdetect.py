#!/usr/bin/env python

############################################################################
#
# MODULE:       t.rast.eventdetect
# AUTHOR:       Paulo van Breugel
# PURPOSE:      Detect and count relatively rapid changes (events) in a
#               space-time raster dataset (strds) and characterize the
#               recovery after each event. Works per pixel on the raw,
#               irregularly spaced observations (NULL gaps kept), using the
#               actual acquisition dates. Generalized from the grassland
#               mowing-frequency method of Kolecka et al. (2018).
#
# COPYRIGHT:    (c) 2026 Paulo van Breugel and the GRASS Development Team
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################

# %module
# % description: Detects and counts rapid changes (events) in a space-time raster dataset and characterizes post-event recovery.
# % keyword: temporal
# % keyword: raster
# % keyword: time series
# % keyword: change detection
# % keyword: phenology
# %end

# %option G_OPT_STRDS_INPUT
# % key: input
# % guisection: Input
# %end

# %option
# % key: year
# % type: integer
# % label: Calendar year to analyze
# % description: Restrict the analysis to this calendar year. If omitted, the whole series is used (events are still confined to one year only when set).
# % required: no
# % guisection: Input
# %end

# %option G_OPT_V_INPUT
# % key: vector
# % required: no
# % label: Parcel vector map for per-parcel analysis
# % description: If given, each observation is reduced to a per-parcel median before detection, and detection runs once per parcel instead of once per pixel. The summary rasters are then constant within each parcel. Boundary handling (e.g. an inward buffer for "shrunken parcels") is left to preprocessing: pass an already-buffered map.
# % guisection: Input
# %end

# %option
# % key: min_clear
# % type: double
# % label: Minimum clear fraction of a parcel per date (vector mode)
# % description: A parcel yields a value on a given date only when at least this fraction of its pixels are clear. 0 accepts any single clear pixel. Used only with vector.
# % answer: 0.0
# % options: 0.0-1.0
# % required: no
# % guisection: Input
# %end

# %option G_OPT_MEMORYMB
# % guisection: Input
# %end

# %option G_OPT_R_BASENAME_OUTPUT
# % key: output
# % label: Prefix for the summary output rasters
# % description: Summary rasters are written as <output>_count, <output>_first_doy, etc.
# % guisection: Output
# %end

# %option
# % key: direction
# % type: string
# % label: Direction of change to detect
# % options: drop,rise,both
# % answer: drop
# % guisection: Detection
# %end

# %option
# % key: threshold
# % type: double
# % label: Change magnitude that counts as an event
# % description: Interpreted according to threshold_type. Applied to both directions unless threshold_drop / threshold_rise are given.
# % answer: 0.2
# % guisection: Detection
# %end

# %option
# % key: threshold_drop
# % type: double
# % label: Separate threshold for drops (direction=both)
# % required: no
# % guisection: Detection
# %end

# %option
# % key: threshold_rise
# % type: double
# % label: Separate threshold for rises (direction=both)
# % required: no
# % guisection: Detection
# %end

# %option
# % key: threshold_type
# % type: string
# % label: How the threshold is interpreted
# % description: absolute = value units; relative = fraction of the pre-event level; mad = multiples of the per-pixel robust SD (1.4826*MAD) over the analyzed year.
# % options: absolute,relative,mad
# % answer: absolute
# % guisection: Detection
# %end

# %option
# % key: lookback
# % type: integer
# % label: Number of previous clear observations to compare against
# % description: 1 = compare only to the last clear observation; 2 = also compare to the second-to-last clear observation (catches events hidden by a cloudy preceding date).
# % answer: 2
# % options: 1-2
# % guisection: Detection
# %end

# %option
# % key: min_separation
# % type: double
# % label: Minimum separation between events (days)
# % description: Two detections closer than this collapse into one (the first is kept). Default is 2*step.
# % required: no
# % guisection: Detection
# %end

# %option
# % key: max_gap
# % type: double
# % label: Maximum observation gap to compare across (days)
# % description: Comparisons that span a longer gap than this (e.g. a long cloudy period) are ignored. Default is 3*step.
# % required: no
# % guisection: Detection
# %end

# %option
# % key: step
# % type: double
# % label: Nominal observation interval (days)
# % description: Used only to derive default min_separation and max_gap. If omitted it is autodetected from the dataset granularity, else the median spacing of the observations.
# % required: no
# % guisection: Detection
# %end

# %option
# % key: season_start
# % type: integer
# % label: First day-of-year to consider (inclusive)
# % required: no
# % options: 1-366
# % guisection: Detection
# %end

# %option
# % key: season_end
# % type: integer
# % label: Last day-of-year to consider (inclusive)
# % required: no
# % options: 1-366
# % guisection: Detection
# %end

# %option
# % key: baseline_window
# % type: integer
# % label: Number of pre-event observations for the reference level
# % description: The reported event magnitude and the observed-mode recovery baseline R are the maximum (drop) / minimum (rise) of the last N clear observations before the event. 1 reproduces Kolecka et al. (2018).
# % answer: 1
# % guisection: Recovery
# %end

# %option
# % key: baseline
# % type: string
# % label: Recovery reference
# % description: observed = recover toward the pre-event level; reference = recover toward the expected level given by a climatology strds (anomaly closing).
# % options: observed,reference
# % answer: observed
# % guisection: Recovery
# %end

# %option G_OPT_STRDS_INPUT
# % key: reference
# % required: no
# % label: Reference (climatology) strds for baseline=reference
# % description: Relative-time strds keyed by day-of-year, e.g. an NDVI climatology. Used only for recovery, never for detection.
# % guisection: Recovery
# %end

# %option
# % key: recovery_target
# % type: double
# % label: Recovery fraction required to count as recovered
# % description: Fraction of the change that must be undone before the next event (or season end) for the event to count as recovered.
# % answer: 0.8
# % options: 0.0-1.0
# % guisection: Recovery
# %end

import json
from datetime import datetime

import grass.script as gs


def _json(result):
    """Parse the JSON stdout of a Tools result."""
    return json.loads(result.stdout)


def _doy(dt):
    """Day-of-year (1-366) of a datetime."""
    return dt.timetuple().tm_yday


def _parse_time(value):
    """Parse a GRASS start_time string to a datetime."""
    value = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    gs.fatal(_("Could not parse time value '{}'.").format(value))


def read_series(tools, strds, year):
    """Return [(map_name, doy), ...] ordered by time for the requested year."""
    where = None
    if year:
        where = (
            f"start_time >= '{year}-01-01' AND start_time < '{year + 1}-01-01'"
        )
    kwargs = dict(
        input=strds,
        columns="name,start_time",
        order="start_time",
        format="json",
    )
    if where:
        kwargs["where"] = where
    rows = _json(tools.t_rast_list(**kwargs))["data"]
    series = [(r["name"], _parse_time(r["start_time"])) for r in rows]
    return [(name, _doy(dt)) for name, dt in series], [dt for _, dt in series]


def autodetect_step(tools, strds, datetimes):
    """Nominal observation interval in days: granularity, else median spacing."""
    try:
        info = _json(tools.t_info(input=strds, flags="g", format="json"))
        gran = str(info.get("granularity", "")).strip()
        if gran.endswith("days"):
            return float(gran.split()[0])
        if gran.endswith("day"):
            return 1.0
    except Exception:
        pass
    if len(datetimes) >= 2:
        diffs = sorted(
            (datetimes[i + 1] - datetimes[i]).days
            for i in range(len(datetimes) - 1)
        )
        med = diffs[len(diffs) // 2]
        if med > 0:
            return float(med)
    return 5.0


def read_reference_index(tools, reference):
    """Map day-of-year -> reference map name for a climatology strds."""
    rows = _json(tools.t_rast_list(
        input=reference, columns="name,start_time", order="start_time",
        format="json",
    ))["data"]
    index = {}
    for r in rows:
        start = str(r["start_time"]).strip()
        try:
            doy = int(float(start))
        except ValueError:
            doy = _doy(_parse_time(start))
        index[doy] = r["name"]
    return index


def main():
    import numpy as np
    import grass.script.array as garray
    from grass.tools import Tools

    options, flags = gs.parser()
    tools = Tools()

    strds = options["input"]
    year = int(options["year"]) if options["year"] else None
    out = options["output"]
    direction = options["direction"]
    ttype = options["threshold_type"]
    lookback = int(options["lookback"])
    baseline_window = max(1, int(options["baseline_window"]))
    baseline = options["baseline"]
    reference = options["reference"]
    recovery_target = float(options["recovery_target"])

    vector = options["vector"]
    parcel_mode = bool(vector)
    min_clear = float(options["min_clear"]) if options["min_clear"] else 0.0
    memory = int(options["memory"]) if options["memory"] else 300

    thr = float(options["threshold"])
    thr_drop = float(options["threshold_drop"]) if options["threshold_drop"] else thr
    thr_rise = float(options["threshold_rise"]) if options["threshold_rise"] else thr

    season_start = int(options["season_start"]) if options["season_start"] else None
    season_end = int(options["season_end"]) if options["season_end"] else None

    if baseline == "reference" and not reference:
        gs.fatal(_("baseline=reference requires a 'reference' strds."))

    records, datetimes = read_series(tools, strds, year)
    if len(records) < 2:
        gs.fatal(_("Need at least two maps to detect events."))

    step = float(options["step"]) if options["step"] else autodetect_step(
        tools, strds, datetimes
    )
    min_separation = (
        float(options["min_separation"])
        if options["min_separation"]
        else 2.0 * step
    )
    max_gap = float(options["max_gap"]) if options["max_gap"] else 3.0 * step
    gs.message(
        _("Nominal step {:.0f} d; min_separation {:.0f} d; max_gap {:.0f} d.").format(
            step, min_separation, max_gap
        )
    )

    # Optional per-parcel mode: reduce each observation to a per-parcel median
    # so that detection runs once per parcel instead of once per pixel. The
    # detection machinery is shape-agnostic, so in this mode every state array
    # is 1-D with one element per parcel.
    label_idx = lab_flat = parcel_sizes = None
    n_parcels = 0
    if parcel_mode:
        import atexit

        tmp_parcels = gs.append_node_pid("t_rast_eventdetect_parcels")
        atexit.register(
            lambda: gs.run_command(
                "g.remove", flags="f", type="raster",
                name=tmp_parcels, quiet=True,
            )
        )
        tools.v_to_rast(
            input=vector, output=tmp_parcels, use="cat", type="area",
            memory=memory, overwrite=True,
        )
        labels = np.asarray(garray.array(tmp_parcels), dtype=np.float64)
        present = np.isfinite(labels)
        if not present.any():
            gs.fatal(_("The parcel map covers no cells in the current region."))
        cats = labels[present].astype(np.int64)
        uniq_cats = np.unique(cats)
        n_parcels = int(uniq_cats.size)
        label_idx = np.full(labels.shape, -1, dtype=np.int64)
        label_idx[present] = np.searchsorted(uniq_cats, cats)
        lab_flat = label_idx.ravel()
        parcel_sizes = np.bincount(
            lab_flat[lab_flat >= 0], minlength=n_parcels
        ).astype(np.float32)
        gs.message(_("Per-parcel mode: {} parcels.").format(n_parcels))

    def parcel_median(a2d):
        """Per-parcel median of a 2D array as a 1-D array (one value per parcel)."""
        xf = a2d.ravel()
        keep = np.isfinite(xf) & (lab_flat >= 0)
        med = np.full(n_parcels, np.nan, np.float32)
        if keep.any():
            lab = lab_flat[keep]
            val = xf[keep].astype(np.float32)
            order = np.lexsort((val, lab))
            lab_s = lab[order]
            val_s = val[order]
            uniq, start, counts = np.unique(
                lab_s, return_index=True, return_counts=True
            )
            lo = start + (counts - 1) // 2
            hi = start + counts // 2
            med[uniq] = 0.5 * (val_s[lo] + val_s[hi])
            if min_clear > 0:
                frac = counts / parcel_sizes[uniq]
                med[uniq[frac < min_clear]] = np.nan
        return med

    def read_map(name):
        """Read a map as a 2D pixel array, or a 1-D per-parcel median array."""
        a = np.asarray(garray.array(name), dtype=np.float32)
        return parcel_median(a) if parcel_mode else a

    shape = read_map(records[0][0]).shape

    # Per-pixel robust scale for threshold_type=mad (loads the year stack).
    mad = None
    if ttype == "mad":
        import warnings

        gs.message(_("threshold_type=mad: loading the year stack for the robust SD."))
        stack = np.empty((len(records),) + shape, dtype=np.float32)
        for i, (name, _d) in enumerate(records):
            stack[i] = read_map(name)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            med = np.nanmedian(stack, axis=0)
            mad = 1.4826 * np.nanmedian(np.abs(stack - med), axis=0)
        del stack

    ref_index = read_reference_index(tools, reference) if reference else None
    ref_doys = sorted(ref_index) if ref_index else []
    ref_cache = {}

    def reference_array(doy):
        """Nearest-DOY climatology array (cached by map name)."""
        nearest = min(ref_doys, key=lambda d: abs(d - doy))
        name = ref_index[nearest]
        if name not in ref_cache:
            ref_cache.clear()
            ref_cache[name] = read_map(name)
        return ref_cache[name]

    directions = {"drop": [1], "rise": [-1], "both": [1, -1]}[direction]
    thr_for = {1: thr_drop, -1: thr_rise}

    # Accumulators shared across directions.
    n_events = np.zeros(shape, np.float32)
    n_drops = np.zeros(shape, np.float32)
    n_rises = np.zeros(shape, np.float32)
    first_doy = np.zeros(shape, np.float32)
    last_doy = np.zeros(shape, np.float32)
    sum_mag = np.zeros(shape, np.float32)
    max_mag = np.zeros(shape, np.float32)
    n_recovered = np.zeros(shape, np.float32)
    sum_recdays = np.zeros(shape, np.float32)
    n_interrupted = np.zeros(shape, np.float32)
    sum_maxf = np.zeros(shape, np.float32)
    n_incomplete = np.zeros(shape, np.float32)
    ever_valid = np.zeros(shape, bool)

    eps = 1e-6
    K = max(lookback, baseline_window)

    for sign in directions:
        # hist[0] = last clear value, hist[1] = second-to-last, ...
        hist = [np.full(shape, np.nan, np.float32) for _ in range(K)]
        hist_doy = [np.full(shape, np.nan, np.float32) for _ in range(K)]
        last_event_doy = np.full(shape, -1e9, np.float32)

        is_open = np.zeros(shape, bool)
        recov_R = np.full(shape, np.nan, np.float32)
        extreme = np.full(shape, np.nan, np.float32)
        event_doy = np.full(shape, np.nan, np.float32)
        cur_maxf = np.zeros(shape, np.float32)

        for name, doy in records:
            x = read_map(name)
            clear = np.isfinite(x)
            ever_valid |= clear
            v = sign * x  # detect drops in v regardless of direction

            in_season = True
            if season_start is not None and doy < season_start:
                in_season = False
            if season_end is not None and doy > season_end:
                in_season = False

            # --- detection: drop in v vs last / second-to-last clear obs ---
            event = np.zeros(shape, bool)
            if in_season:
                for k in range(lookback):
                    prev = hist[k]
                    gap = doy - hist_doy[k]
                    dropv = prev - v
                    ok = clear & np.isfinite(prev) & (gap <= max_gap)
                    if ttype == "absolute":
                        t_eff = thr_for[sign]
                    elif ttype == "relative":
                        t_eff = thr_for[sign] * np.abs(prev)
                    else:  # mad
                        t_eff = thr_for[sign] * mad
                    event |= ok & (dropv > t_eff)

            # collapse detections within min_separation (keep first)
            event_eff = event & ((doy - last_event_doy) >= min_separation)

            # --- recovery bookkeeping on open events (before opening new) ---
            active = is_open & clear
            if baseline == "reference":
                ref = reference_array(doy)
                rec_x = v - sign * ref  # anomaly in v-space
            else:
                rec_x = v

            # events interrupted by a new event
            interrupt = active & event_eff
            n_interrupted[interrupt] += 1.0
            sum_maxf[interrupt] += np.clip(cur_maxf[interrupt], 0.0, 1.0)
            is_open[interrupt] = False

            # ongoing recovery for still-open events without a new event
            cont = is_open & clear & ~event_eff
            extreme[cont] = np.minimum(extreme[cont], rec_x[cont])
            denom = recov_R - extreme
            with np.errstate(invalid="ignore", divide="ignore"):
                f = (rec_x - extreme) / denom
            valid_f = cont & (denom > eps)
            cur_maxf[valid_f] = np.maximum(cur_maxf[valid_f], f[valid_f])
            recovered = valid_f & (f >= recovery_target)
            n_recovered[recovered] += 1.0
            sum_recdays[recovered] += doy - event_doy[recovered]
            is_open[recovered] = False

            # --- open new events ---
            if event_eff.any():
                # pre-event reference level for magnitude and observed recovery
                # R (max over the pre-event window in v-space, NaN-safe via
                # fmax). AD-1 is always included; the window is extended further
                # back only across clear observations that stay contiguous
                # (no step longer than max_gap) and that lie after the previous
                # event, so R never references a value from before a cloud gap
                # or from before an earlier event.
                pre_level = hist[0].copy()
                still = np.ones(shape, bool)
                for k in range(1, baseline_window):
                    step_gap = hist_doy[k - 1] - hist_doy[k]
                    still = (
                        still
                        & np.isfinite(step_gap)
                        & (step_gap <= max_gap)
                        & (hist_doy[k] > last_event_doy)
                    )
                    pre_level = np.where(still, np.fmax(pre_level, hist[k]), pre_level)
                mag = pre_level - v  # >= 0 in v-space

                opening = event_eff
                n_events[opening] += 1.0
                if sign == 1:
                    n_drops[opening] += 1.0
                else:
                    n_rises[opening] += 1.0
                sum_mag[opening] += mag[opening]
                max_mag[opening] = np.maximum(max_mag[opening], mag[opening])
                fresh = opening & (first_doy == 0)
                first_doy[fresh] = doy
                last_doy[opening] = doy

                is_open[opening] = True
                extreme[opening] = rec_x[opening]
                event_doy[opening] = doy
                cur_maxf[opening] = 0.0
                if baseline == "reference":
                    recov_R[opening] = 0.0
                else:
                    recov_R[opening] = pre_level[opening]
                last_event_doy[opening] = doy

            # --- advance clear-observation history (LOCF) ---
            for k in range(K - 1, 0, -1):
                hist[k][clear] = hist[k - 1][clear]
                hist_doy[k][clear] = hist_doy[k - 1][clear]
            hist[0][clear] = v[clear]
            hist_doy[0][clear] = doy

        # events still open at the end of the series: incomplete recoveries
        n_incomplete[is_open] += 1.0

    # --- derived summaries and output ---
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_mag = np.where(n_events > 0, sum_mag / n_events, np.nan)
        frac_rec = np.where(n_events > 0, n_recovered / n_events, np.nan)
        mean_recdays = np.where(n_recovered > 0, sum_recdays / n_recovered, np.nan)
        mean_pctrest = np.where(
            n_interrupted > 0, 100.0 * sum_maxf / n_interrupted, np.nan
        )

    def write(arr, suffix):
        g = garray.array()
        if parcel_mode:
            vals = np.where(ever_valid, arr, np.nan)
            out2d = np.full(label_idx.shape, np.nan, np.float64)
            sel = label_idx >= 0
            out2d[sel] = vals[label_idx[sel]]
            g[...] = out2d
        else:
            g[...] = np.where(ever_valid, arr, np.nan).astype(np.float64)
        g.write(mapname=f"{out}_{suffix}", overwrite=gs.overwrite())

    write(n_events, "count")
    write(np.where(n_events > 0, first_doy, np.nan), "first_doy")
    write(np.where(n_events > 0, last_doy, np.nan), "last_doy")
    write(mean_mag, "mean_magnitude")
    write(np.where(n_events > 0, max_mag, np.nan), "max_magnitude")
    write(n_recovered, "n_recovered")
    write(frac_rec, "frac_recovered")
    write(mean_recdays, "mean_recovery_days")
    write(mean_pctrest, "mean_percent_restored")
    write(n_incomplete, "n_incomplete")
    if direction == "both":
        write(n_drops, "n_drops")
        write(n_rises, "n_rises")

    gs.message(_("Wrote summary rasters with prefix '{}'.").format(out))


if __name__ == "__main__":
    main()

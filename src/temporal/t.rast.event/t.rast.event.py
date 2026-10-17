#!/usr/bin/env python

############################################################################
#
# MODULE:       t.rast.event
# AUTHOR:       Paulo van Breugel
# PURPOSE:      Detect and count relatively rapid changes (events) in a
#               space-time raster dataset (strds) and characterize the
#               recovery after each event. Works per pixel on the raw,
#               irregularly spaced observations (NULL gaps kept), using the
#               actual acquisition dates. An event is one continuous descent
#               (or rise), measured peak-to-trough; this generalizes the
#               grassland mowing-frequency method of Kolecka et al. (2018).
#
# SPDX-FileCopyrightText: 2026 Paulo van Breugel
# SPDX-FileCopyrightText: Other GRASS authors
# SPDX-License-Identifier: GPL-2.0-or-later
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
# % key: groupby
# % type: string
# % label: Temporal grouping
# % description: year = detect events within each yearly cycle separately (the default); none = treat the whole dataset as one continuous series (e.g. annual data, or drops and recoveries that span several years).
# % options: year,none
# % answer: year
# % required: no
# % guisection: Input
# %end

# %option
# % key: year
# % type: integer
# % label: Cycle to analyze
# % description: Restrict the analysis to a single yearly cycle, identified by the calendar year in which the cycle starts (see year_start). If omitted, every cycle present in the input is analyzed separately. Not used with groupby=none.
# % required: no
# % guisection: Input
# %end

# %option
# % key: year_start
# % type: string
# % label: First day of the yearly cycle (MM-DD)
# % description: Month-day on which each yearly cycle begins, e.g. 06-01 for a monsoon or hydrological year. The default 01-01 groups by calendar year. Only used with groupby=year.
# % answer: 01-01
# % required: no
# % guisection: Input
# %end

# %option G_OPT_V_INPUT
# % key: vector
# % required: no
# % label: Parcel vector map
# % description: Use for per-parcel analysis. If given, each observation is reduced to a per-parcel median before detection, and detection runs once per parcel instead of once per pixel. The summary rasters are then constant within each parcel.
# % guisection: Input
# %end

# %option
# % key: min_clear
# % type: double
# % label: Minimum fraction of a parcel per date with value
# % description: A parcel yields a value on a given date only when at least this fraction of its pixels have a value. 0 accepts any single pixel with value. Used only with vector.
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
# % label: Prefix for the output rasters
# % description: Summary rasters are written as <output>_count, <output>_first_doy, etc.
# % guisection: Output
# %end

# %option
# % key: direction
# % type: string
# % label: Direction of change to detect
# % options: drop,rise
# % answer: drop
# % guisection: Detection
# %end

# %option
# % key: threshold
# % type: double
# % label: Minimum required magnitude change
# % description: Minimum magnitude change that counts as an event. Interpreted according to threshold_type.
# % answer: 0.2
# % guisection: Detection
# %end

# %option
# % key: threshold_type
# % type: string
# % label: Interpretation threshold
# % description: absolute = value units; relative = fraction of the pre-event level; mad = multiples of the per-pixel robust SD (1.4826*MAD) over the analyzed year.
# % options: absolute,relative,mad
# % answer: absolute
# % guisection: Detection
# %end

# %option
# % key: max_gap
# % type: double
# % label: Maximum observation gap (days)
# % description: A descent (or ascent) is not continued across a gap longer than this (e.g. a long cloudy period), so seasonal development across clouds is not mistaken for one event. Default is 3*step.
# % required: no
# % guisection: Detection
# %end

# %option
# % key: step
# % type: double
# % label: Nominal observation interval (days)
# % description: Used only to derive the default max_gap. If omitted it is autodetected from the dataset granularity, else the median spacing of the observations.
# % required: no
# % guisection: Detection
# %end

# %option
# % key: season_start
# % type: integer
# % label: First day-of-year
# % description: First day-of-year to consider. Detection of events will start from this date on forwards.
# % required: no
# % options: 1-366
# % guisection: Detection
# %end

# %option
# % key: season_end
# % type: integer
# % label: Last day-of-year
# % description: Last day-of-year to consider. Detection of events will stop at this date.
# % required: no
# % options: 1-366
# % guisection: Detection
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
# % label: Reference strds
# % description: Reference (climatology) strds for baseline=reference. Should be a relative-time strds keyed by day-of-year, e.g. an NDVI climatology. Used only for recovery, never for detection.
# % guisection: Recovery
# %end

# %option
# % key: recovery_target
# % type: double
# % label: Recovery fraction
# % description: Fraction of the change that must be undone before the next event (or season end) for the event to count as recovered.
# % answer: 0.8
# % options: 0.0-1.0
# % guisection: Recovery
# %end

# %option
# % key: max_event_days
# % type: double
# % label: Maximum descent duration
# % description: A descent (peak to trough) that takes longer than this many days is treated as gradual (seasonal) change and not counted. Use a large value to disable. Default 30 for groupby=year, and 1.5*step for groupby=none.
# % required: no
# % guisection: Detection
# %end

# %option
# % key: noise_tolerance
# % type: double
# % label: Noise tolerance
# % description: A descent is considered ended when the signal rebounds from the trough by more than this fraction of the current peak-to-trough amplitude. Larger values keep a wiggly decline as one event; smaller values split it. A suitable value depends on the index.
# % answer: 0.15
# % options: 0.0-1.0
# % guisection: Detection
# %end

# %flag
# % key: g
# % label: gap-diagnostics
# % description: Write gap-diagnostic rasters (<output>_n_obs, _mean_gap, _max_gap_obs)
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


def cycle_anchor(dt, month, day):
    """Start datetime of the yearly cycle that dt belongs to.

    The cycle begins on `month`-`day` each year; observations before that date
    belong to the cycle that started in the previous calendar year. With the
    default 1 January this is simply the calendar year.
    """
    start = datetime(dt.year, month, day)
    return start if dt >= start else datetime(dt.year - 1, month, day)


def _parse_time(value):
    """Parse a GRASS start_time string to a datetime."""
    value = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    gs.fatal(_("Could not parse time value '{}'.").format(value))


def strds_info(strds):
    """Return the 't.info -g' key/value pairs of a space-time dataset."""
    info = gs.parse_command("t.info", input=strds, flags="g")
    return {k: str(v).strip().strip("'\"") for k, v in info.items()}


def read_series(tools, strds):
    """Return [(map_id, datetime), ...] for the whole dataset, ordered by time.

    Maps are identified by their temporal id (name@mapset) so that an
    identically named raster in another mapset cannot be picked instead.
    Grouping into cycles (and any year restriction) is done afterwards in
    Python, because a shifted year_start makes a plain SQL year window wrong.
    """
    rows = _json(tools.t_rast_list(
        input=strds, columns="id,start_time", order="start_time",
        format="json",
    ))["data"]
    return [(r["id"], _parse_time(r["start_time"])) for r in rows]


def step_from_granularity(gran):
    """Nominal step in days from a 't.info' granularity string, or None."""
    gran = gran.strip()
    if gran.endswith("days"):
        return float(gran.split()[0])
    if gran.endswith("day"):
        return 1.0
    return None


def median_spacing(datetimes):
    """Median spacing in days between consecutive observations, or None."""
    if len(datetimes) < 2:
        return None
    diffs = sorted(
        (datetimes[i + 1] - datetimes[i]).days for i in range(len(datetimes) - 1)
    )
    med = diffs[len(diffs) // 2]
    return float(med) if med > 0 else None


def read_reference_index(tools, reference):
    """Map day-of-year -> reference map id for a climatology strds."""
    rows = _json(tools.t_rast_list(
        input=reference, columns="id,start_time", order="start_time",
        format="json",
    ))["data"]
    index = {}
    for r in rows:
        start = str(r["start_time"]).strip()
        try:
            doy = int(float(start))
        except ValueError:
            doy = _doy(_parse_time(start))
        index[doy] = r["id"]
    return index


def main():
    import numpy as np
    import grass.script.array as garray
    from grass.tools import Tools
    from grass.pygrass.raster import RasterRow
    from grass.pygrass.raster.buffer import Buffer

    options, flags = gs.parser()
    tools = Tools()

    strds = options["input"]
    groupby = options["groupby"]
    year = int(options["year"]) if options["year"] else None
    year_start = options["year_start"] or "01-01"
    out = options["output"]
    direction = options["direction"]
    sign = 1 if direction == "drop" else -1
    ttype = options["threshold_type"]
    baseline = options["baseline"]
    reference = options["reference"]
    recovery_target = float(options["recovery_target"])
    max_event_days = (
        float(options["max_event_days"]) if options["max_event_days"] else None
    )
    turn_frac = float(options["noise_tolerance"])

    vector = options["vector"]
    parcel_mode = bool(vector)
    min_clear = float(options["min_clear"]) if options["min_clear"] else 0.0
    memory = int(options["memory"]) if options["memory"] else 300

    thr = float(options["threshold"])
    season_start = int(options["season_start"]) if options["season_start"] else None
    season_end = int(options["season_end"]) if options["season_end"] else None

    try:
        ys_month, ys_day = (int(p) for p in year_start.split("-"))
        datetime(2001, ys_month, ys_day)  # validate as an every-year date
    except (ValueError, TypeError):
        gs.fatal(_("year_start must be a valid month-day, e.g. 06-01."))

    if thr <= 0:
        gs.fatal(_("threshold must be positive."))
    if (
        season_start is not None
        and season_end is not None
        and season_start > season_end
    ):
        gs.fatal(_("season_start must not be greater than season_end."))
    if baseline == "reference" and not reference:
        gs.fatal(_("baseline=reference requires a 'reference' strds."))
    if groupby == "none":
        if year is not None:
            gs.fatal(_("year cannot be combined with groupby=none."))
        if year_start != "01-01":
            gs.warning(_("year_start is ignored with groupby=none."))

    info = strds_info(strds)
    if info.get("temporal_type") != "absolute":
        gs.fatal(_("Input <{}> must be an absolute-time strds.").format(strds))

    gs.message(_("Reading dataset <{}>.").format(strds))
    rows = read_series(tools, strds)
    if len(rows) < 2:
        gs.fatal(_("Need at least two maps to detect events."))

    step = float(options["step"]) if options["step"] else None
    if step is None:
        step = (
            step_from_granularity(info.get("granularity", ""))
            or median_spacing([dt for _, dt in rows])
            or 5.0
        )
    if step <= 0:
        gs.fatal(_("step must be positive."))
    max_gap = float(options["max_gap"]) if options["max_gap"] else 3.0 * step
    if max_gap <= 0:
        gs.fatal(_("max_gap must be positive."))
    # A whole-series run (groupby=none) is typically coarser (e.g. one map per
    # year), where the fixed 30-day default would reject every step as gradual;
    # scale it with the observation interval instead.
    if max_event_days is None:
        max_event_days = 30.0 if groupby == "year" else 1.5 * step
    gs.message(
        _("Nominal step {:.0f} d; max_gap {:.0f} d.").format(step, max_gap)
    )

    # Optional per-parcel mode: reduce each observation to a per-parcel median
    # so that detection runs once per parcel instead of once per pixel. The
    # detection machinery is shape-agnostic, so in this mode every state array
    # is 1-D with one element per parcel.
    label_idx = lab_flat = parcel_sizes = None
    n_parcels = 0
    if parcel_mode:
        import atexit

        tmp_parcels = gs.append_node_pid("t_rast_event_parcels")
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
        labels = np.asarray(garray.array(tmp_parcels, null=np.nan), dtype=np.float64)
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

    # Pixel mode streams the region in horizontal row strips so memory stays
    # bounded on large regions; parcel mode reduces each whole map to one value
    # per parcel, which is already small. Both feed the same detection kernel
    # (detect_block), which is agnostic to the block shape.
    reg = gs.region()
    nrows, ncols = int(reg["rows"]), int(reg["cols"])
    cell_null_in = -2147483648  # GRASS CELL NULL, mapped to NaN on read

    def read_full(name):
        """Whole-region pixel array with NULL as NaN (for parcel reduction)."""
        return np.asarray(garray.array(name, null=np.nan), dtype=np.float32)

    row_handles = {}

    def row_handle(mapid):
        rr = row_handles.get(mapid)
        if rr is None:
            name, _, mapset = mapid.partition("@")
            rr = RasterRow(name, mapset)
            rr.open("r")
            row_handles[mapid] = rr
        return rr

    def read_strip(mapid, r0, r1):
        """Rows [r0, r1) of a map over the current region, NULL as NaN.

        RasterRow reads region rows directly and applies the MASK; float NULL
        arrives as NaN. Integer (CELL) NULL arrives as INT_MIN, mapped to NaN.
        """
        rr = row_handle(mapid)
        block = np.empty((r1 - r0, ncols), np.float32)
        for i in range(r0, r1):
            block[i - r0] = rr[i]
        if rr.mtype == "CELL":
            block[block == cell_null_in] = np.nan
        return block

    def close_row_handles():
        for rr in row_handles.values():
            rr.close()
        row_handles.clear()

    ref_index = read_reference_index(tools, reference) if reference else None
    if reference and not ref_index:
        gs.fatal(_("Reference strds <{}> contains no maps.").format(reference))
    ref_doys = sorted(ref_index) if ref_index else []

    def nearest_ref(doy):
        """Map id of the climatology raster with the nearest (circular) DOY."""
        d = min(ref_doys, key=lambda dd: min(abs(dd - doy), 366 - abs(dd - doy)))
        return ref_index[d]

    eps = 1e-6

    def detect_block(records, shape, read_block, read_ref, report_progress):
        """Detect events for one block of the region and return the summaries.

        The block shape is arbitrary (a row strip of pixels, or one value per
        parcel); `read_block(mapid)` returns that block for an input map and
        `read_ref(doy)` the matching climatology block. A descent opens when the
        signal falls below the running peak, follows the signal down (bridging
        observations up to max_gap), and closes when the signal turns back up.
        The event is confirmed only if the peak-to-trough amplitude reaches the
        threshold, so a multi-step decline counts once and small wiggles are
        ignored. Recovery toward the pre-event peak (observed) or the climatology
        (reference) is tracked afterwards.

        Returns (results, ever_valid): a dict of output suffix -> array and the
        mask of cells with at least one in-season observation.
        """
        # Per-pixel robust scale for threshold_type=mad, from this year's stack.
        mad = None
        if ttype == "mad":
            import warnings

            if report_progress:
                gs.verbose(
                    _("threshold_type=mad: computing the robust SD from the"
                      " year stack.")
                )
            stack = np.empty((len(records),) + shape, dtype=np.float32)
            for i, (name, _d) in enumerate(records):
                stack[i] = read_block(name)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                med = np.nanmedian(stack, axis=0)
                mad = 1.4826 * np.nanmedian(np.abs(stack - med), axis=0)
            del stack

        n_events = np.zeros(shape, np.float32)
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

        v_ref = np.full(shape, np.nan, np.float32)     # running peak (v-space)
        ref_doy = np.full(shape, np.nan, np.float32)
        trough = np.full(shape, np.nan, np.float32)    # trough in raw v-space
        trough_doy = np.full(shape, np.nan, np.float32)
        rec_trough = np.full(shape, np.nan, np.float32)  # trough in recovery space
        in_desc = np.zeros(shape, bool)
        is_open = np.zeros(shape, bool)                # event awaiting recovery
        recov_R = np.full(shape, np.nan, np.float32)
        extreme = np.full(shape, np.nan, np.float32)
        event_doy = np.full(shape, np.nan, np.float32)
        cur_maxf = np.zeros(shape, np.float32)
        last_clear = np.full(shape, np.nan, np.float32)

        def teff():
            if ttype == "absolute":
                return np.full(shape, thr, np.float32)
            if ttype == "relative":
                return thr * np.abs(v_ref)
            return thr * mad

        def finalize(ok):
            """Count the confirmed descents in mask `ok` (magnitude already met)."""
            mag = v_ref - trough
            prior = ok & is_open
            n_interrupted[prior] += 1.0
            sum_maxf[prior] += np.clip(cur_maxf[prior], 0.0, 1.0)
            n_events[ok] += 1.0
            sum_mag[ok] += mag[ok]
            max_mag[ok] = np.maximum(max_mag[ok], mag[ok])
            fresh = ok & (first_doy == 0)
            first_doy[fresh] = trough_doy[fresh]
            last_doy[ok] = trough_doy[ok]
            is_open[ok] = True
            # recovery is measured toward the pre-event peak (observed) or
            # toward the expected level = anomaly 0 (reference); the trough is
            # taken in the matching recovery space.
            recov_R[ok] = 0.0 if baseline == "reference" else v_ref[ok]
            extreme[ok] = rec_trough[ok]
            event_doy[ok] = trough_doy[ok]

        def abrupt(mask):
            if max_event_days is None:
                return mask
            return mask & ((trough_doy - ref_doy) <= max_event_days)

        n = len(records)
        for idx, (name, doy) in enumerate(records):
            x = read_block(name)
            clear = np.isfinite(x)
            v = (sign * x).astype(np.float32)
            # recovery space: raw values (observed) or anomaly vs the
            # climatology (reference). Detection always uses raw v.
            if baseline == "reference":
                rec_v = v - sign * read_ref(doy)
            else:
                rec_v = v

            active = clear.copy()
            if report_progress:
                gs.percent(idx + 1, n, 1)
            if not active.any():
                continue
            ever_valid[active] = True

            gap = doy - last_clear
            broken = active & np.isfinite(last_clear) & (gap > max_gap)

            # continuity broken by a long gap: finalize, mark incomplete, reset
            if broken.any():
                bd = abrupt(broken & in_desc & ((v_ref - trough) >= teff() - eps))
                finalize(bd)
                n_incomplete[bd] += 1.0
                n_incomplete[broken & is_open & ~bd] += 1.0
                in_desc[broken] = False
                is_open[broken] = False
                v_ref[broken] = v[broken]
                ref_doy[broken] = doy
                trough[broken] = np.nan

            c = active & ~broken

            # pixels in a descent
            cd = c & in_desc
            if cd.any():
                newlow = cd & (v < trough)
                trough[newlow] = v[newlow]
                trough_doy[newlow] = doy
                rec_trough[newlow] = rec_v[newlow]
                turn_tol = turn_frac * (v_ref - trough)
                turnup = cd & (v > trough + turn_tol)
                if turnup.any():
                    good = abrupt(turnup & ((v_ref - trough) >= teff() - eps))
                    finalize(good)
                    # this turn-up sample is the first recovery observation
                    with np.errstate(invalid="ignore", divide="ignore"):
                        f = (rec_v - extreme) / (recov_R - extreme)
                    just = good
                    cur_maxf[just] = np.clip(f[just], 0.0, 1.0)
                    rec = just & (f >= recovery_target)
                    n_recovered[rec] += 1.0
                    sum_recdays[rec] += doy - event_doy[rec]
                    is_open[rec] = False
                    # start fresh peak tracking from the turn-up value
                    v_ref[good] = v[good]
                    ref_doy[good] = doy
                    # sub-threshold dip that recovered: discard, keep the peak
                    bad = turnup & ~good
                    v_ref[bad] = np.fmax(v_ref[bad], v[bad])
                    in_desc[turnup] = False

            # pixels not in a descent: recovery, peak tracking, new onset
            co = c & ~in_desc
            if co.any():
                openrec = co & is_open
                with np.errstate(invalid="ignore", divide="ignore"):
                    f = (rec_v - extreme) / (recov_R - extreme)
                cur_maxf[openrec] = np.maximum(cur_maxf[openrec], f[openrec])
                rec = openrec & (f >= recovery_target)
                n_recovered[rec] += 1.0
                sum_recdays[rec] += doy - event_doy[rec]
                is_open[rec] = False
                newpeak = co & (~np.isfinite(v_ref) | (v > v_ref))
                v_ref[newpeak] = v[newpeak]
                ref_doy[newpeak] = doy
                start = co & np.isfinite(v_ref) & (v < v_ref - eps)
                in_desc[start] = True
                trough[start] = v[start]
                trough_doy[start] = doy
                rec_trough[start] = rec_v[start]

            last_clear[active] = doy

        # end of series: a descent still open is a confirmed-but-incomplete
        # event; every other event still awaiting recovery is also incomplete.
        ok = abrupt(in_desc & ((v_ref - trough) >= teff() - eps))
        finalize(ok)
        n_incomplete[ok] += 1.0
        n_incomplete[is_open & ~ok] += 1.0

        with np.errstate(invalid="ignore", divide="ignore"):
            mean_mag = np.where(n_events > 0, sum_mag / n_events, np.nan)
            frac_rec = np.where(n_events > 0, n_recovered / n_events, np.nan)
            mean_recdays = np.where(
                n_recovered > 0, sum_recdays / n_recovered, np.nan
            )
            mean_pctrest = np.where(
                n_interrupted > 0, 100.0 * sum_maxf / n_interrupted, np.nan
            )

        results = {
            "count": n_events,
            "first_doy": np.where(n_events > 0, first_doy, np.nan),
            "last_doy": np.where(n_events > 0, last_doy, np.nan),
            "mean_magnitude": mean_mag,
            "max_magnitude": np.where(n_events > 0, max_mag, np.nan),
            "n_recovered": n_recovered,
            "frac_recovered": frac_rec,
            "mean_recovery_days": mean_recdays,
            "mean_percent_restored": mean_pctrest,
            "n_incomplete": n_incomplete,
        }

        # optional gap diagnostics (in-season observations)
        if flags["g"]:
            prev = np.full(shape, np.nan, np.float32)
            n_obs = np.zeros(shape, np.float32)
            sum_gap = np.zeros(shape, np.float32)
            max_gapo = np.zeros(shape, np.float32)
            for name, doy in records:
                x = read_block(name)
                valid = np.isfinite(x)
                has_prev = valid & np.isfinite(prev)
                g = doy - prev
                sum_gap[has_prev] += g[has_prev]
                max_gapo[has_prev] = np.maximum(max_gapo[has_prev], g[has_prev])
                n_obs[valid] += 1.0
                prev[valid] = doy
            with np.errstate(invalid="ignore", divide="ignore"):
                mean_gap = np.where(n_obs > 1, sum_gap / (n_obs - 1), np.nan)
            results["n_obs"] = n_obs
            results["mean_gap"] = np.where(n_obs > 1, mean_gap, np.nan)
            results["max_gap_obs"] = np.where(n_obs > 1, max_gapo, np.nan)

        return results, ever_valid

    # Integer count and day-of-year outputs are written as CELL; the continuous
    # magnitudes, fractions, gaps and recovery days stay DCELL.
    base_suffixes = [
        "count", "first_doy", "last_doy", "mean_magnitude", "max_magnitude",
        "n_recovered", "frac_recovered", "mean_recovery_days",
        "mean_percent_restored", "n_incomplete",
    ]
    gap_suffixes = ["n_obs", "mean_gap", "max_gap_obs"]
    cell_outputs = {"count", "n_recovered", "n_incomplete", "n_obs"}
    doy_outputs = {"first_doy", "last_doy"}
    cell_sentinel = -2147483647  # a real CELL value standing in for NULL
    suffixes = base_suffixes + (gap_suffixes if flags["g"] else [])

    def is_cell(suffix):
        return suffix in cell_outputs or suffix in doy_outputs

    def doy_store(coord, origin):
        """Turn a per-cell 'days since origin' array into stored values + labels.

        The detection kernel records event times as days since the group origin
        (the cycle start, or the first observation for groupby=none). For output
        this is converted to the calendar day-of-year (1-366) in groupby=year, or
        kept as days since the first observation in groupby=none. The event's
        calendar date is returned as a {stored_value: 'YYYY-MM-DD'} mapping so the
        real date can be attached as the category label. NaN cells stay NaN.
        """
        stored = np.full(coord.shape, np.nan, np.float64)
        labels = {}
        m = np.isfinite(coord)
        if m.any():
            days = coord[m].astype(np.int64)
            base = np.datetime64(origin.date())
            uniq = np.unique(days)
            udates = base + uniq.astype("timedelta64[D]")
            if groupby == "none":
                uvals = uniq
            else:
                uyears = udates.astype("datetime64[Y]")
                uvals = (
                    (udates - uyears).astype("timedelta64[D]").astype(np.int64) + 1
                )
            stored[m] = uvals[np.searchsorted(uniq, days)]
            for v, d in zip(uvals.tolist(), udates.tolist()):
                labels[int(v)] = d.isoformat()
        return stored, labels

    def write_date_labels(mapname, labels):
        """Attach 'YYYY-MM-DD' calendar dates as the category labels of values."""
        if not labels:
            return
        rules = "\n".join(f"{v}\t{d}" for v, d in sorted(labels.items()))
        gs.write_command(
            "r.category", map=mapname, rules="-", separator="tab",
            stdin=rules + "\n",
        )

    def run_year_parcel(records, origin, name_of):
        """Detect once per parcel (whole maps) and write via garray."""

        def read_block(mapid):
            return parcel_median(read_full(mapid))

        ref_state = {"name": None, "arr": None}

        def read_ref(doy, st=ref_state):
            name = nearest_ref(doy)
            if st["name"] != name:
                st["name"] = name
                st["arr"] = parcel_median(read_full(name))
            return st["arr"]

        results, ever_valid = detect_block(
            records, (n_parcels,), read_block, read_ref, True
        )

        def to_2d(arr):
            vals = np.where(ever_valid, arr, np.nan)
            out2d = np.full(label_idx.shape, np.nan, np.float64)
            sel = label_idx >= 0
            out2d[sel] = vals[label_idx[sel]]
            return out2d

        written = []
        for suffix in suffixes:
            mapname = name_of(suffix)
            data = to_2d(results[suffix])
            labels = None
            if suffix in doy_outputs:
                data, labels = doy_store(data, origin)
            if is_cell(suffix):
                valid = np.isfinite(data)
                cell = np.where(valid, np.rint(data), cell_sentinel).astype(np.int32)
                g = garray.array(dtype=np.int32)
                g[...] = cell
                g.write(mapname=mapname, null=cell_sentinel,
                        overwrite=gs.overwrite())
                if labels:
                    write_date_labels(mapname, labels)
            else:
                g = garray.array()
                g[...] = data
                g.write(mapname=mapname, overwrite=gs.overwrite())
            written.append((suffix, mapname))
        return written

    def strip_height(n_maps):
        """Rows per strip that keep the working arrays within the memory budget."""
        state_arrays = 50  # accumulators + per-cell state + temporaries, margin
        per_row = ncols * 4 * (state_arrays + (n_maps if ttype == "mad" else 1))
        budget = max(memory, 1) * 1024 * 1024
        return max(1, min(nrows, int(budget / max(per_row, 1))))

    def run_year_pixels(records, origin, name_of):
        """Detect per pixel, streaming the region in horizontal row strips."""
        strip = strip_height(len(records))
        writers = {}
        for suffix in suffixes:
            w = RasterRow(name_of(suffix))
            w.open("w", mtype="CELL" if is_cell(suffix) else "DCELL",
                   overwrite=gs.overwrite())
            writers[suffix] = w
        doy_labels = {s: {} for s in doy_outputs if s in suffixes}
        strips = list(range(0, nrows, strip))
        for si, r0 in enumerate(strips):
            r1 = min(r0 + strip, nrows)

            def read_block(mapid, r0=r0, r1=r1):
                return read_strip(mapid, r0, r1)

            ref_state = {"name": None, "arr": None}

            def read_ref(doy, r0=r0, r1=r1, st=ref_state):
                name = nearest_ref(doy)
                if st["name"] != name:
                    st["name"] = name
                    st["arr"] = read_strip(name, r0, r1)
                return st["arr"]

            results, ever_valid = detect_block(
                records, (r1 - r0, ncols), read_block, read_ref, False
            )
            for suffix in suffixes:
                w = writers[suffix]
                data = np.where(ever_valid, results[suffix], np.nan)
                if is_cell(suffix):
                    if suffix in doy_labels:
                        data, lbls = doy_store(data, origin)
                        doy_labels[suffix].update(lbls)
                    valid = np.isfinite(data)
                    cell = np.where(valid, np.rint(data), cell_sentinel)
                    cell = cell.astype(np.int32)
                    for i in range(r1 - r0):
                        buf = Buffer((ncols,), mtype="CELL")
                        buf[:] = cell[i]
                        w.put_row(buf)
                else:
                    data = data.astype(np.float64)
                    for i in range(r1 - r0):
                        buf = Buffer((ncols,), mtype="DCELL")
                        buf[:] = data[i]
                        w.put_row(buf)
            gs.percent(si + 1, len(strips), 1)
        for w in writers.values():
            w.close()
        close_row_handles()
        written = []
        for suffix in suffixes:
            mapname = name_of(suffix)
            if is_cell(suffix):
                gs.run_command("r.null", map=mapname, setnull=cell_sentinel,
                               quiet=True)
            if suffix in doy_labels:
                write_date_labels(mapname, doy_labels[suffix])
            written.append((suffix, mapname))
        return written

    # Group the observations into the cycles to analyze. With groupby=year each
    # cycle is a 12-month period starting on year_start (the calendar year by
    # default); with groupby=none the whole series is one group. Within a group
    # the time coordinate is days since the group origin, so it stays monotonic
    # even when a cycle straddles the calendar-year boundary. season_start and
    # season_end drop out-of-window observations up front, by calendar
    # day-of-year, which is equivalent to skipping them during detection.
    def in_season(dt):
        cd = _doy(dt)
        if season_start is not None and cd < season_start:
            return False
        if season_end is not None and cd > season_end:
            return False
        return True

    groups = {}  # key -> (origin_datetime, [(map_id, coord_days), ...])
    if groupby == "none":
        first = rows[0][1]
        origin = datetime(first.year, first.month, first.day)
        recs = [
            (name, (dt - origin).days) for name, dt in rows if in_season(dt)
        ]
        if len(recs) >= 2:
            groups[None] = (origin, recs)
    else:
        for name, dt in rows:
            if not in_season(dt):
                continue
            anchor = cycle_anchor(dt, ys_month, ys_day)
            groups.setdefault(anchor.year, (anchor, []))[1].append(
                (name, (dt - anchor).days)
            )
        if year is not None:
            groups = {year: groups[year]} if year in groups else {}

    keys = sorted(k for k in groups if k is not None) or list(groups)
    multi_cycle = len(keys) > 1
    run_cycle = run_year_parcel if parcel_mode else run_year_pixels

    registry = {}  # output suffix -> [(mapname, origin), ...]
    for k, key in enumerate(keys):
        origin, recs = groups[key]
        if len(recs) < 2:
            gs.warning(
                _("Cycle {} has fewer than two in-season maps; skipped.").format(key)
            )
            continue
        if multi_cycle:
            gs.message(
                _("Detecting events for cycle {} ({} of {}).").format(
                    key, k + 1, len(keys)
                )
            )

        def name_of(suffix, key=key):
            return f"{out}_{suffix}_{key}" if multi_cycle else f"{out}_{suffix}"

        for suffix, mapname in run_cycle(recs, origin, name_of):
            registry.setdefault(suffix, []).append((mapname, origin))

    if not registry:
        gs.fatal(_("No cycle had at least two in-season maps to detect events."))

    if multi_cycle:
        gs.message(_("Registering per-cycle rasters into space-time datasets."))
        for suffix, entries in registry.items():
            stname = f"{out}_{suffix}"
            tools.t_create(
                type="strds", temporaltype="absolute", output=stname,
                title=f"{out} {suffix}",
                description=f"t.rast.event {suffix}, one raster per cycle",
                overwrite=gs.overwrite(),
            )
            reg_file = gs.tempfile()
            with open(reg_file, "w") as fh:
                for mapname, origin in entries:
                    fh.write(f"{mapname}|{origin.date()}\n")
            tools.t_register(
                input=stname, file=reg_file, overwrite=gs.overwrite()
            )
        gs.message(
            _("Wrote per-cycle rasters and space-time datasets with prefix"
              " '{}'.").format(out)
        )
    else:
        gs.message(_("Wrote summary rasters with prefix '{}'.").format(out))


if __name__ == "__main__":
    main()

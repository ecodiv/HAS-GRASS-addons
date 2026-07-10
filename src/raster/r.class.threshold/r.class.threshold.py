#!/usr/bin/env python3
##############################################################################
# MODULE:    r.class.threshold
#
# AUTHOR(S): Paulo van Breugel
#
# PURPOSE:   Select thresholds for converting a continuous raster (e.g. NDVI)
#            into two classes, evaluated against a set of reference points
#            whose attribute table holds the observed class. One threshold is
#            selected per optimisation criterion. It furthermore produces a
#            sensitivity/specificity-vs-threshold plot, a ROC/AUC plot,
#            a raster-value boxplot by observed class, a table of selected
#            thresholds (one per optimisation criterion) as plain text,
#            CSV or JSON, and optionally a classified binary raster.
#
# COPYRIGHT: (C) 2026 by Paulo van Breugel and the GRASS Development Team
#
#            This program is free software under the GNU General Public
#            License (>=v2). Read the file COPYING that comes with GRASS
#            for details.
##############################################################################

# %module
# % description: Selects thresholds for separating a continuous raster into two classes.
# % keyword: raster
# % keyword: threshold
# % keyword: classification
# % keyword: accuracy
# % keyword: ROC
# % keyword: AUC
# % keyword: validation
# %end

# %option G_OPT_R_INPUT
# % key: raster
# % label: Input raster
# % description: Name of input raster with continuous values
# % guisection: Input
# %end

# %option G_OPT_V_INPUT
# % key: map
# % label: Reference points
# % description: Point vector with an attribute table holding the observed class
# % guisection: Input
# %end

# %option G_OPT_DB_COLUMN
# % key: column
# % label: Class column
# % description: Attribute column holding the observed class
# % required: yes
# % guisection: Input
# %end

# %option
# % key: positive_value
# % type: string
# % required: no
# % answer: 1
# % label: Positive (target) value
# % description: Value in the class column that denotes the target class. Default is 1.
# % guisection: Input
# %end

# %option
# % key: negative_value
# % type: string
# % required: no
# % answer: 0
# % label: Negative (non-target) value
# % description: Value in the class column that denotes the non-target class. Default is 0.
# % guisection: Input
# %end

# %option G_OPT_V_FIELD
# % key: layer
# % label: Layer
# % guisection: Input
# %end

# %option G_OPT_F_OUTPUT
# % key: output
# % required: no
# % label: Threshold table file
# % description: File for the selected-threshold table. Default is standard output.
# % guisection: Output
# %end

# %option
# % key: format
# % type: string
# % required: no
# % answer: plain
# % options: plain,csv,json
# % label: Table format
# % description: Output format of the threshold table
# % guisection: Output
# %end

# %option G_OPT_R_OUTPUT
# % key: classified_output
# % required: no
# % label: Classified raster
# % description: Optional binary 0/1 raster, produced by applying the threshold of the criterion set by apply_criterion
# % guisection: Output
# %end

# %option
# % key: apply_criterion
# % type: string
# % required: no
# % answer: max_youden_j
# % options: max_youden_j,equal_sens_spec,closest_topleft,max_accuracy,max_f1,max_kappa
# % label: Criterion for classified raster
# % description: Criterion whose threshold is applied when classified_output is requested
# % guisection: Output
# %end

# %option
# % key: plots
# % type: string
# % required: no
# % multiple: yes
# % options: threshold,roc,boxplot
# % label: Plots to display interactively
# % description: Plots to show in a window. Requires an interactive backend and display. If none are given, no plot is shown interactively. File output is controlled separately by plot=, roc_plot= and boxplot=.
# % guisection: Plots
# %end

# %option
# % key: criterion
# % type: string
# % required: no
# % multiple: yes
# % answer: max_youden_j
# % options: all,max_youden_j,equal_sens_spec,closest_topleft,max_accuracy,max_f1,max_kappa
# % label: Reference-line criteria
# % description: Criteria whose thresholds are drawn as reference lines on the threshold plot and boxplot. Use 'all' for every criterion. This does NOT limit the output table, which always lists every criterion. Criteria sharing a threshold are merged in the legend.
# % guisection: Plots
# %end

# %option G_OPT_F_OUTPUT
# % key: plot
# % required: no
# % label: Threshold plot file
# % description: File for the sensitivity/specificity vs threshold plot. The extension sets the type. If omitted, no file is written.
# % guisection: Plots
# %end

# %option G_OPT_F_OUTPUT
# % key: roc_plot
# % required: no
# % label: ROC plot file
# % description: File for the ROC plot. The extension sets the type. If omitted, no file is written.
# % guisection: Plots
# %end

# %option G_OPT_F_OUTPUT
# % key: boxplot
# % required: no
# % label: Boxplot file
# % description: File for the boxplot. The extension sets the type. If omitted, no file is written.
# % guisection: Plots
# %end

# %option
# % key: range
# % type: string
# % required: no
# % answer: raster
# % options: raster,sample
# % label: Threshold plot x-axis range
# % description: 'raster' spans the full raster min/max; 'sample' spans only the range of the sampled reference values (useful when the raster has extreme values not represented in the reference points)
# % guisection: Plots
# %end

# %option
# % key: steps
# % type: integer
# % required: no
# % answer: 100
# % options: 2-100000
# % label: Threshold plot resolution
# % description: Number of steps drawn on the sensitivity/specificity plot. Does not affect the threshold table, ROC curve or AUC, which use the empirical value breakpoints.
# % guisection: Plots
# %end

# %option
# % key: backend
# % type: string
# % required: no
# % answer: default
# % options: default,no_plot,Agg,WXAgg,QtAgg,TkAgg,GTK3Agg,GTK4Agg,MacOSX
# % label: Matplotlib backend
# % description: Backend used for plotting. 'default' lets matplotlib auto-select. 'no_plot' skips plotting entirely (matplotlib not imported; only the threshold table is produced - useful for automation). 'Agg' is non-interactive (savefig only). The others are interactive and need the matching GUI toolkit installed (WXAgg=wxPython, QtAgg=PyQt/PySide, TkAgg=Tkinter, GTK*Agg=GTK, MacOSX=native macOS). Falls back to Agg with a warning if the chosen backend cannot be initialised.
# % guisection: Settings
# %end

# %option
# % key: tie_tolerance
# % type: double
# % required: no
# % answer: 0.0
# % label: Tie tolerance for optima
# % description: Two scores are treated as tied optima when they differ by no more than this tolerance (relative + absolute, as in numpy.isclose). The default 0 requires exact equality, so a one-observation difference is not silently merged.
# % guisection: Settings
# %end

# %flag
# % key: r
# % label: Reverse rule (class 1 at or below the threshold)
# % description: Use when low raster values indicate the target class
# %end

import atexit
import json
import math
import os
import sys

import grass.script as gs

# GRASS installs the gettext _() helper into builtins at runtime.
# Helps to avoid linter errors in e.g., Positron
try:
    _
except NameError:

    def _(string):
        return string


# Module-level constants
# Criteria reported in the table, one row each. The True Skill Statistic (TSS)
# and "maximum balanced accuracy" are mathematical the same as max_youden_j -
# all three maximise sensitivity + specificity - 1. So they are not reported
# as separate rows
CRITERIA = (
    "max_youden_j",
    "equal_sens_spec",
    "closest_topleft",
    "max_accuracy",
    "max_f1",
    "max_kappa",
)

# Alternative names for max_youden_j.
YOUDEN_ALIASES = ("max_youden_j", "max_tss", "max_balanced_accuracy")

TABLE_FIELDS = (
    "criterion",
    "threshold",
    "threshold_lo",
    "threshold_hi",
    "tp",
    "fp",
    "fn",
    "tn",
    "sensitivity",
    "specificity",
    "accuracy",
    "balanced_accuracy",
    "precision",
    "recall",
    "f1",
    "youden_j",
    "kappa",
)

# Non-interactive matplotlib backends.
NON_INTERACTIVE_BACKENDS = {"agg", "cairo", "pdf", "pgf", "ps", "svg", "template"}

TMP_VECTOR = None


def cleanup():
    """Remove the temporary vector copy."""
    if TMP_VECTOR:
        try:
            from grass.tools import Tools

            Tools().g_remove(type="vector", name=TMP_VECTOR, flags="f", quiet=True)
        except Exception as exc:  # noqa: BLE001 - cleanup must not raise
            gs.debug(f"cleanup failed to remove <{TMP_VECTOR}>: {exc}")


def _unique_column_name(tools, vector, layer):
    """Return a temporary column name not already present on the given layer."""
    try:
        existing = set(gs.vector_columns(vector, layer).keys())
    except Exception:  # noqa: BLE001 - fall back to a best-effort name
        existing = set()
    existing_lower = {c.lower() for c in existing}
    for _attempt in range(100):
        name = "rct_" + gs.tempname(8)
        if name.lower() not in existing_lower:
            return name
    gs.fatal(_("Could not generate a unique temporary column name"))


def sample_points(tools, raster, points, column, layer, positive_value, negative_value):
    """Sample the raster at the reference points.

    Returns two lists: observed classes (int 0/1) and raster values (float).
    Points outside the raster (NULL) or whose class column does not match
    positive_value or negative_value are dropped with a warning.

    Class parsing is strict: a value is class 1 only if it equals
    positive_value and class 0 only if it equals negative_value.
    Numeric comparison is used when both sides parse as finite floats,
    otherwise a case-sensitive string comparison is used.
    """
    global TMP_VECTOR
    TMP_VECTOR = f"tmp_rclassthr_{gs.tempname(12)}"

    # Work on a copy so the user's vector is never modified.
    tools.g_copy(vector=(points, TMP_VECTOR))

    rast_col = _unique_column_name(tools, TMP_VECTOR, layer)
    tools.v_db_addcolumn(
        map=TMP_VECTOR,
        layer=layer,
        columns=f"{rast_col} double precision",
    )
    tools.v_what_rast(
        map=TMP_VECTOR,
        layer=layer,
        raster=raster,
        column=rast_col,
    )

    # JSON output gives native types: NULLs come back as None.
    result = tools.v_db_select(
        map=TMP_VECTOR,
        columns=f"{column},{rast_col}",
        format="json",
        layer=layer,
    )
    try:
        records = result["records"]
    except (KeyError, TypeError):
        gs.fatal(_("Could not read sampled values from <{}>").format(points))

    def as_float(token):
        try:
            f = float(token)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    pos_f = as_float(positive_value)
    neg_f = as_float(negative_value)
    pos_s = str(positive_value)
    neg_s = str(negative_value)
    if pos_s == neg_s or (pos_f is not None and neg_f is not None and pos_f == neg_f):
        gs.fatal(
            _("positive_value and negative_value must differ (both are '{}')").format(
                pos_s
            )
        )

    def classify(obs):
        """Return 1, 0, or None (unrecognised) for an observed token."""
        obs_f = as_float(obs)
        if obs_f is not None and pos_f is not None and neg_f is not None:
            if obs_f == pos_f:
                return 1
            if obs_f == neg_f:
                return 0
            return None
        # Fall back to exact string comparison for non-numeric class codes.
        obs_s = str(obs)
        if obs_s == pos_s:
            return 1
        if obs_s == neg_s:
            return 0
        return None

    observed, values = [], []
    skipped = 0
    for rec in records:
        obs = rec.get(column)
        val = rec.get(rast_col)
        if obs is None or val is None:
            skipped += 1
            continue
        val_f = as_float(val)
        if val_f is None:
            skipped += 1
            continue
        cls = classify(obs)
        if cls is None:
            skipped += 1
            continue
        observed.append(cls)
        values.append(val_f)

    if skipped:
        gs.warning(
            _(
                "{} point(s) skipped (NULL raster value, or class not equal to "
                "positive_value '{}' / negative_value '{}')"
            ).format(skipped, pos_s, neg_s)
        )
    return observed, values


def empirical_thresholds(values):
    """Candidate thresholds at the empirical breakpoints of the sampled values."""
    import numpy as np

    u = np.unique(np.asarray(values, dtype=float))
    if u.size == 1:
        eps = max(abs(u[0]) * 1e-9, 1e-9)
        return np.array([u[0] - eps, u[0] + eps])
    mids = (u[:-1] + u[1:]) / 2.0
    eps_low = max(abs(u[0]) * 1e-9, 1e-9)
    eps_high = max(abs(u[-1]) * 1e-9, 1e-9)
    return np.concatenate(([u[0] - eps_low], mids, [u[-1] + eps_high]))


def confusion(thresholds, values, observed, reverse):
    """Confusion-matrix counts for every threshold.

    Returns TP, FP, FN, TN as integer arrays, one entry per threshold.
    Without reverse, a point is predicted positive when value >= threshold;
    with reverse set, when value <= threshold.

    Implemented with np.searchsorted on the sorted positive/negative value
    arrays to reduce memory use (O(n_points + n_thresholds)).
    """
    import numpy as np

    thresholds = np.asarray(thresholds, dtype=float)
    values = np.asarray(values, dtype=float)
    observed = np.asarray(observed, dtype=int)

    pos_values = np.sort(values[observed == 1])
    neg_values = np.sort(values[observed == 0])
    n_pos = pos_values.size
    n_neg = neg_values.size

    if reverse:
        # Predicted positive when value <= threshold => count values <= t.
        tp = np.searchsorted(pos_values, thresholds, side="right")
        fp = np.searchsorted(neg_values, thresholds, side="right")
    else:
        # Predicted positive when value >= threshold => count values >= t.
        tp = n_pos - np.searchsorted(pos_values, thresholds, side="left")
        fp = n_neg - np.searchsorted(neg_values, thresholds, side="left")

    fn = n_pos - tp
    tn = n_neg - fp
    return (
        tp.astype(int),
        fp.astype(int),
        fn.astype(int),
        tn.astype(int),
    )


def metrics(tp, fp, fn, tn):
    """Derive rate metrics from confusion-matrix arrays.

    Returns sensitivity, specificity, accuracy, balanced_accuracy, precision,
    f1, youden_j and kappa. Recall is identical to sensitivity (And TPR) and
    is not returned separately.
    """
    import numpy as np

    tp = tp.astype(float)
    fp = fp.astype(float)
    fn = fn.astype(float)
    tn = tn.astype(float)
    total = tp + fp + fn + tn

    with np.errstate(divide="ignore", invalid="ignore"):
        sens = np.where((tp + fn) > 0, tp / (tp + fn), np.nan)
        spec = np.where((tn + fp) > 0, tn / (tn + fp), np.nan)
        acc = np.where(total > 0, (tp + tn) / total, np.nan)
        bal_acc = (sens + spec) / 2.0
        prec = np.where((tp + fp) > 0, tp / (tp + fp), np.nan)
        f1 = np.where((2 * tp + fp + fn) > 0, 2 * tp / (2 * tp + fp + fn), np.nan)
        youden = sens + spec - 1.0
        pe = np.where(
            total > 0,
            ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (total * total),
            np.nan,
        )
        kappa = np.where((1 - pe) != 0, (acc - pe) / (1 - pe), np.nan)
    return sens, spec, acc, bal_acc, prec, f1, youden, kappa


def roc_auc(values, observed, reverse):
    """Empirical ROC curve and AUC.

    The curve (for plotting) is built by placing thresholds between
    consecutive unique raster values, so it reflects the data rather than the
    plotting grid. The AUC is computed exactly from the rank-sum
    (Mann-Whitney) statistic, which is tie-aware. With reverse, ranks are
    based on negated raster values so larger scores still indicate the positive
    class. Returns sorted FPR, sorted TPR and the AUC.
    """
    import numpy as np

    values = np.asarray(values, dtype=float)
    observed = np.asarray(observed, dtype=int)

    # ROC curve points for plotting.
    uval = np.unique(values)
    if uval.size == 1:
        thr = np.array([uval[0] - 1.0, uval[0] + 1.0])
    else:
        mids = (uval[:-1] + uval[1:]) / 2.0
        thr = np.concatenate(([uval[0] - 1.0], mids, [uval[-1] + 1.0]))
    tp, fp, fn, tn = confusion(thr, values, observed, reverse)
    sens, spec = metrics(tp, fp, fn, tn)[:2]
    fpr, tpr = 1.0 - spec, sens
    # Lexicographic sort (FPR then TPR) keeps the plotted staircase monotone
    # when several thresholds share an FPR. Does not affect the AUC, which is
    # computed independently from ranks below.
    order = np.lexsort((tpr, fpr))
    fpr_s = np.concatenate(([0.0], fpr[order], [1.0]))
    tpr_s = np.concatenate(([0.0], tpr[order], [1.0]))

    # Exact, tie-aware AUC via the rank-sum statistic.
    scores = -values if reverse else values  # higher score => more "positive"
    sorder = np.argsort(scores, kind="mergesort")
    s_sorted = scores[sorder]
    ranks = np.empty(scores.size, dtype=float)
    avg_ranks = np.empty(scores.size, dtype=float)
    i, m = 0, scores.size
    while i < m:
        j = i
        while j + 1 < m and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        avg_ranks[i : j + 1] = (i + j) / 2.0 + 1.0  # 1-based average rank
        i = j + 1
    ranks[sorder] = avg_ranks
    pos = observed == 1
    n1 = int(pos.sum())
    n0 = int(observed.size - n1)
    if n1 == 0 or n0 == 0:
        auc = float("nan")
    else:
        rank_sum_pos = float(ranks[pos].sum())
        auc = (rank_sum_pos - n1 * (n1 + 1) / 2.0) / (n1 * n0)
    return fpr_s, tpr_s, auc


def tied_runs(indices):
    """Split an array of sorted indices into contiguous runs.

    [0, 1, 2, 5, 6] -> [array([0, 1, 2]), array([5, 6])]
    """
    import numpy as np

    indices = np.asarray(indices)
    if indices.size == 0:
        return []
    splits = np.where(np.diff(indices) > 1)[0] + 1
    return np.split(indices, splits)


def argbest(thr, score, mode, tie_tolerance):
    """Locate the optimal plateau of a score array.

    thr are the threshold values (used to order ties and to pick a
    representative), score is the per-threshold criterion, mode is
    'max' or 'min'. tie_tolerance is the relative+absolute tolerance for
    treating scores as tied (0 means exact equality).

    Returns (rep_index, lo_index, hi_index) where lo/hi bound a single
    contiguous run of tied empirical candidates (ordered by threshold) and rep
    is the candidate within that run closest to its midpoint. NaNs are ignored.
    The midpoint is never taken across a gap between disjoint optima.

    rep is an actual candidate, not the interpolated midpoint, because callers
    report thr[rep] as the threshold alongside the counts and metrics taken at
    that same index. For an even-length run, np.argmin resolves the two equally
    central candidates to the lower one; a threshold nudged low is the safer
    default because it errs toward predicting the positive class.
    """
    import numpy as np

    thr = np.asarray(thr, dtype=float)
    score = np.asarray(score, dtype=float)
    finite = np.isfinite(score)
    if not finite.any():
        return 0, 0, 0

    best = np.nanmax(score) if mode == "max" else np.nanmin(score)

    if tie_tolerance > 0:
        tied = np.where(
            finite & np.isclose(score, best, rtol=tie_tolerance, atol=tie_tolerance)
        )[0]
    else:
        tied = np.where(finite & (score == best))[0]

    # Order tied indices by threshold value, then split into contiguous runs.
    tied = tied[np.argsort(thr[tied])]
    runs = tied_runs(tied)

    # Pick the longest contiguous plateau; break ties between equally long
    # plateaus by choosing the one whose mean threshold is most central.
    center = float(np.median(thr))
    run = min(runs, key=lambda r: (-len(r), abs(float(np.mean(thr[r])) - center)))

    lo_i, hi_i = int(run[0]), int(run[-1])
    mid_val = 0.5 * (thr[lo_i] + thr[hi_i])
    rep_i = int(run[np.argmin(np.abs(thr[run] - mid_val))])
    return rep_i, lo_i, hi_i


def best_candidates(thresholds, tp, fp, fn, tn, tie_tolerance):
    """Pick the optimal threshold per criterion from empirical breakpoints."""
    import numpy as np

    sens, spec, acc, bal_acc, prec, f1, youden, kappa = metrics(tp, fp, fn, tn)
    thr = np.asarray(thresholds, dtype=float)

    criteria = {
        "max_youden_j": (youden, "max"),
        "equal_sens_spec": (np.abs(sens - spec), "min"),
        "closest_topleft": ((1.0 - sens) ** 2 + (1.0 - spec) ** 2, "min"),
        "max_accuracy": (acc, "max"),
        "max_f1": (f1, "max"),
        "max_kappa": (kappa, "max"),
    }

    def clean(x):
        """Float, or None when NaN/None (-> JSON null / 'NA' in text)."""
        if x is None:
            return None
        x = float(x)
        return None if math.isnan(x) else x

    rows = []
    for name in CRITERIA:
        score, mode = criteria[name]
        i, lo, hi = argbest(thr, score, mode, tie_tolerance)
        rows.append(
            {
                "criterion": name,
                # Report the same empirical candidate used for the counts and
                # metrics below (index i).
                "threshold": float(thr[i]),
                "threshold_lo": float(thr[lo]),
                "threshold_hi": float(thr[hi]),
                "tp": int(tp[i]),
                "fp": int(fp[i]),
                "fn": int(fn[i]),
                "tn": int(tn[i]),
                "sensitivity": clean(sens[i]),
                "specificity": clean(spec[i]),
                "accuracy": clean(acc[i]),
                "balanced_accuracy": clean(bal_acc[i]),
                "precision": clean(prec[i]),
                "recall": clean(sens[i]),  # recall == sensitivity
                "f1": clean(f1[i]),
                "youden_j": clean(youden[i]),
                "kappa": clean(kappa[i]),
            }
        )
    return rows


def _fmt(value, field=None):
    """Format a value for the plain-text table.

    Thresholds keep high precision (they are the operationally meaningful
    numbers); rate metrics in [0, 1] are rounded to 4 significant digits for
    readability. The full-precision values are always available in CSV/JSON.
    """
    if value is None:
        return "NA"
    if isinstance(value, float):
        if math.isnan(value):
            return "NA"
        if field in ("threshold", "threshold_lo", "threshold_hi"):
            return "{:.12g}".format(value)
        return "{:.4g}".format(value)
    return str(value)


def write_table(rows, summary, fmt, output):
    """Write the selected-threshold table in the requested format.

    JSON and CSV carry full-precision numeric values; only the plain-text table
    applies display formatting.
    """
    fields = list(TABLE_FIELDS)

    try:
        if output in (None, "", "-"):
            out = sys.stdout
            close = False
        else:
            out = open(output, "w", newline="", encoding="utf-8")
            close = True
    except OSError as exc:
        gs.fatal(_("Unable to open output file <{}>: {}").format(output, exc))

    try:
        if fmt == "json":
            json.dump({"summary": summary, "thresholds": rows}, out, indent=2)
            out.write("\n")
        elif fmt == "csv":
            import csv

            writer = csv.writer(out)
            writer.writerow(fields)
            for row in rows:
                writer.writerow(
                    [
                        ""
                        if row.get(f) is None
                        or (isinstance(row.get(f), float) and math.isnan(row.get(f)))
                        else row.get(f)
                        for f in fields
                    ]
                )
        else:  # plain
            # Transposed layout: one row per field, one column per criterion.
            crit_names = [r["criterion"] for r in rows]
            label_w = max((len(f) for f in fields), default=0)
            col_cells = {
                r["criterion"]: {f: _fmt(r.get(f), f) for f in fields} for r in rows
            }
            # Column width = max over its own cells and its header (criterion).
            col_w = {
                name: max(
                    len(name), max((len(col_cells[name][f]) for f in fields), default=0)
                )
                for name in crit_names
            }
            # "criterion" is the field that names each column
            body_fields = [f for f in fields if f != "criterion"]

            header = (
                "field".ljust(label_w)
                + "  "
                + "  ".join(name.ljust(col_w[name]) for name in crit_names)
            )
            out.write(header + "\n")
            out.write("-" * len(header) + "\n")
            for f in body_fields:
                line = (
                    f.ljust(label_w)
                    + "  "
                    + "  ".join(
                        col_cells[name][f].ljust(col_w[name]) for name in crit_names
                    )
                )
                out.write(line + "\n")
    finally:
        if close:
            out.close()


def classify_raster(tools, raster, output, threshold, reverse):
    """Write a binary 0/1 raster by thresholding the input raster.

    Without reverse: 1 where value >= threshold, else 0.
    With reverse:    1 where value <= threshold, else 0.
    NULL cells stay NULL.
    """
    if threshold is None or (isinstance(threshold, float) and math.isnan(threshold)):
        gs.warning(
            _("Selected criterion has no defined threshold; <{}> not created").format(
                output
            )
        )
        return
    op = "<=" if reverse else ">="
    expr = (
        f"{output} = if(isnull({raster}), null(), "
        f"if({raster} {op} {float(threshold):.17g}, 1, 0))"
    )
    tools.r_mapcalc(expression=expr)
    gs.message(
        _("Classified raster <{}> created (class 1 where {} {} {:.12g})").format(
            output, raster, op, float(threshold)
        )
    )


# Plotting, split into helpers
def _activate_backend(matplotlib, backend_opt, save_mode, want_show):
    """Select the matplotlib backend without mutating os.environ.

    Honours an explicit backend choice (option or pre-set MPLBACKEND). With no
    explicit choice, picks Agg  when we are purely saving; otherwise leaves
    matplotlib's default selection alone so an interactive window can open.
    """
    explicit = ""
    if backend_opt not in ("default", "no_plot"):
        explicit = backend_opt
    elif os.environ.get("MPLBACKEND", "").strip():
        explicit = os.environ["MPLBACKEND"].strip()

    if explicit:
        try:
            matplotlib.use(explicit, force=True)
        except Exception as exc:  # noqa: BLE001
            gs.warning(
                _("Backend '{}' could not be activated ({}); using Agg instead").format(
                    explicit, exc
                )
            )
            matplotlib.use("Agg", force=True)
    elif not want_show and (save_mode or not os.environ.get("DISPLAY")):
        matplotlib.use("Agg", force=True)


def _merge_reference_thresholds(refs):
    """Merge reference (label, threshold) pairs that share a threshold value.

    Returns (merged, ref_colors): merged is a list of (labels, threshold) with
    distinct thresholds in first-seen order; ref_colors maps threshold -> color.
    """
    merged = []
    seen = {}
    for label, thr_val in refs:
        if thr_val is None or (isinstance(thr_val, float) and math.isnan(thr_val)):
            continue
        # Round only for grouping coincident lines, not for display.
        key = round(float(thr_val), 9)
        if key in seen:
            merged[seen[key]][0].append(label)
        else:
            seen[key] = len(merged)
            merged.append(([label], float(thr_val)))
    palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
    ]
    ref_colors = {
        thr_val: palette[i % len(palette)] for i, (_lbls, thr_val) in enumerate(merged)
    }
    return merged, ref_colors


def _stacked_legend_entries(ax, merged, ref_colors):
    """Draw the reference lines and build stacked legend handles/labels.

    Each merged group of coincident criteria becomes several legend rows: the
    first row carries the dashed line symbol and the first criterion name plus
    the shared threshold value; the remaining criteria are added as rows with a
    blank (invisible) handle so they line up underneath, e.g.

        --- max_youden_j (0.149)
            closest_topleft
            max_accuracy
            max_kappa

    Returns (handles, labels) ready to pass to ax.legend().
    """
    from matplotlib.lines import Line2D

    handles = []
    labels = []
    for crit_labels, thr_val in merged:
        # First row: the real line, first name + threshold value.
        line = ax.axvline(
            thr_val,
            color=ref_colors[thr_val],
            ls="--",
            lw=1.2,
        )
        handles.append(line)
        labels.append(f"{crit_labels[0]} ({thr_val:.4g})")
        # Remaining names: blank handle so only the text shows, indented under
        # the first name.
        for extra in crit_labels[1:]:
            handles.append(Line2D([], [], linestyle="none", marker="none"))
            labels.append(extra)
    return handles, labels


def _stacked_legend_entries_h(ax, merged, ref_colors):
    """Horizontal-line variant of :func:`_stacked_legend_entries` (axhline)."""
    from matplotlib.lines import Line2D

    handles = []
    labels = []
    for crit_labels, thr_val in merged:
        line = ax.axhline(
            thr_val,
            color=ref_colors[thr_val],
            ls="--",
            lw=1.2,
        )
        handles.append(line)
        labels.append(f"{crit_labels[0]} ({thr_val:.4g})")
        for extra in crit_labels[1:]:
            handles.append(Line2D([], [], linestyle="none", marker="none"))
            labels.append(extra)
    return handles, labels


def _rule_text(reverse):
    return (
        "class 1 if value <= threshold" if reverse else "class 1 if value >= threshold"
    )


def make_plots(
    matplotlib,
    plt,
    np,
    thresholds,
    tp,
    fp,
    fn,
    tn,
    fpr,
    tpr,
    auc,
    raster,
    values,
    observed,
    refs,
    reverse,
    plot,
    roc_plot,
    boxplot,
    show,
):
    """Build the sensitivity/specificity plot, ROC plot, and class boxplot.

    'show' is a list naming which figures to display interactively (any of
    'threshold', 'roc', 'boxplot'); an empty list shows nothing. Saving to a
    file is independent of ``show`` and controlled by plot/roc_plot/boxplot.
    """
    save_mode = bool(plot or roc_plot or boxplot)
    show = set(show or [])
    merged, ref_colors = _merge_reference_thresholds(refs)

    sens, spec = metrics(tp, fp, fn, tn)[:2]

    # Sensitivity / specificity vs threshold (dual y-axis).
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    color1, color2 = "#1f77b4", "#d62728"
    ax1.plot(thresholds, sens * 100, color=color1, lw=2)
    ax1.set_xlabel(f"Threshold ({raster})")
    ax1.set_ylabel("% correctly predicted 1 (sensitivity)", color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.set_ylim(0, 100)

    ax2 = ax1.twinx()
    ax2.plot(thresholds, spec * 100, color=color2, lw=2)
    ax2.set_ylabel("% correctly predicted 0 (specificity)", color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(0, 100)

    handles1, labels1 = _stacked_legend_entries(ax1, merged, ref_colors)
    if handles1:
        ax1.legend(
            handles1,
            labels1,
            loc="center left",
            fontsize=8,
            framealpha=0.9,
            handlelength=1.8,
            handletextpad=0.6,
        )
    fig1.tight_layout()

    # ROC / AUC.
    fig2, axr = plt.subplots(figsize=(6, 6))
    auc_label = "ROC (AUC = n/a)" if (auc != auc) else f"ROC (AUC = {auc:.3f})"
    axr.plot(fpr, tpr, color="#2ca02c", lw=2, label=auc_label)
    axr.plot([0, 1], [0, 1], ls="--", color="gray", lw=1, label="random")
    axr.set_xlabel("False positive rate (1 - specificity)")
    axr.set_ylabel("True positive rate (sensitivity)")
    axr.set_xlim(0, 1)
    axr.set_ylim(0, 1)
    axr.legend(loc="lower right")
    fig2.tight_layout()

    # Raster values by observed class.
    values_arr = np.asarray(values, dtype=float)
    observed_arr = np.asarray(observed, dtype=int)
    class0 = values_arr[observed_arr == 0]
    class1 = values_arr[observed_arr == 1]

    fig3, axb = plt.subplots(figsize=(6, 5))
    axb.boxplot([class0, class1], notch=True, showfliers=True, patch_artist=True)
    # Set tick labels separately to remain compatible with matplotlib >= 3.11,
    # where the `labels=` parameter of boxplot() is removed.
    axb.set_xticklabels(["0", "1"])

    handles3, labels3 = _stacked_legend_entries_h(axb, merged, ref_colors)
    if handles3:
        axb.legend(
            handles3,
            labels3,
            loc="best",
            fontsize=8,
            framealpha=0.9,
            handlelength=1.8,
            handletextpad=0.6,
        )
    axb.set_xlabel("Observed class")
    axb.set_ylabel(f"Raster value ({raster})")
    axb.yaxis.grid(True)
    fig3.tight_layout()

    if plot:
        fig1.savefig(plot, dpi=150)
        gs.message(_("Sensitivity/specificity plot written to <{}>").format(plot))
    if roc_plot:
        fig2.savefig(roc_plot, dpi=150)
        gs.message(_("ROC plot written to <{}>").format(roc_plot))
    if boxplot:
        fig3.savefig(boxplot, dpi=150)
        gs.message(_("Boxplot written to <{}>").format(boxplot))

    # Interactive display is opt-in via plots=. Show only the requested figures
    # and close the rest so no unwanted windows appear.
    fig_by_name = {"threshold": fig1, "roc": fig2, "boxplot": fig3}
    is_interactive = matplotlib.get_backend().lower() not in NON_INTERACTIVE_BACKENDS
    if show and is_interactive:
        for name, fig in fig_by_name.items():
            if name not in show:
                plt.close(fig)
        plt.show()
    elif show and not is_interactive:
        gs.warning(
            _(
                "plots=%s requested interactive display, but matplotlib is "
                "using the non-interactive '%s' backend - nothing will be "
                "shown. Choose an interactive backend= (e.g. QtAgg, TkAgg), "
                "or save with plot=, roc_plot= and/or boxplot=."
            )
            % (",".join(sorted(show)), matplotlib.get_backend())
        )


def run_plots(
    backend_opt, *plot_args_without_mpl, reverse, plot, roc_plot, boxplot, show
):
    """Import matplotlib lazily, configure the backend, and draw the plots."""
    save_mode = bool(plot or roc_plot or boxplot)
    want_show = bool(show)
    # Skip matplotlib entirely when there is nothing to save and nothing to
    # display - building figures nobody will see only wastes time.
    if not save_mode and not want_show:
        return
    try:
        import matplotlib
    except ImportError:
        gs.warning(_("matplotlib not available - skipping plots"))
        return

    _activate_backend(matplotlib, backend_opt, save_mode, want_show)

    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        gs.warning(_("matplotlib.pyplot or numpy not available - skipping plots"))
        return

    # matplotlib.use() only sets rcParams; the backend module loads lazily on
    # first figure creation. Probe interactive backends now so failures are
    # caught here with a clean fallback rather than mid-plot.
    if matplotlib.get_backend().lower() not in NON_INTERACTIVE_BACKENDS:
        try:
            _probe = plt.figure()
            plt.close(_probe)
        except Exception as exc:  # noqa: BLE001
            gs.warning(
                _("Backend '{}' failed to initialise ({}); falling back to Agg").format(
                    matplotlib.get_backend(), exc
                )
            )
            matplotlib.use("Agg", force=True)

    make_plots(
        matplotlib,
        plt,
        np,
        *plot_args_without_mpl,
        reverse=reverse,
        plot=plot,
        roc_plot=roc_plot,
        boxplot=boxplot,
        show=show,
    )


def main():
    options, flags = gs.parser()

    import numpy as np
    from grass.tools import Tools

    raster = options["raster"]
    points = options["map"]
    column = options["column"]
    layer = options["layer"]
    positive_value = options["positive_value"]
    negative_value = options["negative_value"]
    steps = int(options["steps"])
    plot_range = options["range"]
    fmt = options["format"]
    output = options["output"]
    classified_output = options["classified_output"]
    apply_criterion = options["apply_criterion"]
    plot = options["plot"]
    roc_plot = options["roc_plot"]
    boxplot = options["boxplot"]
    backend_opt = options.get("backend", "default")
    # numpy.isclose does not validate rtol/atol: a negative value silently
    # behaves as exact equality, inf merges every candidate into one run, and
    # nan warns then degrades to exact equality. Reject all three up front.
    try:
        tie_tolerance = float(options["tie_tolerance"])
    except ValueError:
        gs.fatal(_("Option tie_tolerance must be a number"))
    if not math.isfinite(tie_tolerance):
        gs.fatal(_("Option tie_tolerance must be finite"))
    if tie_tolerance < 0:
        gs.fatal(_("Option tie_tolerance must not be negative"))
    reverse = flags["r"]
    # Which plots to display interactively (empty => show nothing).
    plots_sel = [p.strip() for p in options["plots"].split(",") if p.strip()]
    criteria_sel = [c.strip() for c in options["criterion"].split(",") if c.strip()]
    # 'all' expands to every reported criterion. Aliases are not in the option
    # list, so no further de-duplication is needed here.
    if "all" in criteria_sel:
        criteria_sel = list(CRITERIA)

    # Validate inputs.
    if not gs.find_file(raster, element="cell")["fullname"]:
        gs.fatal(_("Raster map <{}> not found").format(raster))
    if not gs.find_file(points, element="vector")["fullname"]:
        gs.fatal(_("Vector map <{}> not found").format(points))

    tools = Tools()

    observed, values = sample_points(
        tools, raster, points, column, layer, positive_value, negative_value
    )
    n = len(observed)
    if n == 0:
        gs.fatal(_("No usable reference points (need both classes)"))
    obs_arr = np.asarray(observed)
    n_pos = int((obs_arr == 1).sum())
    n_neg = int((obs_arr == 0).sum())
    if n_pos == 0 or n_neg == 0:
        gs.fatal(
            _("Column <{}> must contain both the positive and negative class").format(
                column
            )
        )

    # Threshold grid for the sensitivity/specificity plot only. Its resolution
    # (steps) and span (range) do not influence the threshold table or AUC.
    values_arr = np.asarray(values, dtype=float)
    if plot_range == "sample":
        gmin, gmax = float(values_arr.min()), float(values_arr.max())
    else:
        info = gs.raster_info(raster)
        if info.get("min") is None or info.get("max") is None:
            gs.fatal(_("Raster <{}> has no finite values").format(raster))
        gmin, gmax = float(info["min"]), float(info["max"])
    if gmin == gmax:
        gs.fatal(_("Plot value range collapses to a single value (min == max)"))
    grid = np.linspace(gmin, gmax, steps)
    grid_tp, grid_fp, grid_fn, grid_tn = confusion(grid, values, observed, reverse)

    # Optimal thresholds are selected on the EXACT empirical breakpoints of the
    # sampled reference values, not on the plotting grid.
    emp = empirical_thresholds(values)
    emp_tp, emp_fp, emp_fn, emp_tn = confusion(emp, values, observed, reverse)

    fpr, tpr, auc = roc_auc(values, observed, reverse)
    rows = best_candidates(emp, emp_tp, emp_fp, emp_fn, emp_tn, tie_tolerance)
    rows_by_criterion = {r["criterion"]: r for r in rows}

    # Raster value range for the summary (informational).
    rinfo = gs.raster_info(raster)
    rmin = None if rinfo.get("min") is None else float(rinfo["min"])
    rmax = None if rinfo.get("max") is None else float(rinfo["max"])

    summary = {
        "raster": raster,
        "points": points,
        "column": column,
        "positive_value": positive_value,
        "negative_value": negative_value,
        "n_points": n,
        "n_positive": n_pos,
        "n_negative": n_neg,
        "raster_min": rmin,
        "raster_max": rmax,
        "steps": steps,
        "n_breakpoints": int(len(emp)),
        "reverse": bool(reverse),
        "rule": _rule_text(reverse),
        "youden_aliases": list(YOUDEN_ALIASES),
        "auc": None if (auc != auc) else float(auc),
    }

    auc_txt = "n/a" if (auc != auc) else f"{auc:.3f}"
    gs.message(
        _("Reference points: {} (class 1: {}, class 0: {})  |  AUC: {}").format(
            n, n_pos, n_neg, auc_txt
        )
    )

    write_table(rows, summary, fmt, output)

    # Optional classified raster.
    if classified_output:
        chosen = rows_by_criterion.get(apply_criterion)
        if chosen is None:
            gs.warning(
                _("Criterion '{}' not available; <{}> not created").format(
                    apply_criterion, classified_output
                )
            )
        else:
            classify_raster(
                tools, raster, classified_output, chosen["threshold"], reverse
            )

    # Resolve selected criteria to (label, threshold) pairs for the plots.
    refs = []
    for crit in criteria_sel:
        row = rows_by_criterion.get(crit)
        if row is None:
            gs.warning(_("Unknown criterion '{}' - skipping").format(crit))
            continue
        refs.append((crit, row["threshold"]))
    if not refs:
        # Always draw at least one reference line so plots stay informative.
        refs = [("max_youden_j", rows_by_criterion["max_youden_j"]["threshold"])]

    if backend_opt == "no_plot":
        if plot or roc_plot or boxplot:
            gs.warning(
                _(
                    "backend=no_plot was set; plot/roc_plot/boxplot paths "
                    "were ignored. Remove backend=no_plot to save the plots."
                )
            )
        if plots_sel:
            gs.warning(
                _(
                    "backend=no_plot was set; plots={} ignored (nothing is displayed)."
                ).format(",".join(plots_sel))
            )
    else:
        run_plots(
            backend_opt,
            grid,
            grid_tp,
            grid_fp,
            grid_fn,
            grid_tn,
            fpr,
            tpr,
            auc,
            raster,
            values,
            observed,
            refs,
            reverse=reverse,
            plot=plot,
            roc_plot=roc_plot,
            boxplot=boxplot,
            show=plots_sel,
        )

    return 0


if __name__ == "__main__":
    atexit.register(cleanup)
    sys.exit(main())

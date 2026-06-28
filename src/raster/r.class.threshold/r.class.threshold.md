## DESCRIPTION

*r.class.threshold* helps to find a good threshold for separating a raster with
continuous values (such as an NDVI map) into two classes. The threshold is
evaluated against observed reference data supplied as a vector point layer whose
attribute table contains a column with two classes: the **positive** (target /
presence) class and the **negative** (non-target / absence) class. By default
these are coded **1** and **0**, but any two distinct values can be used through
the **positive_value** and **negative_value** options (for example
`presence`/`absence`, `yes`/`no`, `true`/`false`, or species-specific codes).

The module reports candidate thresholds, diagnostic statistics, and plots. It
does *not* by itself produce a classified map, but it can optionally write one
(see **classified_output** below).

### Confusion matrix

The module samples the input **raster** at every reference point. It then
computes, for the empirical breakpoints of the sampled values, a confusion
matrix. This is done as follows.

At a given threshold *t*, each reference point is assigned a predicted class and
compared with its observed class. By default a point is predicted as the
positive class when the raster value is greater than or equal to the threshold
(`value >= t`); with the **-r** flag the rule is reversed (`value <= t`), which
is appropriate when low values indicate the target class. This gives four
counts:

- **TP** -- observed positive, predicted positive (true positive)
- **FP** -- observed negative, predicted positive (false positive)
- **FN** -- observed positive, predicted negative (false negative)
- **TN** -- observed negative, predicted negative (true negative)

with `N = TP + FP + FN + TN` the total number of reference points.

### STATISTICS AND FORMULAS

Each candidate threshold is described by the following per-threshold
statistics:

| Statistic | Formula | Meaning |
|---|---|---|
| Sensitivity (TPR, recall) | `TP / (TP + FN)` | Share of observed positives correctly predicted (left y-axis of the plot) |
| Specificity (TNR) | `TN / (TN + FP)` | Share of observed negatives correctly predicted (right y-axis of the plot) |
| Precision | `TP / (TP + FP)` | Share of predicted positives that are correct |
| Recall | `TP / (TP + FN)` | Identical to sensitivity |
| Accuracy | `(TP + TN) / N` | Overall fraction of correctly classified points |
| Balanced accuracy | `(sensitivity + specificity) / 2` | Accuracy averaged over the two classes; robust to class imbalance |
| F1 score | `2 * TP / (2 * TP + FP + FN)` | Harmonic mean of precision and recall |
| Youden's J | `sensitivity + specificity - 1` | Ranges from -1 to 1; 0 means no better than chance |
| True Skill Statistic (TSS) | `sensitivity + specificity - 1` | Numerically identical to Youden's J |
| Cohen's kappa (k) | `(p_o - p_e) / (1 - p_e)` | Agreement corrected for chance (see below) |

For Cohen's kappa, the observed agreement is the accuracy
(`p_o = (TP + TN) / N`) and the expected (chance) agreement is:

```text
p_e = [ (TP + FP)(TP + FN) + (FN + TN)(FP + TN) ] / N^2
```

The **AUC** (Area Under the ROC Curve) is reported once for the whole dataset
and is computed exactly from the rank-sum (Mann-Whitney) statistic, which is
tie-aware and independent of the number of **steps**:

```text
AUC = ( R1 - n1 * (n1 + 1) / 2 ) / ( n1 * n0 )
```

where `R1` is the sum of the (midrank) ranks of the raster values at the
positive points after ranking all points by raster value, `n1` is the number of
positive points and `n0` the number of negative points.

### SELECTION CRITERIA

The candidate-threshold table reports one row per criterion. Every criterion is
always listed in the output table; the **criterion** option only controls which
of them are drawn as reference lines on the plots. Each criterion selects the
threshold *t\** that optimises a combination of the statistics above:

| Criterion | Selected threshold |
|---|---|
| `max_youden_j` | `t* = argmax_t [ sensitivity(t) + specificity(t) - 1 ]` |
| `equal_sens_spec` | `t* = argmin_t \| sensitivity(t) - specificity(t) \|` |
| `closest_topleft` | `t* = argmin_t [ (1 - sensitivity(t))^2 + (1 - specificity(t))^2 ]` |
| `max_accuracy` | `t* = argmax_t accuracy(t)` |
| `max_f1` | `t* = argmax_t F1(t)` |
| `max_kappa` | `t* = argmax_t kappa(t)` |

**Aliases.** Several popular criteria are *mathematically identical* to
`max_youden_j` and therefore always select the same threshold, so they are not
reported as separate rows:

- The **True Skill Statistic (TSS)** equals Youden's J exactly
  (`sensitivity + specificity - 1`).
- **Maximum balanced accuracy** maximises `(sensitivity + specificity) / 2`,
  which differs from Youden's J only by an additive/multiplicative constant and
  so has the same maximiser.

The `max_youden_j` row therefore also gives you the TSS-optimal and
balanced-accuracy-optimal threshold. (The balanced-accuracy *value* is still
reported, as the `balanced_accuracy` field, for every criterion.) "Maximum
sensitivity" and "maximum recall" alone are degenerate -- any threshold below
the smallest value attains them -- and are likewise not offered.

Classifier performance is frequently constant over a whole *interval* of
thresholds rather than at a single point. When the optimum forms such a
plateau, the row reports the plateau bounds as `threshold_lo` and
`threshold_hi`, and `threshold` is their midpoint (a representative value). The
plateau is always a single *contiguous* run of optimal breakpoints: if the
optimum is attained at several disjoint locations, the longest contiguous run is
chosen (and, between equally long runs, the most central one), so the reported
`threshold` is itself an optimum rather than a midpoint spanning a gap. For an
isolated optimum, all three values coincide. The confusion counts and metrics in
the row are taken at the representative threshold.

By default two thresholds are treated as tied optima only when their scores are
*exactly* equal. This avoids silently merging near-optima -- for example a
one-observation difference in accuracy on a large dataset -- into a single
plateau. If you want a tolerance, set **tie_tolerance** to a small positive
value (interpreted as in `numpy.isclose`, i.e. combined relative and absolute).

Each criterion is described by `threshold`, `threshold_lo`, `threshold_hi`, TP,
FP, FN, TN, sensitivity, specificity, accuracy, balanced accuracy, precision,
recall, the F1 score, Youden's J and Cohen's kappa. Where a statistic is
mathematically undefined (for example kappa when `1 - p_e = 0`), it is reported
as `NA` in plain/CSV output and as `null` in JSON. The AUC is reported in the
on-screen message and, for JSON output, in the `summary` object.

In the **plain-text** output the table is *transposed*: one row per statistic
and one column per criterion. This keeps the table narrow and readable as the
number of statistics grows. The **CSV** and **JSON** output keep the
conventional one-record-per-criterion layout for easy machine processing.

Numeric values in the JSON and CSV output are written at full precision; the
plain-text table rounds the rate metrics for readability but keeps the
thresholds at high precision. The full-precision threshold matters for rasters
whose meaningful values are very small or very large.

Note that the AUC measures the overall ranking quality of the raster as a
predictor and is independent of any single threshold; it is reported alongside
the thresholds for context, not as a validation of the chosen threshold itself.

### Choosing a criterion

For balanced classes, `max_accuracy` is reasonable. For **imbalanced** classes
it can be misleading (a classifier that always predicts the majority class can
have high accuracy), and `max_f1` ignores true negatives entirely. In those
cases `max_youden_j` (equivalently, maximum balanced accuracy or TSS) or
`max_kappa` are usually more informative. If the target class is rare and you
care primarily about it, a precision-recall view (the `precision` and `recall`
fields) is more telling than ROC/AUC.

### Calibration vs validation

The same point set is used both to choose the threshold and to report the
statistics at that threshold. This is threshold *calibration*, not independent
*validation*: statistics reported at the selected threshold are optimistic
because the threshold was chosen to optimise them on these very points. If you
need an unbiased performance estimate, fit the threshold on one set of points
and evaluate it on a separate, independent set. The points are therefore
referred to as *reference points* rather than *validation points*.

### Outputs

The following outputs can be produced:

- A **plot** (file) and/or interactive window showing the threshold on the
  x-axis, the percentage of correctly predicted positives (sensitivity) on the
  left y-axis and the percentage of correctly predicted negatives (specificity)
  on the right y-axis.
- A **roc_plot** showing the Receiver Operating Characteristic (ROC) curve
  together with the Area Under the Curve (AUC).
- A **boxplot** of the raster values grouped by observed class.
- A table of candidate thresholds (**output**) in the selected **format**
  (plain text, CSV or JSON).
- Optionally, a classified binary raster (**classified_output**), produced by
  applying the threshold of the criterion named in **apply_criterion**. Without
  **-r** the output is 1 where `value >= threshold` and 0 otherwise; with **-r**
  it is 1 where `value <= threshold`. NULL cells stay NULL.

Saving a plot to a file and displaying it on screen are controlled
independently. The **plot**, **roc_plot** and **boxplot** options write image
files; the **plots** option selects which of the three figures are shown
interactively in a window. They can be combined (save *and* show) or used on
their own.

## NOTES

By default a point is predicted as the positive class when the raster value is
greater than or equal to the threshold. Use the **-r** flag to reverse the rule
(predict positive where the value is less than or equal to the threshold) when
low values indicate the target class. The active rule is shown in the plot
titles and in the JSON `summary`.

The **steps** option controls only the resolution of the sensitivity/specificity
plot. The reported optimal thresholds are computed on the empirical breakpoints
of the sampled values, and the AUC and ROC curve are computed from the empirical
value distribution, so all of these are independent of **steps**. Increasing
**steps** does *not* give a more accurate threshold table.

The **range** option controls the value span of the sensitivity/specificity plot
x-axis. The default `raster` spans the full raster min/max. If the raster
contains extreme values that are not represented among the reference points, the
informative part of the curve can be compressed; `range=sample` then spans only
the range of the sampled reference values.

The **criterion** option only selects which thresholds are drawn as reference
lines on the plots; the output table always lists every criterion. Use
`criterion=all` to draw a reference line for every criterion at once instead of
listing them individually. Criteria that share a threshold (which is common,
since several criteria often agree) are merged into a single line in the legend.

The **plots** option selects which figures are shown interactively
(`threshold`, `roc`, `boxplot`, or any combination). If **plots** is left empty,
nothing is displayed on screen, even with an interactive backend; this is the
right setting for batch/scripted use where you only want files or the table.
Showing a plot interactively needs an interactive **backend** (for example
`QtAgg` or `TkAgg`) and an available display.

Points that fall outside the raster (NULL), or whose observed value matches
neither **positive_value** nor **negative_value**, are ignored with a warning.
The column must contain both classes.

The module copies the reference vector to a uniquely named temporary map before
sampling so the user's data is never modified; the copy is removed on exit. For
very large reference datasets this copy can be expensive in time and disk space.
The temporary sampled-value column and the temporary vector both use
collision-safe generated names, and the **layer** option is honoured throughout,
so non-default layers work correctly.

The plots require the Python *matplotlib* package and the computation requires
*numpy*. If a plot output file is given, the image format is taken from the file
extension (for example `.png`, `.pdf` or `.svg`). The **backend** option selects
the matplotlib backend; `backend=no_plot` skips plotting entirely (matplotlib is
not imported), which is useful for automation. To see a plot in a window, choose
an interactive backend and list the figure(s) in **plots**.

## EXAMPLE

Find a good NDVI threshold to separate vegetated from non-vegetated points,
write the candidate thresholds as JSON, save the plots, and also write a
classified raster using the Youden-optimal threshold:

```sh
r.class.threshold raster=ndvi map=field_plots column=vegetated \
    steps=200 format=json output=thresholds.json \
    plot=ndvi_sensspec.png roc_plot=ndvi_roc.png \
    classified_output=ndvi_binary apply_criterion=max_youden_j
```

Use textual class codes and write the candidate thresholds as CSV to standard
output:

```sh
r.class.threshold raster=ndvi map=field_plots column=landcover \
    positive_value=vegetated negative_value=bare format=csv
```

Reverse the rule (low values indicate the target) and only run the table, with
no plotting, for use in a script:

```sh
r.class.threshold raster=depth map=sites column=present -r \
    backend=no_plot format=json output=thresholds.json
```

Show the ROC curve and boxplot interactively, drawing a reference line for every
criterion, without saving any image files:

```sh
r.class.threshold raster=ndvi map=field_plots column=vegetated \
    plots=roc,boxplot criterion=all backend=QtAgg
```

## SEE ALSO

In short: *r.edm.eval* is built to **evaluate and compare model predictions**,
while *r.class.threshold* is built to **select, document and apply a
classification threshold**. Both compute the same diagnostic core, so the choice
is about emphasis.

*r.class.threshold* and
*[r.edm.eval](https://grass.osgeo.org/grass-stable/manuals/addons/r.edm.eval.html)*
overlap in their diagnostic core -- both compute a confusion matrix across
thresholds, ROC/AUC, the true skill statistic (TSS, equivalent to Youden's J)
and Cohen's kappa, and report the thresholds that optimise them. They are built
for different jobs, however:

- Use *r.class.threshold* when the reference data are **vector points** sampled
  against a single raster, when you want exact (non-binned) optima over a wider
  set of criteria, or when you need the **classified binary raster** produced at
  the chosen threshold.
- Use *r.edm.eval* when the reference and the prediction are both **raster
  layers** (every cell is an observation), when comparing **several prediction
  layers** at once, or when you need species-distribution-modelling features
  such as background-point handling, an absence buffer, or prevalence
  adjustment.

*[r.edm.eval](https://grass.osgeo.org/grass-stable/manuals/addons/r.edm.eval.html), [r.learn.train](https://grass.osgeo.org/grass-stable/manuals/addons/r.learn.train.html), [r.maxent.train](https://grass.osgeo.org/grass-stable/manuals/addons/r.maxent.train.html)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green
academy](https://has.nl), [Innovative Biomonitoring research
group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research
group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)

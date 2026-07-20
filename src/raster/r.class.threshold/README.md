## NAME

_**r.class.threshold**_ - Selects thresholds for separating a continuous raster into two classes.

> [!WARNING]  
> This addon is work in progress, with limited testing. Consider this an early alpha version!! Use at your own risk.
> Do you encounter bugs of do you have suggestions for improvements, please file a bug report.

## SYNOPSIS

**r.class.threshold**  

**r.class.threshold --help**  

**r.class.threshold** \[-**r**\] **raster**\=_name_ **map**\=_name_ **column**\=_name_ \[**positive\_value**\=_string_\] \[**negative\_value**\=_string_\] \[**layer**\=_string_\] \[**output**\=_name_\] \[**format**\=_string_\] \[**classified\_output**\=_name_\] \[**apply\_criterion**\=_string_\] \[**plots**\=_string_\[,_string_,...\]\] \[**criterion**\=_string_\[,_string_,...\]\] \[**plot**\=_name_\] \[**roc\_plot**\=_name_\] \[**boxplot**\=_name_\] \[**range**\=_string_\] \[**steps**\=_integer_\] \[**backend**\=_string_\] \[**tie\_tolerance**\=_float_\] \[--**overwrite**\] \[--**help**\] \[--**verbose**\] \[--**quiet**\] \[--**ui**\]

### Flags:

* **\-r**: Reverse rule (class 1 at or below the threshold). Use when low raster values indicate the target class
* **\--overwrite**. Allow output files to overwrite existing files
* **\--help** Print usage summary
* **\--verbose** Verbose module output
* **\--quiet** Quiet module output
* **\--ui** Force launching GUI dialog

### Parameters:

* **raster**\=_name_ **\[required\]** Input raster - Name of input raster with continuous values
* **map**\=_name_ **\[required\]** Reference points - Point vector with an attribute table holding the observed class
* **column**\=_name_ **\[required\]** Class column - Attribute column holding the observed class
* **positive\_value**\=_string_ Positive (target) value - Value in the class column that denotes the target class. Default is 1.
* **negative\_value**\=_string_ Negative (non-target) value - Value in the class column that denotes the non-target class. Default is 0.
* **layer**\=_string_ Layer - Vector features can have category values in different layers. This number determines which layer to use. When used with direct OGR access this is the layer name. Default: _1_
* **output**\=_name_ Threshold table file - File for the selected-threshold table. Default is standard output.
* **format**\=_string_ Table format - Output format of the threshold table. Options: _plain, csv, json_. Default: _plain_
* **classified\_output**\=_name_ Classified raster - Optional binary 0/1 raster, produced by applying the threshold of the criterion set by apply\_criterion
* **apply\_criterion**\=_string_ Criterion for classified raster - Criterion whose threshold is applied when classified\_output is requested. Options: _max\_youden\_j, equal\_sens\_spec, closest\_topleft, max\_accuracy, max\_f1, max\_kappa_. Default: _max\_youden\_j_
* **plots**\=_string\[,_string_,...\]_ Plots to display interactively. Plots to show in a window. Requires an interactive backend and display. If none are given, no plot is shown interactively. File output is controlled separately by plot=, roc\_plot= and boxplot=. Options: _threshold, roc, boxplot_
* **criterion**\=_string\[,_string_,...\]_ Reference-line criteria - Criteria whose thresholds are drawn as reference lines on the threshold plot and boxplot. Use 'all' for every criterion. This does NOT limit the output table, which always lists every criterion. Criteria sharing a threshold are merged in the legend. Options: _all, max\_youden\_j, equal\_sens\_spec, closest\_topleft, max\_accuracy, max\_f1, max\_kappa_ Default: _max\_youden\_j_
* **plot**\=_name_ Threshold plot file - File for the sensitivity/specificity vs threshold plot. The extension sets the type. If omitted, no file is written.
* **roc\_plot**\=_name_ ROC plot file - File for the ROC plot. The extension sets the type. If omitted, no file is written.
* **boxplot**\=_name_: Boxplot file - File for the boxplot. The extension sets the type. If omitted, no file is written.
* **range**\=_string_ Threshold plot x-axis range - 'raster' spans the full raster min/max; 'sample' spans only the range of the sampled reference values (useful when the raster has extreme values not represented in the reference points). Options: _raster, sample_. Default: _raster_
* **steps**\=_integer_ Threshold plot resolution - Number of steps drawn on the sensitivity/specificity plot. Does not affect the threshold table, ROC curve or AUC, which use the empirical value breakpoints. Options: _2-100000_. Default: _100_
* **backend**\=_string_ Matplotlib backend - Backend used for plotting. 'default' lets matplotlib auto-select. 'no\_plot' skips plotting entirely (matplotlib not imported; only the threshold table is produced - useful for automation). 'Agg' is non-interactive (savefig only). The others are interactive and need the matching GUI toolkit installed (WXAgg=wxPython, QtAgg=PyQt/PySide, TkAgg=Tkinter, GTK\*Agg=GTK, MacOSX=native macOS). Falls back to Agg with a warning if the chosen backend cannot be initialised. Options: _default, no\_plot, Agg, WXAgg, QtAgg, TkAgg, GTK3Agg, GTK4Agg, MacOSX_ Default: _default_
* **tie\_tolerance**\=_float_ Tie tolerance for optima - Two scores are treated as tied optima when they differ by no more than this tolerance (relative + absolute, as in numpy.isclose). The default 0 requires exact equality, so a one-observation difference is not silently merged. Must be non-negative and finite. Default: _0.0_

## DESCRIPTION

*r.class.threshold* selects thresholds for separating a raster with continuous
values (such as an NDVI map) into two classes. Each threshold is evaluated
against observed reference data supplied as a vector point layer whose attribute
table contains a column with two classes: the **positive** (target / presence)
class and the **negative** (non-target / absence) class. By default these are
coded **1** and **0**, but any two distinct values can be used through the
**positive_value** and **negative_value** options (for example
`presence`/`absence`, `yes`/`no`, `true`/`false`, or species-specific codes).

There is no single optimal threshold: the module reports one selected threshold
per criterion, together with diagnostic statistics and plots. It does *not* by
itself produce a classified map, but it can optionally write one (see
**classified_output** below).

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

### Classification statistics

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
tie-aware (ties receive half credit through midranks) and independent of the
number of **steps**:

```text
AUC = ( R1 - n1 * (n1 + 1) / 2 ) / ( n1 * n0 )
```

where `R1` is the sum of the (midrank) ranks of the raster values at the
positive points after ranking all points by raster value, `n1` is the number of
positive points and `n0` the number of negative points. With the **-r** flag the
ranking is based on the negated raster values, so a larger ranking score always
indicates stronger evidence for the positive class.

The AUC measures the overall ranking quality of the raster as a predictor and is
independent of any single threshold. It is reported alongside the thresholds for
context, not as a validation of the chosen threshold itself.

### Threshold criteria

The selected-threshold table reports one row per criterion. Every criterion is
always listed in the output table; the **criterion** option only controls which
of them are drawn as reference lines on the plots, and **apply_criterion**
selects which threshold is used for **classified_output**. Each criterion selects
the threshold *t\** that optimises a combination of the statistics above:

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
  which is exactly `(J + 1) / 2` and so has the same maximiser.

The `max_youden_j` row therefore also gives you the TSS-optimal and
balanced-accuracy-optimal threshold. (The balanced-accuracy *value* is still
reported, as the `balanced_accuracy` field, for every criterion.) "Maximum
sensitivity" and "maximum recall" alone are degenerate -- an extreme threshold
classifies every point as positive and so attains them -- and are likewise not
offered.

The `max_youden_j` and `closest_topleft` criteria can select different
thresholds, even though both weight sensitivity and specificity equally.

Candidate thresholds are placed midway between consecutive unique sampled
values, with one additional candidate just below and one just above the sampled
range. This covers every distinct binary classification obtainable from the
sample.

Classifier performance is frequently constant over a whole *interval* of
thresholds rather than at a single point. When the optimum forms such a plateau,
the row reports the bounds of the selected run of tied candidates as
`threshold_lo` and `threshold_hi`, and `threshold` is the candidate nearest the
midpoint of that run. The run is always a single *contiguous* set of candidates:
if the optimum is attained at several disjoint locations, the longest contiguous
run is chosen (and, between equally long runs, the most central one), so the
reported `threshold` is itself an optimum rather than a value spanning a gap.
Where a run contains an even number of candidates, the lower of the two central
candidates is used. For an isolated optimum, all three values coincide.

The reported `threshold` is therefore always one of the candidates, and the
confusion counts and metrics in the row are exactly those obtained by applying
it. A **classified_output** raster written at that threshold reproduces the
counts reported for its criterion.

By default two thresholds are treated as tied optima only when their scores are
*exactly* equal. This avoids silently merging near-optima -- for example a
one-observation difference in accuracy on a large dataset -- into a single run.
If you want a tolerance, set **tie_tolerance** to a small positive value
(interpreted as in `numpy.isclose`, i.e. combined relative and absolute). The
value must be non-negative and finite.

Each criterion is described by `threshold`, `threshold_lo`, `threshold_hi`, TP,
FP, FN, TN, sensitivity, specificity, accuracy, balanced accuracy, precision,
recall, the F1 score, Youden's J and Cohen's kappa. Where a statistic is
mathematically undefined (for example kappa when `1 - p_e = 0`), it is written as
`NA` in plain-text output, as an empty field in CSV, and as `null` in JSON. The
AUC is reported in the on-screen message and, for JSON output, in the `summary`
object.

In the **plain-text** output the table is *transposed*: one row per statistic
and one column per criterion. This keeps the table narrow and readable as the
number of statistics grows. The **CSV** and **JSON** output keep the
conventional one-record-per-criterion layout for easy machine processing.

Numeric values in the JSON and CSV output are written at full precision; the
plain-text table rounds the rate metrics for readability but keeps the
thresholds at high precision. The full-precision threshold matters for rasters
whose meaningful values are very small or very large.

### Outputs

The following outputs can be produced:

- A **plot** (file) and/or interactive window showing the threshold on the
  x-axis, the percentage of correctly predicted positives (sensitivity) on the
  left y-axis and the percentage of correctly predicted negatives (specificity)
  on the right y-axis.
- A **roc_plot** showing the Receiver Operating Characteristic (ROC) curve
  together with the Area Under the Curve (AUC).
- A **boxplot** of the raster values grouped by observed class.
- A table of selected thresholds (**output**) in the chosen **format**
  (plain text, CSV or JSON).
- Optionally, a classified binary raster (**classified_output**), produced by
  applying the threshold of the criterion named in **apply_criterion**. Without
  **-r** the output is 1 where `value >= threshold` and 0 otherwise; with **-r**
  it is 1 where `value <= threshold`. NULL cells stay NULL. Because the applied
  threshold is one of the empirical candidates, the raster reproduces exactly
  the confusion counts reported for that criterion.

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

### Choosing a criterion

There is no universally optimal criterion. `max_youden_j` (equivalently, maximum
balanced accuracy or TSS) weights sensitivity and specificity equally.
`max_accuracy` weights the classes according to their frequency among the
reference points: for balanced classes it is reasonable, but for **imbalanced**
classes it can be misleading, since a classifier that always predicts the
majority class can have high accuracy. `max_f1` ignores true negatives entirely
and is most relevant when performance on the positive class is the main concern.
Cohen's kappa depends on the observed and predicted class marginals, so
`max_kappa` should not be treated as an automatic remedy for class imbalance.

The choice should reflect the consequences of false positives and false
negatives and the intended population. If the target class is rare and you care
primarily about it, a precision-recall view (the `precision` and `recall`
fields) is more telling than ROC/AUC.

### Calibration and validation

The same point set is used both to choose the threshold and to report the
statistics at that threshold. This is threshold *calibration*, not independent
*validation*: statistics reported at the selected threshold are optimistic
because the threshold was chosen to optimise them on these very points. If you
need an unbiased performance estimate, fit the threshold on one set of points
and evaluate it on a separate, independent set, or use cross-validation or
resampling. The points are therefore referred to as *reference points* rather
than *validation points*.

### Other notes

The **steps** option controls only the resolution of the sensitivity/specificity
plot. The selected thresholds are computed on the empirical breakpoints of the
sampled values, and the AUC and ROC curve are computed from the empirical value
distribution, so all of these are independent of **steps**. Increasing **steps**
does *not* give a more accurate threshold table.

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
an interactive backend and list the figure(s) in **plots**. If the chosen backend
cannot be initialised, the module falls back to `Agg` with a warning, so files
are still written but nothing is displayed.

## EXAMPLE

Select thresholds for separating vegetated from non-vegetated points, write the
selected thresholds as JSON, save the plots, and also write a classified raster
using the Youden-optimal threshold:

```sh
r.class.threshold raster=ndvi map=field_plots column=vegetated \
    steps=200 format=json output=thresholds.json \
    plot=ndvi_sensspec.png roc_plot=ndvi_roc.png \
    classified_output=ndvi_binary apply_criterion=max_youden_j
```

Use textual class codes and write the selected thresholds as CSV to standard
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

## REFERENCES

Allouche, O., Tsoar, A., & Kadmon, R. (2006). Assessing the accuracy of species
distribution models: Prevalence, kappa and the true skill statistic (TSS).
Journal of Applied Ecology, 43(6), 1223–1232.
https://doi.org/10.1111/j.1365-2664.2006.01214.x

Brodersen, K. H., Ong, C. S., Stephan, K. E., & Buhmann, J. M. (2010). The
Balanced Accuracy and Its Posterior Distribution. 2010 20th International
Conference on Pattern Recognition, 3121–3124.
https://doi.org/10.1109/ICPR.2010.764

Cohen, J. (1960). A Coefficient of Agreement for Nominal Scales. Educational and
Psychological Measurement, 20(1), 37–46.
https://doi.org/10.1177/001316446002000104

Hanley, J. A., & McNeil, B. J. (1982). The meaning and use of the area under a
receiver operating characteristic (ROC) curve. Radiology, 143(1), 29–36.
https://doi.org/10.1148/radiology.143.1.7063747

Perkins, N. J., & Schisterman, E. F. (2006). The Inconsistency of “Optimal”
Cutpoints Obtained using Two Criteria based on the Receiver Operating
Characteristic Curve. American Journal of Epidemiology, 163(7), 670–675.
https://doi.org/10.1093/aje/kwj063

Thiele, C., & Hirschfeld, G. (2021). cutpointr: Improved Estimation and
Validation of Optimal Cutpoints in R. Journal of Statistical Software, 98, 1–27.
https://doi.org/10.18637/jss.v098.i11

Youden, W. J. (1950). Index for rating diagnostic tests. Cancer, 3(1), 32–35.
https://doi.org/10.1002/1097-0142(1950)3:1<32::AID-CNCR2820030106>3.0.CO;2-3

## SEE ALSO

*[r.edm.eval](https://grass.osgeo.org/grass-stable/manuals/addons/r.edm.eval.html)*:
use when the reference and the prediction are both **raster layers** (every cell
is an observation), when comparing **several prediction layers** at once, or
when you need species-distribution-modelling features such as background-point
handling, an absence buffer, or prevalence adjustment.

*[r.confusionmatrix](https://grass.osgeo.org/grass-stable/manuals/addons/r.confusionmatrix.html)*:
use when the raster is **already classified** and you only need a confusion
matrix, the accuracies and Cohen's kappa for it, rather than a threshold.

*[r.learn.train](https://grass.osgeo.org/grass-stable/manuals/addons/r.learn.train.html)*

*[r.maxent.train](https://grass.osgeo.org/grass-stable/manuals/addons/r.maxent.train.html)*
`

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green
academy](https://has.nl), [Innovative Biomonitoring research
group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research
group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)

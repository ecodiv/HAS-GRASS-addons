## DESCRIPTION

*t.rast.scatter* draws a scatterplot of the values of two space-time raster
datasets (strds), sampled at a set of points within the region of interest. Both
datasets are sampled at the *same* point locations and, crucially, the same
points are reused at every shared timestep. Each plotted point is therefore a
matched **(x, y)** pair for one location at one moment in time, where *x* comes
from the dataset given with **xstrds** and *y* from the dataset given with
**ystrds**. This makes it possible to explore the relationship between two
time-varying variables (for example land surface temperature versus a vegetation
index, or rainfall versus soil moisture) across both space and time in a single
plot.

Optionally, one or more fits can be overlaid on the cloud of points: an ordinary
least-squares (OLS) regression line (**-o**), a LOWESS smoother (**-l**), and/or
a Generalized Additive Model (GAM) curve (**-g**).

The module works only on datasets that use **absolute** (calendar-dated) time.
Relative time is not supported, because the time-matching tolerance (e.g.
*1 day*) has no meaning without a known time unit.

### Sampling

The sample locations are provided as a point vector map with the **points**
option. Both datasets are sampled at these points with
*[t.rast.what](t.rast.what.md)* across all of their registered timesteps. Only
point features are used, and each point keeps a stable category (id) so that the
two datasets are paired at exactly the same location.

The **where** option can be used to restrict the timesteps that are sampled, for
example to limit the analysis to a given period. See the [temporal data
processing](https://grass.osgeo.org/grass-stable/manuals/temporalintro.html)
documentation for the syntax of the *where* clause.

Sampling can be sped up on multi-core machines with the **nprocs** option, which
sets the number of parallel *r.what* processes used by *t.rast.what*.

### Temporal pairing

Because the two datasets rarely have identical timestamps, the **method** option
controls how their timesteps are paired into (x, y) observations:

- **nearest** (default) matches each map of the x dataset to the closest-in-time
  map of the y dataset, provided the time difference is within **tolerance**.
  The tolerance is a duration such as *1 day*, *6 hours* or *30 minutes*. Maps
  with no counterpart inside this window are dropped. This method preserves the
  individual observations.
- **mean**, **median**, **sum**, **min** and **max** are *aggregate* methods.
  They first bin both datasets to a common **frequency** (a pandas offset alias,
  e.g. *D* daily, *W* weekly, *MS* month-start, *YS* year-start) per point, then
  reduce each bin with the chosen statistic and pair the per-period summaries.

The **tolerance** option applies only to *method=nearest*, and **frequency**
only to the aggregate methods; supplying the wrong one for the chosen method is
an error.

### Regression and smoothers

Three optional fits can be added on top of the scatter cloud:

- **-o** adds the OLS regression line. Its slope, intercept and R² are always
  printed to the terminal.
- **-l** adds a LOWESS (locally weighted) smoother. The span is controlled with
  **lowess_frac** (fraction of the data used for each local fit, between 0 and
  1; larger is smoother). This fit requires the *statsmodels* package.
- **-g** adds a GAM (smooth spline) curve. This fit requires the *pygam*
  package.

With the **-t** flag, the fit statistics (OLS slope, R², etc.) are also shown in
the plot legend; without it they are only printed to the terminal.

### Output and appearance

By default the plot is shown in an interactive window. If an **output** file is
given, the plot is saved instead, with the format taken from the file extension
(e.g. *.png*, *.pdf*, *.svg*). The resolution (**dpi**) and figure size
(**plot_dimensions**, in inches) can be set. The matplotlib **backend** is
chosen automatically (a non-interactive one when saving to a file) but can be
overridden.

The paired samples can additionally be written to a **csv** file, with one row
per point and timestep, including coordinates and date.

A number of aesthetic options are available: a **title**, custom axis labels
(**x_label**, **y_label**), grid lines (**-d**), and control over the point
**color**, size (**s**), **marker**, transparency (**point_alpha**), base
**fontsize** and fit **line_width**. With the **-c** flag the points are colored
by their timestep and a colorbar is drawn, which can reveal temporal structure
such as seasonal loops (the **color** option is then ignored).

## NOTES

Both input datasets must use absolute time. The module will stop with an error
if either dataset uses relative time.

The optional fits have optional dependencies: the LOWESS smoother (**-l**)
requires *statsmodels* and the GAM curve (**-g**) requires *pygam*. These are
only needed when the corresponding flag is set. The core of the module relies on
*numpy*, *pandas* (>= 2.0), *scipy* and *matplotlib*.

## EXAMPLE

The examples below assume two space-time raster datasets with absolute time, for
example a temperature series *tempmean* and a rainfall series *precip_sum*, and a
point vector map *samples* with the sample locations.

### Example 1

Plot the rainfall (x) against temperature (y) at the sample points, pairing each
temperature map with the nearest rainfall map within one day, and add the OLS
regression line with its statistics in the legend.

```sh
t.rast.scatter xstrds=precip_sum ystrds=tempmean points=samples \
    method=nearest tolerance="1 day" -o -t nprocs=4
```

### Example 2

Aggregate both datasets to monthly means before pairing, color the points by
time to reveal seasonal structure, and add a LOWESS smoother.

```sh
t.rast.scatter xstrds=precip_sum ystrds=tempmean points=samples \
    method=mean frequency=MS -l -c lowess_frac=0.4
```

### Example 3

Save the plot to a PNG file and also export the paired samples to a CSV file,
restricting the analysis to a single year with the **where** option.

```sh
t.rast.scatter xstrds=precip_sum ystrds=tempmean points=samples \
    method=nearest tolerance="1 day" -o \
    where="start_time >= '2010-01-01 00:00:00' AND start_time < '2011-01-01'" \
    output=scatter.png csv=samples.csv dpi=300
```

## SEE ALSO

*[t.rast.stl](t.rast.stl.md),
[t.rast.line](t.rast.line.md),
[t.rast.what](t.rast.what.md),
[t.rast.univar](t.rast.univar.md),
[v.scatterplot](v.scatterplot.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth),
[Innovative Biomonitoring](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/)
and
[Climate-robust Landscapes](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)
research groups at the [HAS green academy](https://has.nl)

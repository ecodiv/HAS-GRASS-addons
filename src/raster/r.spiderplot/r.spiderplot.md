## DESCRIPTION

*r.spiderplot* draws a spider (radar) plot of the values of two or more
**input** rasters. Each raster becomes one axis, arranged evenly around the
circle, and the sampled values are connected into a closed outline.

The rasters are sampled either at a single point or at the features of a
vector map:

- **coordinates** samples a single *east,north* point. When the module is
  launched from a **Map Display**, this field can be filled by clicking in the
  display.
- **map** samples a vector of points or areas. A points map is drawn as one
  line per point. An areas map is aggregated into classes, each drawn as a
  mean outline with a shaded standard-deviation band.

**Classes and facets.** For a vector, features are grouped into classes and
each class is drawn as its own small radar (a facet); a single class is drawn
as one radar. By default areas are grouped by **category**, so several area
features that share a category are treated as one class. Provide a
**group_column** to define classes from an attribute instead: features sharing
a column value form one class. For points, **group_column** likewise
aggregates the points of each class into a mean and standard-deviation band;
without it every point is a separate line. Restrict which features are used
with **cats** or **where**.

Each axis is scaled independently to its own range. Provide the range with the
**minimum** and **maximum** options (one value per input raster, in the same
order). Any bound that is left empty, or omitted entirely, is computed from the
raster's own value range. Values are clamped to their axis range. Use the
**-r** flag to print the *[min, max]* range next to each axis label.

## NOTES

The interactive coordinate picker (the button next to the **coordinates**
field) requires launching the module from the GRASS GUI with an open Map
Display. Run standalone (for example from the command line) the picker is
inactive and the coordinates must be entered directly.

Sampling honors the current computational region. A point that falls outside
the region, or on a NULL cell, produces a warning and is drawn at the axis
minimum.

At least two rasters are required; three or more make the plot meaningful.

For area classes the mean and standard deviation are computed over all cells of
the areas in the class (areas sharing a category are merged first). The band
spans the mean plus and minus one (population) standard deviation.

The **nprocs** and **memory** options are used for the vector aggregation
(rasterizing the areas and computing the zonal statistics) and when an axis
range has to be computed from the rasters.

## EXAMPLES

Spider plot of three rasters at a point, with computed axis ranges, shown in an
interactive window:

```sh
r.spiderplot input=elevation,slope,aspect coordinates=637500,221750
```

Fix the axis ranges, label the axes, and save to a file:

```sh
r.spiderplot input=elevation,slope,aspect \
  minimum=50,0,0 maximum=150,45,360 \
  labels="Elevation,Slope,Aspect" \
  coordinates=637500,221750 output=spider.png -n -l
```

Leave one bound to be computed (empty entry) while fixing the others:

```sh
r.spiderplot input=elevation,slope,aspect \
  minimum=50,0,0 maximum=,45,360 \
  coordinates=637500,221750
```

Sample a points map, drawing one line per point:

```sh
r.spiderplot input=elevation,slope,aspect map=samples output=points.png
```

Aggregate an areas map into one facet per land-cover class, each with a
standard-deviation band:

```sh
r.spiderplot input=elevation,slope,aspect map=zones \
  group_column=landcover output=classes.png
```

## SEE ALSO

*[r.barplot](r.barplot.md), [r.what](r.what.md), [r.univar](r.univar.md),
[t.rast.stl](t.rast.stl.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl), [Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/), [Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)

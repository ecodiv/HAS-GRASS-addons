## DESCRIPTION

*r.histogram* draws a histogram of the non-NULL values in an input raster map.
The **bins** option sets the number of equal-width intervals. The height of
each bar is the number of raster cells in that interval.

The histogram is computed with *r.stats*. Integer rasters are converted to a
temporary floating-point raster to ensure that values are grouped into the
requested number of equal-width bins instead of being reported as individual
categories.

By default, the active Matplotlib style determines the bar color. A single
**color** can be set using a color name, hexadecimal value, or `R:G:B` triplet.
With the **-c** flag, every bar is assigned the input raster's color at the
midpoint of that bin. This mirrors both continuous color ramps and discrete
color tables. If both **-c** and **color** are given, **-c** takes precedence.
The **border_color**, **border_width**, and relative bar width (**rwidth**)
options control the remaining bar appearance.

The histogram can be drawn horizontally (**-h**), with grid lines along the
count axis (**-g**), rotated value-axis labels (**rotate_labels**), an optional
**title**, and limited value-axis bounds (**axis_limits**). A Matplotlib
[style sheet](https://matplotlib.org/stable/gallery/style_sheets/style_sheets_reference.html)
can be applied with the **style** option, for example `style=ggplot`.

By default, the plot is displayed on screen. If **output** is given, the plot
is written to that file. The file format is determined from its extension. The
size (**plot_dimensions**, in inches), resolution (**dpi**), and **fontsize**
can be set as well.

## NOTES

The histogram is computed over the current computational region and respects
an active raster mask. When the current region, mask, or integer data type
requires it, the module creates and removes a temporary floating-point raster.
It does not modify the input map.

For a constant raster, the module draws one bar centered on the single raster
value because multiple zero-width bins would overlap.

Matplotlib is required.

## EXAMPLES

The examples use the North Carolina sample dataset.

Draw a 40-bin histogram of the `elevation` raster:

```sh
g.region raster=elevation
r.histogram map=elevation bins=40 output=r_histogram.png
```

Draw the histogram with each bar colored from the `elevation` raster color
table:

```sh
r.histogram -c map=elevation bins=40 output=r_histogram_colors.png
```

Draw a horizontal histogram with a grid, a reduced relative bar width, and a
Matplotlib style:

```sh
r.histogram -hg map=elevation bins=30 rwidth=0.9 style=ggplot \
  output=r_histogram_horizontal.png
```

## SEE ALSO

*[d.histogram](https://grass.osgeo.org/grass-stable/manuals/d.histogram.html),
[r.boxplot](https://grass.osgeo.org/grass-stable/manuals/addons/r.boxplot.html),
[r.stats](https://grass.osgeo.org/grass-stable/manuals/r.stats.html),
[v.histogram](https://grass.osgeo.org/grass-stable/manuals/addons/v.histogram.html)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl),
[Innovative Biomonitoring research
group](https://www.has.nl/en/research/professorships/innovative-biomonitoring-professorship/),
[Climate-robust Landscapes research
group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)

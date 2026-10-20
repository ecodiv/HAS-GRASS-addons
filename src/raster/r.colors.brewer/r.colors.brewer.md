## DESCRIPTION

*r.colors.brewer* builds a [ColorBrewer](https://colorbrewer2.org) color
table for a raster map. The user selects a scheme from one of three families
(sequential, diverging or qualitative) and the number of classes. The module
then either applies the color table to the raster map with *r.colors*, or,
when no **map** is given (or with the **-n** flag), prints the color rules to
standard output so they can be reused.

### Scheme families

One scheme must be chosen from exactly one of the three families:

- **sequential** for ordered data that runs from low to high: *Blues, BuGn,
  BuPu, GnBu, Greens, Greys, OrRd, Oranges, PuBu, PuBuGn, PuRd, Purples, RdPu,
  Reds, YlGn, YlGnBu, YlOrBr, YlOrRd*.
- **diverging** for data with a meaningful midpoint (such as zero or a mean):
  *BrBG, PRGn, PiYG, PuOr, RdBu, RdGy, RdYlBu, RdYlGn, Spectral*.
- **qualitative** for categorical data: *Accent, Dark2, Paired, Pastel1,
  Pastel2, Set1, Set2, Set3*.

The number of **classes** must be within the range the chosen scheme supports:
3 to 9 for most sequential schemes (3 to 8 for YlOrRd), 3 to 11 for diverging
schemes, and up to 3 to 12 for qualitative schemes. An unsupported number of
classes is reported with the valid range for that scheme.

### Mapping colors to values

For sequential and diverging schemes the colors are, by default, spread evenly
across the map range as a continuous gradient. With the **-d** flag discrete
class bands are created with hard color steps.

By default, the rules are written as percentages. The same rules therefore apply
to any map and can be stored once and reused. Supply **range** as `min,max` to
write absolute breakpoints across a fixed range instead.

The **breakpoints** option sets the class boundaries explicitly for sequential
and diverging schemes. It takes `classes + 1` values as plain numbers (absolute
values) or as percentages. With **-d** each interval becomes a flat band.
Without it, the class colors are centered on their intervals and interpolated
into a gradient.

When the color table uses fixed values (a **range** or absolute
**breakpoints**), cells outside that span keep the nearest end color: values
below the minimum get the first color and values above the maximum get the
last color. Percentage rules that run from 0% to 100% already cover the whole
map, so they need no such extension.

Qualitative schemes assign the colors to integer categories 1 to **classes**.
The **breakpoints**, **range** and **-d** settings do not apply to them.

The **-r** flag reverses the order of the colors. The **null_color** option
sets the color of NULL cells, given as a GRASS color name or as `R:G:B`.

## NOTES

Percentage rules depend on the range of the map they are applied to. If the
rules are meant to be exported later to a QGIS style with absolute breakpoints
with *r.colors.toqml*, build them with **range** or absolute **breakpoints** so
that no percentages remain in the color table.

## EXAMPLES

Apply a 7-class diverging *RdYlGn* color table to a raster map:

```sh
r.colors.brewer map=elevation diverging=RdYlGn classes=7
```

Print a 5-class sequential *Blues* rules string and apply it with *r.colors*:

```sh
r.colors.brewer sequential=Blues classes=5 -n | r.colors map=elevation rules=-
```

Create discrete classes with user-defined breakpoints and a white NULL color:

```sh
r.colors.brewer map=ndvi sequential=YlGn classes=5 -d \
    breakpoints=-0.2,0.0,0.2,0.4,0.6,1.0 null_color=white
```

Write absolute breakpoints across a fixed range (for a legend shared between
maps):

```sh
r.colors.brewer map=slope sequential=Oranges classes=6 range=0,45
```

Use the printed rules from Python with *grass.tools*:

```python
from io import StringIO
from grass.tools import Tools

tools = Tools()
rules = tools.r_colors_brewer(sequential="Blues", classes=5, flags="n").text
tools.r_colors(map="water_bodies", rules=StringIO(rules))
```

## SEE ALSO

*[r.colors](https://grass.osgeo.org/grass-stable/manuals/r.colors.html)*,
*[r.colors.out](https://grass.osgeo.org/grass-stable/manuals/r.colors.out.html)*,
*[r3.colors](https://grass.osgeo.org/grass-stable/manuals/r3.colors.html)*,
*[v.colors](https://grass.osgeo.org/grass-stable/manuals/v.colors.html)*,
*[r.colors.qml](https://grass.osgeo.org/grass-stable/manuals/addons/r.colors.qml.html)*,
*[r.colors.toqml](https://grass.osgeo.org/grass-stable/manuals/addons/r.colors.toqml.html)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl),
[Innovative Biomonitoring research
group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research
group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)

The bundled ColorBrewer color values are by Cynthia Brewer
([colorbrewer2.org](https://colorbrewer2.org)) and are licensed under the
Apache License 2.0.

## DESCRIPTION

*m.printmap* combines raster, vector, legend and label layers into a single PNG
image. Like in the interactive map display, each layer can be made partly
transparent.

The description and settings of layers are written to a small plain-text **spec
file**. They are build up one layer at a time and then render, rather than
describing the whole map in a single long command.

Working with the module therefore has two phases. The first phase consists of
one or more steps to *Build* the spec file. Each run adds (or edits) one layer.
The user picks a layer **type**, fills in that type's options and runs it to
append the layerto the spec file. The second phase is to *render* the spec file
(`operation=render`) to a PNG.

Give the spec file with **new_spec** to start a new map, or **spec** to read or
update an existing one (these are mutually exclusive). Each **type** has its own
tab of options in the GUI. You can fill in more than one, but note that only the
options for the chosen type are used.

The module is designed to make building the spec file easy and then render it to
a PNG. The spec file is, however, also a plain, human-readable list that you can
write or edit by hand. This is handy for fine-tuning the exact position of an
element, or for treating one spec as a template and producing many maps by only
swapping the input map name(s).

When editing by hand, most settings are stored under the parameter name of the
underlying display command, so you can look up their meaning in that command's
manual. A vector layer uses the *d.vect* parameters (`map`, `type`, `color`,
`width`, ...), a raster legend the *d.legend* parameters (`raster`, `at`,
`digits`, `flags`, ...), a scale bar the *d.barscale* parameters, and so on. The
longer GUI option names (e.g. `legend_raster_digits`) are also accepted as
aliases and are converted to the canonical parameter name on the next write.
The exception is font size: each text element stores a `font_scale` (and the
raster legend a `title_scale`) that is a *ratio* of the template base font size
(see [Fonts](#fonts)). Template-level settings live in a `settings` block at the
top of the spec (see [Template settings](#template-settings)); a spec with no
settings is written as a bare list of layers.

### Layer types

The **type** option selects what a layer is:

- *solid*: a full-canvas color fill, used as a background or, at a low
  opacity, as a tint over the layers below.
- *raster*: a raster map.
- *vector*: a vector map (areas, lines or points).
- *labels*: text labels from a vector attribute column.
- *legend_raster*, *legend_vector*: a legend for a raster or vector map.
- *barscale*: a scale bar.
- *grid*: a coordinate grid.
- *image*: an external image (e.g. a logo or inset) placed in a box.

### OPACITY AND LAYER ORDER

The **opacity** option controls the level of transparancy of each layer. Layers
are drawn bottom to top in the order they appear in the spec file.
`operation=list` prints that order with 1-based indices, which the **position**
option then uses to insert, replace or delete a layer (position `0` means the
end/top). See the *operation* and *position* parameters for details.

### MARGIN AROUND THE MAP

At render time the **margin** option adds a border of the given number of pixels
around the map. The margin is part of the *mapping area*: the **width** option
gives the width of the map plus margin, and a *solid* background layer fills the
whole mapping area (map and margin).

### PLACING ELEMENTS OUTSIDE THE MAP

The `at` placement of the raster legend, vector legend and image layers is given
in percent of the **mapping area** (`0`–`100` spans the map plus any margin,
origin bottom-left; so `0` is the outer edge of the margin). Values below `0` or
above `100` place the element *outside* the mapping area: to the left or below
for values `< 0`, to the right or above for values `> 100`. The output image is
then automatically enlarged on that side to make room.

The **width** option sets the mapping-area width (map plus margin). With
elements placed outside, the final PNG may be wider or taller.

The whole output image (the outer canvas, including the area around outside
elements) is transparent by default. Give it a colour with the **background**
option to fill it; unlike the *solid* layer, this covers the entire image, not
just the mapping area.

### FIGURE SIZE AND RESOLUTION

The output has two mutually exclusive sizing modes. In both, the size you give
refers to the **final cropped image** — including any legends or images placed
outside the mapping area — not just the map. The mapping area is sized so the
cropped figure fits the request, keeping its aspect ratio.

- **Pixel mode** (**width**, default 1200 px): total output width in pixels.
  Quick, good for web output.
- **Physical mode** (**figure_width** and/or **figure_height** in cm, at
  **dpi**): sizes the figure for direct insertion into a publication. Either
  dimension may be omitted; when both are given the more restrictive one wins.
  The saved PNG stores the resolution, so it is placed at the intended physical
  size. For example, `figure_width=12 dpi=300` yields a figure up to ~1417 px
  wide (12 cm at 300 dpi).

(When nothing is placed outside the map, the total equals the mapping area, so
the size is exact in a single render; with outside elements the mapping-area
width is solved from two trial renders so the cropped total matches the target.)

### FONTS

Typography is driven by a single **base font size** (the **fontsize** option,
in points; default 12). Every text element sizes itself as a *ratio* of that
base, so you set the overall size once and the parts stay in proportion:

| Element | Ratio option | Default |
|---|---|---|
| Labels | **label_font_scale** | 1 |
| Raster-legend labels | **legend_raster_font_scale** | 1 |
| Raster-legend title | **legend_raster_title_scale** | 1 |
| Vector legend | **legend_vector_font_scale** | 1 |
| Barscale | **barscale_font_scale** | 1 |
| Grid | **grid_font_scale** | 0.5 |

The size of a text element is the **base font size × its ratio**. So with
`fontsize=12`, grid labels (ratio 0.5) are 6 pt and legend labels (ratio 1) are
12 pt; changing **fontsize** to 16 rescales them together to 8 and 16 pt. These
point sizes are rendered at the output resolution (**dpi**), so one spec gives
the same-looking typography whether you render it small for the web or large for
print.

These points are close to typographic points as used in a word processor, so
`fontsize=12` gives roughly 12-point text, and you can pick sizes with that
familiar scale in mind.

Line widths and symbol sizes (vector **line_width** and point **size**, the
grid line width, and the vector-legend symbol size) are given in **points**,
the same unit as the fonts, so they stay in proportion with the text and keep
the same physical thickness at any **dpi**. At the default screen dpi one point
is one pixel, so `line_width=1` is a hairline on screen.

Note: for a *categorical* raster the `d.legend` module fits the class labels to
the legend box and may override the requested font size — a continuous raster
legend honours it.

### TEMPLATE SETTINGS

The style/layout options **font**, **fontsize**, **dpi**, **margin** and
**background** are stored in the spec itself (in a `settings` block), so a spec
works as a reusable template: set them once and every render of that spec looks
the same. They are set stickily — passing any of them on an `add`/`replace`
updates the stored value (last one wins). Passing the same option again at
**render** time *overrides* it for that one render only, without changing the
spec; everything else (the **output** file name and the sizing options
**width**/**figure_width**/**figure_height**) is always per-render.

To change a stored setting deliberately, use `operation=replace` (optionally
with no **type**, to edit only the settings); doing it through `operation=add`
still works but warns you that you are changing an existing template value.
`operation=list` prints the current settings.

## WORKSPACE IMPORT

An existing GRASS GUI map composition can be turned into a spec file with
*[m.printmap.gxw](m.printmap.gxw.md)*, which converts a workspace (`.gxw`) into
the spec file format used by this module. You can then adjust the layers and
render them.

## NOTES

*m.printmap* requires the Python [Pillow](https://python-pillow.org/) library.

*m.printmap* draws whatever the **current region and mask** are, so set those
with *g.region* and *r.mask* before rendering.

This module is specifically convenient to compose a map using the **GUI**: you
fill in each layer's options in its tab, without having to remember parameter
names. The examples are for the commmand line, but it works the same way from
the GUI. Build the spec one layer at a time, then later replace individual
layers (Example 2) to reuse a layout for a new map. Use whichever fits you.


## EXAMPLE

The examples use data from the North Carolina dataset, which you can download
from [here](https://grass.osgeo.org/download/data/) or in GRASS you can download
it using the *Download sample project* button in the *Data panel*.

### Example 1

Set the region and and build a spec file with four layers, then render it:

```sh
# region
g.region raster=elev_state_500m
```

Initiate the spec file and set a lightgrey solid background layer. The
`fontsize` here sets the base font size (points) stored in the template; every
text element sizes itself relative to it.

```sh
m.printmap new_spec=NC01.spec type=solid solid_color="#ececec" fontsize=11
```

Add the other layers.

```sh
# Add elevation layer
m.printmap spec=NC01.spec type=raster raster=elev_state_500m

# Add layer with county boundaries
m.printmap spec=NC01.spec type=vector vector=boundary_county \
    color="49:49:49" line_width=1 opacity=0.8

# Add legend (labels use the base font size; ratio defaults to 1)
m.printmap spec=NC01.spec type=legend_raster \
    legend_raster_map=elev_state_500m legend_raster_at=12,16,6,40 \
    legend_raster_flags=s,t

# Add logo
m.printmap spec=NC01.spec type=image image=grass-logo.png \
    image_at="5,30,90,99"

m.printmap spec=NC01.spec operation=render \
    output=m_printmap_01.png width=600 --overwrite
```

Print the list of layers that will make up the map.

```sh
m.printmap spec=NC01.spec operation=list
```

Render the map to png.

```sh
m.printmap spec=NC01.spec operation=render \
    output=m_printmap_01.png width=1200
```

The resulting map:

![](m_printmap_01.png)

### Example 2

Now, let's replace the elevation layer (which as we have seen above, is the 2nd
layer) and the legend (4th position) with the layer with average precipitation
in January 2000. This is part of the
[NC Climate data set](https://grass.osgeo.org/download/data/).

```sh
# Replace the elevantion with rainfall layer
m.printmap spec=NC01.spec type=raster \
           raster=2000_01_precip@climate_2000_2012 \
           operation=replace position=2

# Replace legend
m.printmap spec=NC01.spec type=legend_raster \
    legend_raster_map=2000_01_precip@climate_2000_2012 \
    legend_raster_at=12,16,6,40 \
    legend_raster_flags=s,t operation=replace position=4

# Render the map to PNG
m.printmap spec=NC01.spec operation=render \
    output=m_printmap_02.png width=600
```

The resulting map:

![](m_printmap_02.png)


### Example 3

Repeate example 1, but place the legend right of the mapping area and move the
logo to the left. We furthermore store a margin of 10 pixels in the template
(alongside the base font size), so it no longer has to be given at render time.
We'll create a new spec file *NC03.spec* for this.

```sh
# region
g.region raster=elev_state_500m

# Add layers to file; store base font size and margin in the template
m.printmap new_spec=NC03.spec type=solid solid_color="#ececec" \
    fontsize=11 margin=10
m.printmap spec=NC03.spec type=raster raster=elev_state_500m
m.printmap spec=NC03.spec type=vector vector=boundary_county \
    color="49:49:49" line_width=1 opacity=0.8

# Add legend
m.printmap spec=NC03.spec type=legend_raster \
    legend_raster_map=elev_state_500m legend_raster_at=5,95,101,104 \
    legend_raster_flags=s,t

# Add logo
m.printmap spec=NC03.spec type=image image=grass-logo.png \
    image_at="5,30,1,10"
```

Render the map to png (the stored margin is applied automatically).

```sh
m.printmap spec=NC03.spec operation=render \
    output=m_printmap_03.png width=600 --overwrite
```

The resulting map:

![](m_printmap_03.png)

### Example 4

Repeate the previous example, but place both the logo and the legend below the
mapping area, and set a general background to dark(er) grey.

```sh
# region
g.region raster=elev_state_500m

# Add layers to file; store base font size, margin and background in the template
m.printmap new_spec=NC04.spec type=solid solid_color="#ececec" \
    fontsize=11 margin=10 background="#dfdfdf"
m.printmap spec=NC04.spec type=raster raster=elev_state_500m
m.printmap spec=NC04.spec type=vector vector=boundary_county \
    color="49:49:49" line_width=1 opacity=0.8

# Add legend
m.printmap spec=NC04.spec type=legend_raster \
    legend_raster_map=elev_state_500m legend_raster_at=-7,-2,25,95 \
    legend_raster_flags=s,t

# Add logo
m.printmap spec=NC04.spec type=image image=grass-logo-horizontal.png \
    image_at="-14,-3,2,20"
```

Render the map to png (margin and background come from the template).

```sh
m.printmap spec=NC04.spec operation=render \
    output=m_printmap_04.png width=600 --overwrite
```

The resulting map:

![](m_printmap_04.png)


## SEE ALSO

*[m.printmap.gxw](m.printmap.gxw.md), [m.printws](m.printws.md),
[d.rast](d.rast.md), [d.vect](d.vect.md), [d.legend](d.legend.md),
[d.legend.vect](d.legend.vect.md), [d.out.file](d.out.file.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl),
[Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)


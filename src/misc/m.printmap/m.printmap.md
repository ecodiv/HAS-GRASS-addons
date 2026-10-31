## DESCRIPTION

*m.printmap* combines raster, vector, legend and label layers into a single PNG
image. Like in the interactive map display, each layer can be made partly
transparent. The description and settings of layers are written to a small JSON
**spec file**. They are build up one layer at a time and then render.

Working with the module has two phases. The first phase consists of one or more
steps to *Build* the spec file. Each run adds (or edits) one layer. The user
picks a layer **type**, fills in that type's options and runs it to append the
layerto the spec file. The second phase is to *render* the spec file
(`operation=render`) to a PNG.

Give the spec file with **new_spec** to start a new map, or **spec** to read or
update an existing one (these are mutually exclusive). Each **type** has its own
tab of options in the GUI. You can fill in more than one, but note that only the
options for the chosen type are used.

### Spec file

The module is designed to make building the spec file easy and then render it to
a PNG. The spec file is, however, also a plain, human-readable JSON file that
you can write or edit by hand in any text editor. This is handy for fine-tuning
the exact position of an element, or for treating one spec as a template and
producing many maps by only swapping the input map name(s).

When editing by hand, most settings are stored under the parameter name of the
underlying display command, so you can look up their meaning in that command's
manual. A vector layer uses the *d.vect* parameters (`map`, `type`, `color`,
`width`, ...), a raster legend the *d.legend* parameters (`raster`, `at`,
`digits`, `flags`, ...), a scale bar the *d.barscale* parameters, and so on. The
longer GUI option names (e.g. `legend_raster_digits`) are also accepted as
aliases and are converted to the canonical parameter name on the next write.

Flags follow the same convention as the command they are passed to, so
`legend_raster_flags=st` gives *d.legend* its `-s` and `-t` flags. A
comma-separated form (`s,t`) is accepted as well, and is normalized to the
concatenated form when the spec is written.

The exception is font size: each text element stores a `font_scale` (and the
raster legend a `title_scale`) that is a *ratio* of the template base font size
(see [Fonts](#fonts)). Template-level settings live in a `settings` block at the
top of the spec (see [Template settings](#template-settings)); a spec with no
settings is written as a bare JSON array of layers.

A small spec file looks like this:

```json
{
  "settings": {
    "fontsize": 12,
    "dpi": 300,
    "margin": 10
  },
  "layers": [
    {
      "kind": "raster",
      "map": "elevation",
      "opacity": 1.0
    },
    {
      "kind": "legend_raster",
      "raster": "elevation",
      "title": "Elevation",
      "at": [5, 50, 5, 8]
    }
  ]
}
```

### Layer types

The **type** option selects what a layer is:

- *solid*: a full-canvas color fill, used as a background or, at a low opacity,
  as a tint over the layers below.
- *raster*: a raster map.
- *vector*: a vector map (areas, lines or points).
- *labels*: text labels from a vector attribute column.
- *legend_raster*, *legend_vector*: a legend for a raster or vector map.
- *barscale*: a scale bar.
- *grid*: a coordinate grid.
- *image*: an external image (e.g. a logo or inset) placed in a box.

### Operations

The **operation** option selects what a run does. Operations that target an
existing layer use the **position** option (a 1-based index; `0` = the last
layer). See [Opacity and layer order](#opacity-and-layer-order).

- **add** (default): append a new layer, or insert it at **position**. Requires
  **type**.
- **delete**: remove the layer at **position**.
- **list**: print the template settings, the placeholders and the layers, bottom
  to top, with their positions.
- **settings**: store the template settings in the spec (see
  [Template settings](#template-settings)).
- **render**: draw the spec to the **output** PNG (see
  [Figure size and resolution](#figure-size-and-resolution)).

The spec is plain JSON, so to change a value can be done quickly and easily by
editing the json file. In addition, you can combine **delete** with **add** at a
**position** to remove a layer to put one back in a different place. To render
one layout with different input maps, use placeholders instead of editing at all
(see [Reusing a template](#reusing-a-template-placeholders)).

### OPACITY AND LAYER ORDER

The **opacity** option controls the level of transparancy of each layer. Layers
are drawn bottom to top in the order they appear in the spec file.
`operation=list` prints that order with 1-based indices, which the **position**
option then uses to insert or delete a layer (position `0` means the end/top).
See the *operation* and *position* parameters for details.

### MARGIN AROUND THE MAP

At render time the **margin** option adds a border of the given number of pixels
around the map. The margin is part of the *mapping area*: a *solid* background
layer fills the whole mapping area (map and margin), and the `at` percentages
are measured against it (see below).

### PLACING ELEMENTS OUTSIDE THE MAP

The `at` placement of the raster legend, vector legend and image layers is given
in percent of the **mapping area** (`0`–`100` spans the map plus any margin).
The origin is bottom-left. This means that values below `0` or above `100` place
the element *outside* the mapping area: to the left or below for values `< 0`,
to the right or above for values `> 100`. The output image is then automatically
enlarged on that side to make room.

Note that the requested output size (**width**, or **figure_width** /
**figure_height**) always refers to the *whole* image, including anything placed
outside. See [Figure size and resolution](#figure-size-and-resolution) for more
details.

The whole output image (the outer canvas, including the area around outside
elements) is transparent by default. Give it a colour with the **background**
option to fill it; unlike the *solid* layer, this covers the entire image, not
just the mapping area.

### FIGURE SIZE AND RESOLUTION

The output has two mutually exclusive sizing modes. In both, the size you give
refers to the **final image**, including any legends or images placed outside
the mapping area. 

- **Pixel mode** (**width**, default 1200 px): total output width in pixels.
- **Physical mode** (**figure_width** and/or **figure_height** in cm, at
  **dpi**). Either dimension may be omitted. When both are given the more
  restrictive one wins.

### FONTS

Typography is driven by a single **base font size** (the **fontsize** option, in
points; default 12). Individual text element can be adjusted by providing a
*ratio* of that base, so you set the overall size once and the parts stay in
proportion:

| Element              | Ratio option                  | Default |
|----------------------|-------------------------------|:-------:|
| Labels               | **label_font_scale**          | 1       |
| Raster-legend labels | **legend_raster_font_scale**  | 1       |
| Raster-legend title  | **legend_raster_title_scale** | 1       |
| Vector legend        | **legend_vector_font_scale**  | 1       |
| Barscale             | **barscale_font_scale**       | 1       |
| Grid                 | **grid_font_scale**           | 0.5     |

The size of a text element is the **base font size × its ratio**. So with
`fontsize=12`, grid labels (ratio 0.5) are 6 pt and legend labels (ratio 1) are
12 pt. The point sizes are rendered at the output resolution (**dpi**), so one
spec gives the same-looking typography whether you render it small for the web
or large for print. Note that point sizes are close to, but not exactly the same
as the typographic points used in a word processor.

Line widths and symbol sizes (vector **line_width** and point **size**, the grid
line width, and the vector-legend symbol size) are also given in **points**, so
they keep the same physical thickness at any **dpi**. At the default screen dpi
one point is one pixel, so `line_width=1` is a hairline on screen.

Note: for a *categorical* raster the `d.legend` module fits the class labels to
the legend box and may override the requested font size.

Note: for an integer (CELL) raster, `d.legend` draws a discrete category legend.
Ticks belong to the continuous legend, so `legend_raster_flags=t` has no effect
there; combine it with the smooth-gradient flag (`legend_raster_flags=st`) to get
a gradient with ticks. For a floating-point (FCELL/DCELL) raster, `t` works on
its own. Values given in **legend_raster_label_values** must lie within the
raster's range, otherwise `d.legend` stops with an "out of range" error. Use
**legend_raster_range** (`min,max`) to restrict the legend to a subset of the
map's data range.

### TEMPLATE SETTINGS

The style/layout options **font**, **fontsize**, **dpi**, **margin** and
**background** are stored in the `settings` block of the spec file, so a spec
works as a reusable template.

You can define the settings in the spec file using **operation=settings**. This
will add or update the options you pass. This means you can tweak one (e.g.
`operation=settings margin=25`) without restating the rest. Run it whenever you
like, including together with **new_spec** to start a template:

```sh
m.printmap new_spec=NC.json operation=settings fontsize=12 dpi=300 margin=10
```

At **render** time, passing one of these options *overrides* the stored value
for that one render only, without changing the spec. Everything else (the
**output** file name and the sizing options **width** / **figure_width** /
**figure_height**) is always per-render. `operation=list` prints the current
settings.

### REUSING A TEMPLATE: PLACEHOLDERS

One spec can serve many maps by writing `${name}` wherever a value should vary,
and filling those in at render time with the **replace** option. A placeholder
goes anywhere a value goes, and the same name may appear more than once. A reference to a raster layer can therefore refer to a raster and the corresponding raster legend:

```json
{
  "layers": [
    { "kind": "raster", "map": "${rast}" },
    { "kind": "legend_raster", "raster": "${rast}", "title": "${title}" }
  ]
}
```

Rendering it is then a single run:

```sh
m.printmap spec=NC.json operation=render output=precip.png width=600 \
    replace="rast=2000_01_precip@climate_2000_2012,title=Rainfall"
```

**replace** takes a comma-separated list of `name=value` pairs. The substitution
is made on the spec as it is read, not in the file, so the template keeps its
placeholders and can be rendered again with other values. `operation=list` names
the placeholders a spec contains, so you need not read the JSON to see what it
expects. Rendering a spec that still has an unfilled placeholder is an error,
rather than passing a literal `${name}` on to the display command.

A value that contains a comma has to be quoted, as the comma would otherwise
start the next pair:

```sh
replace="rast=precip,title='Rainfall, January 2000'"
```

A quote opens a quoted value only directly after the `=`, so an apostrophe
inside an unquoted value (`title=Cote d'Ivoire`) needs no escaping; for a value
with both an apostrophe and a comma, quote it with `"`. On the command line the
shell consumes the outer quotes, which is why the example has `"` outside and
`'` inside. In the GUI there is no shell, so type the inner form straight into
the field.

Numbers can be parameterized as well, but since the spec is JSON the field then
has to be written as a string. Note that a multi-value placement needs quoting
like any other value holding commas:

```json
{ "kind": "legend_raster", "raster": "${rast}", "at": "${pos}" }
```

```sh
replace="rast=elevation,pos='5,95,101,104'"
```

Part of a value works too, so `"at": "5,95,${right},104"` with
`replace="right=101"` moves one edge and leaves the rest of the placement in the
template.

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
the GUI. Build the spec one layer at a time, and use placeholders to reuse that
layout for other maps (Example 2). Use whichever fits you.


## EXAMPLE

The examples use data from the North Carolina dataset, which you can download
from [here](https://grass.osgeo.org/download/data/). Alternatively, in GRASS you
can download it using the *Download sample project* button in the *Data panel*.

### Example 1

Set the region and and build a spec file with four layers, then render it:

```sh
# region
g.region raster=elev_state_500m
```

Initiate the spec file, storing a base font size of 11 points in the template
(every text element sizes itself relative to it), and add a lightgrey solid
background layer.

```sh
m.printmap new_spec=NC01.json operation=settings fontsize=11
m.printmap spec=NC01.json type=solid solid_color="#ececec"
```

Add the other layers.

```sh
# Add elevation layer
m.printmap spec=NC01.json type=raster raster=elev_state_500m

# Add layer with county boundaries
m.printmap spec=NC01.json type=vector vector=boundary_county \
    color="49:49:49" line_width=0.1 opacity=0.8

# Add legend (labels use the base font size; ratio defaults to 1)
m.printmap spec=NC01.json type=legend_raster \
    legend_raster_map=elev_state_500m legend_raster_at=12,16,6,40 \
    legend_raster_flags=st

# Add logo
m.printmap spec=NC01.json type=image image=grass-logo.png \
    image_at="5,30,90,99"
```

Print the list of layers that will make up the map.

```sh
m.printmap spec=NC01.json operation=list
```

Render the map to png.

```sh
m.printmap spec=NC01.json operation=render \
    output=m_printmap_01.png width=650 --overwrite
```

The resulting map:

![](m_printmap_01.png)

### Example 2

The layout of Example 1 does not depend on *which* raster it shows, so it can be
built once and reused. We repeat it as *NC02.json*, but write `${rast}` instead
of a map name. Because the raster layer and its legend use the same placeholder,
one value sets both.

```sh
g.region raster=elev_state_500m

m.printmap new_spec=NC02.json operation=settings fontsize=11
m.printmap spec=NC02.json type=solid solid_color="#ececec"
m.printmap spec=NC02.json type=raster raster='${rast}'
m.printmap spec=NC02.json type=vector vector=boundary_county \
    color="49:49:49" line_width=0.1 opacity=0.8
m.printmap spec=NC02.json type=legend_raster \
    legend_raster_map='${rast}' legend_raster_at=12,16,6,40 \
    legend_raster_flags=st
m.printmap spec=NC02.json type=image image=grass-logo.png \
    image_at="5,30,90,99"
```

The single quotes around `${rast}` keep the shell from expanding it; in the GUI
you type `${rast}` into the field as it is. `operation=list` now reports the
placeholder alongside the layers:

```sh
m.printmap spec=NC02.json operation=list
```

Rendering it for the elevation map gives the same composition as Example 1:

```sh
m.printmap spec=NC02.json operation=render output=m_printmap_02a.png \
    width=600 replace="rast=elev_state_500m"
```

And rendering the same template for the average precipitation in January 2000
(part of the [NC Climate data set](https://grass.osgeo.org/download/data/))
gives a different map with no change to the spec file at all:

```sh
m.printmap spec=NC02.json operation=render output=m_printmap_02.png \
    width=600 replace="rast=2000_01_precip@climate_2000_2012"
```

The resulting map:

![](m_printmap_02.png)


### Example 3

Repeate example 1, but place the legend right of the mapping area and move the
logo to the left. We furthermore store a margin of 10 pixels in the template
(alongside the base font size), so it no longer has to be given at render time.
We'll create a new spec file *NC03.json* for this.

```sh
# region
g.region raster=elev_state_500m

# Store base font size and margin in the template, then add layers
m.printmap new_spec=NC03.json operation=settings fontsize=11 \
    margin=10 background="255:255:255"
m.printmap spec=NC03.json type=solid solid_color="#ececec"
m.printmap spec=NC03.json type=raster raster=elev_state_500m
m.printmap spec=NC03.json type=vector vector=boundary_county \
    color="49:49:49" line_width=1 opacity=0.8

# Add legend
m.printmap spec=NC03.json type=legend_raster \
    legend_raster_map=elev_state_500m legend_raster_at=5,95,101,104 \
    legend_raster_flags=st

# Add logo
m.printmap spec=NC03.json type=image image=grass-logo.png \
    image_at="5,30,1,10"
```

Render the map to png (the stored margin is applied automatically).

```sh
m.printmap spec=NC03.json operation=render \
    output=m_printmap_03.png width=600
```

The resulting map is shown below. 

![](m_printmap_03.png)


### Example 4

Repeate the previous example, but place both the logo and the legend below the
mapping area, and set a general background to dark(er) grey.

```sh
# region
g.region raster=elev_state_500m

# Store base font size, margin and background in the template, then add layers
m.printmap new_spec=NC04.json operation=settings \
    fontsize=11 margin=10 background="#dfdfdf"
m.printmap spec=NC04.json type=solid solid_color="#ececec"
m.printmap spec=NC04.json type=raster raster=elev_state_500m
m.printmap spec=NC04.json type=vector vector=boundary_county \
    color="49:49:49" line_width=1 opacity=0.8

# Add legend
m.printmap spec=NC04.json type=legend_raster \
    legend_raster_map=elev_state_500m legend_raster_at=-7,-2,25,95 \
    legend_raster_flags=st

# Add logo
m.printmap spec=NC04.json type=image image=grass-logo-horizontal.png \
    image_at="-14,-3,2,20"
```

Render the map to png (margin and background come from the template).

```sh
m.printmap spec=NC04.json operation=render \
    output=m_printmap_04.png width=600
```

The resulting map:

![](m_printmap_04.png)


### Example 5

Let's combine two raster layers, the elevation map and a relief map based on
that map, by changing the opacity of one of them. We'll update the spec file
created earlier.

```sh
# Create relief map
r.relief input=elev_state_500m@PERMANENT output=shadedrelief_state_500m zscale=10

# As a reminder, get the order of the layers of the spec file 4
m.printmap spec=NC04.json operation=list

# Add the relief layer just before the elevation layer. I.e., the elevation layer
# will be drawn on top of the shaded relief layer.
m.printmap spec=NC04.json type=raster raster=shadedrelief_state_500m \
    operation=add position=2
```

The elevation layer now sits at position 3, fully opaque, hiding the relief
underneath it. Make it half transparent by setting its `opacity` in
*NC04.json*:

```json
{
  "kind": "raster",
  "map": "elev_state_500m",
  "opacity": 0.5
}
```

Alternatively, take the layer out and add it back with the opacity you want:
`operation=delete position=3`, then `type=raster raster=elev_state_500m
operation=add position=3 opacity=0.5`.

```sh
# Print map
m.printmap spec=NC04.json operation=render \
    output=m_printmap_05.png width=600 --overwrite
```

The resulting map:

![](m_printmap_05.png)

## SEE ALSO

*[m.printmap.gxw](m.printmap.gxw.md), [m.printws](m.printws.md),
[d.rast](d.rast.md), [d.vect](d.vect.md), [d.legend](d.legend.md),
[d.legend.vect](d.legend.vect.md), [d.out.file](d.out.file.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl),
[Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)


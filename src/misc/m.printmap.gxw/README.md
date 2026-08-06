<h2>NAME</h2>
<em><b>m.printmap.gxw</b></em>  - Convert a GRASS workspace (.gxw) into an m.printmap spec file.
<h2>KEYWORDS</h2>
cartography, map, workspace, import

<h2>SYNOPSIS</h2>
<div id="name"><b>m.printmap.gxw</b><br></div>
<b>m.printmap.gxw --help</b><br>
<div id="synopsis"><b>m.printmap.gxw</b> <b>input</b>=<em>name</em> <b>output</b>=<em>name</em>  [--<b>overwrite</b>]  [--<b>help</b>]  [--<b>verbose</b>]  [--<b>quiet</b>]  [--<b>ui</b>] 
</div>

<div id="flags">
<h3>Flags:</h3>
<dl>
<dt><b>--overwrite</b></dt>
<dd>Allow output files to overwrite existing files</dd>
<dt><b>--help</b></dt>
<dd>Print usage summary</dd>
<dt><b>--verbose</b></dt>
<dd>Verbose module output</dd>
<dt><b>--quiet</b></dt>
<dd>Quiet module output</dd>
<dt><b>--ui</b></dt>
<dd>Force launching GUI dialog</dd>
</dl>
</div>

<div id="parameters">
<h3>Parameters:</h3>
<dl>
<dt><b>input</b>=<em>name</em>&nbsp;<b>[required]</b></dt>
<dd>GRASS workspace (.gxw) file to convert</dd>

<dt><b>output</b>=<em>name</em>&nbsp;<b>[required]</b></dt>
<dd>m.printmap spec file to create</dd>


## DESCRIPTION

*m.printmap.gxw* converts a GRASS workspace file (**input**, a `.gxw` saved from
the GUI) into an *[m.printmap](m.printmap.md)* spec file (**output**, a JSON
file). Each display command in the workspace is translated into the matching
*m.printmap* layer type, so an existing GUI map composition can be turned into a
reusable, editable spec and rendered with *m.printmap*.

## NOTES

The layers of the **first** display are converted. Their order is flipped to
*m.printmap*'s bottom-to-top convention, and overlays (legends, scale bar, grid)
are placed on top.

Only visible (checked) layers are converted.

Supported commands: *d.rast*, *d.vect*, *d.legend*, *d.legend.vect*,
*d.barscale* and *d.grid*. Any other command is reported and skipped.

A *d.vect* that also labels features (has an **attribute_column**) is split into
a **vector** layer plus a **labels** layer.

The workspace's display extent is not stored, because *m.printmap* renders the
current region. The equivalent *g.region* command is printed so the view can be
reproduced before rendering.

This addon was heavily inspired by and borrows from
*[m.printws](m.printws.md)*. That addon opens a workspace file and creates a map
sheet according to its visible contents. *m.printmap.gxw*, together with
*[m.printmap](m.printmap.md)*, offers a complementary approach: instead of
printing the workspace directly, it turns the workspace into an editable spec
file. You can then adjust the layers (order, opacity, or add new ones) and
render the result with *m.printmap*.

## EXAMPLE

```sh
m.printmap.gxw input=rotterdam.gxw output=rotterdam.json

# set the region as printed by the command above, then:

# list the layers
m.printmap spec=rotterdam.json operation=list

# Render the map
m.printmap spec=rotterdam.json operation=render output=rotterdam.png
```

## SEE ALSO

*[m.printmap](m.printmap.md), [m.printws](m.printws.md), [d.rast](d.rast.md),
[d.vect](d.vect.md), [d.legend](d.legend.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl),
[Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)


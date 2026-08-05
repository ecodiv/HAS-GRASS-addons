## DESCRIPTION

*m.printmap.gxw* converts a GRASS workspace file (**input**, a `.gxw` saved from
the GUI) into an *[m.printmap](m.printmap.md)* spec file (**output**). Each
display command in the workspace is translated into the matching *m.printmap*
layer type, so an existing GUI map composition can be turned into a reusable,
editable spec and rendered with *m.printmap*.

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
m.printmap.gxw input=rotterdam.gxw output=rotterdam.spec

# set the region as printed by the command above, then:

# list the layers
m.printmap spec=rotterdam.spec operation=list

# Render the map
m.printmap spec=rotterdam.spec operation=render output=rotterdam.png
```

## SEE ALSO

*[m.printmap](m.printmap.md), [m.printws](m.printws.md), [d.rast](d.rast.md),
[d.vect](d.vect.md), [d.legend](d.legend.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl),
[Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)


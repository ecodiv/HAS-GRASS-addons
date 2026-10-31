#!/usr/bin/env python3

##############################################################################
# MODULE:    m.printmap
#
# AUTHOR(S): Paulo van Breugel
#
# PURPOSE:   Composite GRASS raster, vector, legend and label layers into a
#            single PNG with per-layer opacity. Layers are stored in a JSON
#            spec file. The module both builds the spec file one layer at a
#            time and renders it.
#
# SPDX-FileCopyrightText: 2026 Paulo van Breugel
# SPDX-FileCopyrightText: Other GRASS authors
# SPDX-License-Identifier: GPL-2.0-or-later
#
##############################################################################

# %module
# % description: Composite raster, vector, legend and label layers into a PNG with per-layer opacity.
# % keyword: cartography
# % keyword: map
# % keyword: export
# % keyword: printing
# %end

# %option G_OPT_F_BIN_INPUT
# % key: spec
# % required: no
# % label: Layer spec file (existing)
# % description: Existing layer specification file to read or update
# % guisection: Main
# %end

# %option G_OPT_F_OUTPUT
# % key: new_spec
# % required: no
# % label: Layer spec file (new)
# % description: New layer specification file to create
# % guisection: Main
# %end

# %option
# % key: operation
# % type: string
# % required: yes
# % options: add,render,list,delete,settings
# % answer: add
# % description: Action to perform on the spec file (settings = set template settings)
# % guisection: Main
# %end

# %option
# % key: type
# % type: string
# % required: no
# % options: solid,raster,vector,labels,legend_raster,legend_vector,barscale,grid,image
# % description: Layer type (required for operation=add)
# % guisection: Main
# %end

# %option
# % key: position
# % type: string
# % required: no
# % answer: 0
# % description: 1-based layer index; 0 = at the end (append/last layer)
# % guisection: Main
# %end

# %option
# % key: opacity
# % type: double
# % required: no
# % answer: 1.0
# % options: 0.0-1.0
# % description: Layer opacity at compositing (0 = invisible, 1 = fully opaque)
# % guisection: Main
# %end

# %option G_OPT_CN
# % key: background
# % answer: none
# % label: Image background color
# % description: Background color of the output image, i.e. the outer canvas (operation=render)
# % guisection: Main
# %end

# %option G_OPT_F_OUTPUT
# % key: output
# % required: no
# % description: Output PNG file
# % guisection: Render
# %end

# %option
# % key: replace
# % type: string
# % required: no
# % multiple: yes
# % label: Placeholder substitutions as name=value
# % description: Replace ${name} throughout the spec when rendering, e.g. replace="rast=elevation,title=Elevation"
# % guisection: Render
# %end

# %option
# % key: width
# % type: integer
# % required: no
# % description: Total output width in pixels (default 1200; quick pixel-based output)
# % guisection: Render
# %end

# %option
# % key: figure_width
# % type: double
# % required: no
# % description: Figure width in cm (physical output; needs dpi)
# % guisection: Render
# %end

# %option
# % key: figure_height
# % type: double
# % required: no
# % description: Figure height in cm (physical output; needs dpi)
# % guisection: Render
# %end

# %option
# % key: dpi
# % type: integer
# % required: no
# % answer: 96
# % description: Resolution in dpi: sizes point-based fonts and line widths (both modes) and the figure in physical mode
# % guisection: Render
# %end

# %option
# % key: margin
# % type: integer
# % required: no
# % answer: 0
# % description: Margin in pixels around the map, filled by the solid layer (operation=render)
# % guisection: Render
# %end

# %option
# % key: font
# % type: string
# % required: no
# % answer: DejaVuSansCondensed
# % description: Global render font
# % guisection: Render
# %end

# %option
# % key: fontsize
# % type: double
# % required: no
# % answer: 12
# % description: Base font size in points; per-element sizes are ratios of this
# % guisection: Render
# %end

# %option G_OPT_C
# % key: solid_color
# % answer: white
# % description: Fill color for a solid layer
# % guisection: Solid
# %end

# %option G_OPT_R_INPUT
# % key: raster
# % required: no
# % description: Raster map to display
# % guisection: Raster
# %end

# %option
# % key: values
# % type: string
# % required: no
# % description: List of raster values to display (others transparent)
# % guisection: Raster
# %end

# %option G_OPT_V_INPUT
# % key: vector
# % required: no
# % description: Vector map to display
# % guisection: Vector
# %end

# %option
# % key: display_type
# % type: string
# % required: no
# % options: area,line,boundary,point,centroid
# % description: Vector feature type (default: auto-detected from the map, else area)
# % guisection: Vector
# %end

# %option G_OPT_CN
# % key: color
# % answer: black
# % description: Vector line color
# % guisection: Vector
# %end

# %option G_OPT_CN
# % key: fill_color
# % answer: none
# % description: Vector fill color
# % guisection: Vector
# %end

# %option
# % key: line_width
# % type: double
# % required: no
# % description: Vector line width in points (1 pt = 1 px at 96 dpi)
# % guisection: Vector
# %end

# %option G_OPT_V_CATS
# % key: cats
# % required: no
# % description: Category values to display
# % guisection: Vector
# %end

# %option G_OPT_DB_WHERE
# % key: where
# % required: no
# % description: WHERE condition of SQL statement to select features
# % guisection: Vector
# %end

# %option
# % key: icon
# % type: string
# % required: no
# % description: Point/centroid symbol (e.g. basic/circle)
# % gisprompt: old,symbol,symbol
# % guisection: Vector
# %end

# %option
# % key: size
# % type: double
# % required: no
# % description: Point/centroid symbol size in points (1 pt = 1 px at 96 dpi)
# % guisection: Vector
# %end

# %option G_OPT_V_INPUT
# % key: labels
# % required: no
# % description: Vector map to label
# % guisection: Labels
# %end

# %option
# % key: label_type
# % type: string
# % required: no
# % options: area,line,boundary,point,centroid
# % description: Feature type to label (default: auto-detected from the map, else area)
# % guisection: Labels
# %end

# %option G_OPT_DB_COLUMN
# % key: attribute_column
# % required: no
# % description: Attribute column to label with
# % guisection: Labels
# %end

# %option
# % key: label_font_scale
# % type: double
# % required: no
# % description: Label text size as a ratio of the base font size (default 1)
# % guisection: Labels
# %end

# %option G_OPT_C
# % key: label_color
# % answer: black
# % description: Label text color
# % guisection: Labels
# %end

# %option
# % key: label_font
# % type: string
# % required: no
# % description: Label font
# % guisection: Labels
# %end

# %option
# % key: xref
# % type: string
# % required: no
# % options: left,center,right
# % answer: center
# % description: Label horizontal justification
# % guisection: Labels
# %end

# %option
# % key: yref
# % type: string
# % required: no
# % options: top,center,bottom
# % answer: center
# % description: Label vertical justification
# % guisection: Labels
# %end

# %option G_OPT_V_CATS
# % key: label_cats
# % required: no
# % description: Category values to label
# % guisection: Labels
# %end

# %option G_OPT_DB_WHERE
# % key: label_where
# % required: no
# % description: WHERE condition of SQL statement to select features to label
# % guisection: Labels
# %end

# %option G_OPT_R_INPUT
# % key: legend_raster_map
# % required: no
# % description: Raster map the legend describes
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_title
# % type: string
# % required: no
# % description: Legend title
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_at
# % type: double
# % required: no
# % multiple: yes
# % description: Placement as bottom,top,left,right (percent of the map; <0 or >100 places it outside the map)
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_font_scale
# % type: double
# % required: no
# % description: Legend label size as a ratio of the base font size (default 1)
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_title_scale
# % type: double
# % required: no
# % description: Legend title size as a ratio of the base font size (default 1)
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_digits
# % type: integer
# % required: no
# % description: Number of digits after the decimal point
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_flags
# % type: string
# % required: no
# % label: Flags passed to d.legend, e.g. 'ct'
# % description: Any of v,c,t,n,s,f,d,b,l (as in d.legend; commas optional)
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_labelnum
# % type: integer
# % required: no
# % description: Number of labels for a smooth gradient legend
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_label_values
# % type: string
# % required: no
# % description: Specific values to label in the legend
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_use
# % type: string
# % required: no
# % description: List of raster values to draw in the legend
# % guisection: Raster legend
# %end

# %option
# % key: legend_raster_range
# % type: double
# % required: no
# % multiple: yes
# % description: Use a subset of the map range for the legend (min,max)
# % guisection: Raster legend
# %end

# %option G_OPT_CN
# % key: legend_raster_border_color
# % answer: none
# % description: Legend border color
# % guisection: Raster legend
# %end

# %option G_OPT_CN
# % key: legend_raster_bgcolor
# % answer: none
# % description: Legend box background color
# % guisection: Raster legend
# %end

# %option G_OPT_V_INPUT
# % key: legend_vector_map
# % required: no
# % description: Vector map the legend describes
# % guisection: Vector legend
# %end

# %option
# % key: legend_vector_at
# % type: double
# % required: no
# % multiple: yes
# % description: Top-left placement as x,y (percent of the map; <0 or >100 places it outside the map)
# % guisection: Vector legend
# %end

# %option
# % key: legend_vector_title
# % type: string
# % required: no
# % description: Legend title
# % guisection: Vector legend
# %end

# %option
# % key: legend_vector_columns
# % type: integer
# % required: no
# % description: Number of legend columns
# % guisection: Vector legend
# %end

# %option
# % key: legend_vector_symbol_size
# % type: integer
# % required: no
# % description: Legend symbol size in points (1 pt = 1 px at 96 dpi)
# % guisection: Vector legend
# %end

# %option
# % key: legend_vector_font_scale
# % type: double
# % required: no
# % description: Legend font size as a ratio of the base font size (default 1)
# % guisection: Vector legend
# %end

# %option
# % key: legend_vector_font
# % type: string
# % required: no
# % description: Legend font
# % guisection: Vector legend
# %end

# %option G_OPT_CN
# % key: legend_vector_bgcolor
# % answer: none
# % description: Background color (a color enables the background box)
# % guisection: Vector legend
# %end

# %option G_OPT_C
# % key: legend_vector_border_color
# % answer: black
# % description: Background border color
# % guisection: Vector legend
# %end

# %option
# % key: barscale_at
# % type: double
# % required: no
# % multiple: yes
# % description: Barscale placement as x,y (percent)
# % guisection: Barscale
# %end

# %option
# % key: barscale_style
# % type: string
# % required: no
# % description: Barscale style (see d.barscale)
# % guisection: Barscale
# %end

# %option
# % key: barscale_length
# % type: double
# % required: no
# % description: Barscale length (in map units)
# % guisection: Barscale
# %end

# %option
# % key: barscale_units
# % type: string
# % required: no
# % options: meters,kilometers,feet,miles,nautmiles
# % description: Barscale length units
# % guisection: Barscale
# %end

# %option
# % key: barscale_segment
# % type: integer
# % required: no
# % description: Number of barscale segments
# % guisection: Barscale
# %end

# %option
# % key: barscale_font_scale
# % type: double
# % required: no
# % description: Barscale font size as a ratio of the base font size (default 1)
# % guisection: Barscale
# %end

# %option
# % key: barscale_color
# % type: string
# % required: no
# % description: Barscale color
# % gisprompt: old,color,color
# % guisection: Barscale
# %end

# %option
# % key: barscale_bgcolor
# % type: string
# % required: no
# % description: Barscale background color
# % gisprompt: old,color_none,color
# % guisection: Barscale
# %end

# %option
# % key: barscale_text_position
# % type: string
# % required: no
# % options: under,over,left,right
# % description: Barscale text position
# % guisection: Barscale
# %end

# %option
# % key: barscale_flags
# % type: string
# % required: no
# % label: Flags passed to d.barscale, e.g. 'ft'
# % description: Any of f,t,n (as in d.barscale; commas optional)
# % guisection: Barscale
# %end

# %option
# % key: grid_size
# % type: string
# % required: no
# % description: Grid spacing (map units, or DDD:MM:SS with the g flag)
# % guisection: Grid
# %end

# %option
# % key: grid_color
# % type: string
# % required: no
# % description: Grid line color
# % gisprompt: old,color,color
# % guisection: Grid
# %end

# %option
# % key: grid_border_color
# % type: string
# % required: no
# % description: Grid border color
# % gisprompt: old,color_none,color
# % guisection: Grid
# %end

# %option
# % key: grid_text_color
# % type: string
# % required: no
# % description: Grid text color
# % gisprompt: old,color,color
# % guisection: Grid
# %end

# %option
# % key: grid_font_scale
# % type: double
# % required: no
# % description: Grid font size as a ratio of the base font size (default 0.5)
# % guisection: Grid
# %end

# %option
# % key: grid_width
# % type: double
# % required: no
# % description: Grid line width in points (1 pt = 1 px at 96 dpi)
# % guisection: Grid
# %end

# %option
# % key: grid_flags
# % type: string
# % required: no
# % label: Flags passed to d.grid, e.g. 'wc'
# % description: Any of a,g,w,c,d,f,n,b,t (as in d.grid; commas optional)
# % guisection: Grid
# %end

# %option G_OPT_F_BIN_INPUT
# % key: image
# % required: no
# % description: Image file to overlay (type=image)
# % guisection: Image
# %end

# %option
# % key: image_at
# % type: double
# % required: no
# % multiple: yes
# % description: Box as bottom,top,left,right (percent of the map; <0 or >100 places it outside); aspect kept, anchored lower-left
# % guisection: Image
# %end

# %rules
# % required: spec,new_spec
# % exclusive: spec,new_spec
# % exclusive: width,figure_width
# % exclusive: width,figure_height
# %end

import json
import os
import re
import sys
import tempfile

import grass.script as gs
from grass.exceptions import CalledModuleError

try:
    from PIL import Image, ImageColor
except ImportError:
    gs.fatal(
        "m.printmap requires the Python Pillow library. "
        "Install it with, e.g., 'pip install Pillow'."
    )


# ----------------------------------------------------------------------------
# Option keys per layer type {option_name: spec_key}. Every type is
# self-contained (its own map/color options) because they need to be exposed
# in separate GUI tabs.
# ----------------------------------------------------------------------------
_TYPE_OPTIONS = {
    "solid": {"solid_color": "color"},
    "raster": {"raster": "map", "values": "values"},
    "vector": {
        "vector": "map",
        "display_type": "type",
        "color": "color",
        "fill_color": "fill_color",
        "line_width": "width",
        "cats": "cats",
        "where": "where",
        "icon": "icon",
        "size": "size",
    },
    "labels": {
        "labels": "map",
        "label_type": "type",
        "attribute_column": "attribute_column",
        "label_font_scale": "font_scale",
        "label_color": "label_color",
        "label_font": "font",
        "xref": "xref",
        "yref": "yref",
        "label_cats": "cats",
        "label_where": "where",
    },
    "legend_raster": {
        "legend_raster_map": "raster",
        "legend_raster_title": "title",
        "legend_raster_at": "at",
        "legend_raster_font_scale": "font_scale",
        "legend_raster_title_scale": "title_scale",
        "legend_raster_digits": "digits",
        "legend_raster_flags": "flags",
        "legend_raster_labelnum": "labelnum",
        "legend_raster_label_values": "label_values",
        "legend_raster_use": "use",
        "legend_raster_range": "range",
        "legend_raster_border_color": "border_color",
        "legend_raster_bgcolor": "bgcolor",
    },
    "legend_vector": {
        "legend_vector_map": "map",
        "legend_vector_at": "at",
        "legend_vector_title": "title",
        "legend_vector_columns": "columns",
        "legend_vector_symbol_size": "symbol_size",
        "legend_vector_font_scale": "font_scale",
        "legend_vector_font": "font",
        "legend_vector_bgcolor": "bgcolor",
        "legend_vector_border_color": "border_color",
    },
    "barscale": {
        "barscale_at": "at",
        "barscale_style": "style",
        "barscale_length": "length",
        "barscale_units": "units",
        "barscale_segment": "segment",
        "barscale_font_scale": "font_scale",
        "barscale_color": "color",
        "barscale_bgcolor": "bgcolor",
        "barscale_text_position": "text_position",
        "barscale_flags": "flags",
    },
    "grid": {
        "grid_size": "size",
        "grid_color": "color",
        "grid_border_color": "border_color",
        "grid_text_color": "text_color",
        "grid_font_scale": "font_scale",
        "grid_width": "width",
        "grid_flags": "flags",
    },
    "image": {
        "image": "image",
        "image_at": "at",
    },
}

# Spec keys whose value is a list of floats (the legend "at" placement).
_FLOAT_LIST_KEYS = {"at"}

# Spec keys holding a d.* flag string.
_FLAG_KEYS = {"flags"}

# Flags accepted by the d.* command behind each layer type.
_FLAG_CHOICES = {
    "legend_raster": "vctnsfdbl",  # d.legend
    "barscale": "ftn",  # d.barscale
    "grid": "agwcdfnbt",  # d.grid
}


def normalize_flags(value, kind=None):
    """Return the flag string the d.* command expects. Flags may be given the
    way the underlying command takes them ('ct'), as a comma- or
    space-separated list ('c,t'), or a mix; duplicates are dropped. Unknown
    flags are refused, listing the valid ones for that layer type."""
    letters = [c for c in str(value).replace(",", " ").replace(";", " ").split()]
    flags = "".join(letters)
    allowed = _FLAG_CHOICES.get(kind, "")
    if allowed:
        unknown = sorted({c for c in flags if c not in allowed})
        if unknown:
            gs.fatal(
                "Unknown flag(s) '%s' for a '%s' layer. Valid flags are: %s."
                % ("".join(unknown), kind, ", ".join(allowed))
            )
    seen = []
    for char in flags:  # keep order, drop repeats
        if char not in seen:
            seen.append(char)
    return "".join(seen)

# Template-level style/layout settings. They live in the spec's 'settings'
# block (so a spec acts as a reusable template) and each is overridable at
# render time via the same-named option. 'fontsize' is the base point size that
# the per-element *_font_scale ratios multiply.
_SETTING_KEYS = ("font", "fontsize", "dpi", "margin", "background")


def _coerce_setting(key, value):
    """Store each template setting in its natural type."""
    if key in ("dpi", "margin"):
        return int(round(float(value)))
    if key == "fontsize":
        return float(value)
    return str(value)


def _provided_options():
    """The option keys the user set explicitly (GRASS passes both CLI and GUI
    fields as 'key=value' in argv), so we can tell an override from a default."""
    provided = set()
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and "=" in arg:
            provided.add(arg.split("=", 1)[0])
    return provided


# ----------------------------------------------------------------------------
# Spec file I/O
# ----------------------------------------------------------------------------
def read_spec(path):
    """Read the JSON spec file into (layers, settings). The spec is either a
    bare list of layers or an object {"settings": {...}, "layers": [...]}; both
    are accepted. Returns ([], {}) if the file is absent or empty."""
    if not os.path.exists(path):
        return [], {}
    with open(path, encoding="utf-8") as handle:
        text = handle.read().strip()
    if not text:
        return [], {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        gs.fatal(f"Could not parse spec file <{path}> as JSON: {error}")
    if isinstance(data, dict):
        settings = dict(data.get("settings", {}))
        layers = data.get("layers", [])
    elif isinstance(data, list):
        settings, layers = {}, data
    else:
        gs.fatal(f"Spec file <{path}> must be a JSON array of layers or an "
                 "object with 'settings' and 'layers'.")
    if not isinstance(layers, list):
        gs.fatal(f"Spec file <{path}> has a non-list 'layers' entry.")
    return [_normalize_layer(layer) for layer in layers], settings


def _normalize_layer(layer):
    """Accept the GUI option names as aliases in a hand-edited spec, translating
    them to the canonical spec keys the renderer uses, which are the underlying
    d.* parameter names (e.g. 'legend_raster_digits' -> 'digits'). Canonical
    keys take precedence."""
    if not isinstance(layer, dict):
        return layer
    for opt_name, spec_key in _TYPE_OPTIONS.get(layer.get("kind"), {}).items():
        if opt_name != spec_key and opt_name in layer:
            layer.setdefault(spec_key, layer.pop(opt_name))
    return layer


def _spec_to_json(data):
    """Pretty-print the spec as JSON, but keep short all-number arrays (like the
    'at' placement) on a single line instead of one element per line."""
    inline = {}

    def prep(obj):
        if isinstance(obj, dict):
            return {k: prep(v) for k, v in obj.items()}
        if isinstance(obj, list):
            if obj and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                           for x in obj):
                token = f"@@INLINE{len(inline)}@@"
                inline[token] = json.dumps(obj)
                return token
            return [prep(x) for x in obj]
        return obj

    text = json.dumps(prep(data), indent=2)
    for token, rep in inline.items():
        text = text.replace(json.dumps(token), rep)
    return text


def write_spec(path, layers, settings=None):
    """Write the spec back as pretty-printed JSON. With template settings
    present it is an object {"settings": ..., "layers": [...]}; otherwise a bare
    array of layers (keeping simple specs uncluttered)."""
    data = {"settings": settings, "layers": layers} if settings else layers
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(_spec_to_json(data) + "\n")


def capture_settings(settings, options, provided):
    """Update 'settings' with the explicitly-provided template settings (last
    value wins); options left at their default are untouched. Returns the keys
    that were updated."""
    updated = []
    for key in _SETTING_KEYS:
        if key in provided:
            settings[key] = _coerce_setting(key, options[key])
            updated.append(key)
    return updated


def _coerce_layer_value(spec_key, value, kind=None):
    """Coerce a raw option string into the value stored under a spec key
    (float list for 'at', normalized flag string for 'flags', else the
    string)."""
    if spec_key in _FLOAT_LIST_KEYS:
        return [float(v) for v in value.split(",")]
    if spec_key in _FLAG_KEYS:
        return normalize_flags(value, kind)
    return value


def build_layer(options):
    """Build one layer dict from the module options for the chosen type."""
    kind = options["type"]
    if not kind:
        gs.fatal("This operation requires the 'type' option.")

    layer = {"kind": kind}
    for opt_name, spec_key in _TYPE_OPTIONS[kind].items():
        value = options.get(opt_name, "")
        if value != "":
            layer[spec_key] = _coerce_layer_value(spec_key, value, kind)

    # opacity always carries a meaningful default and applies to every type.
    layer["opacity"] = float(options["opacity"])

    _validate_layer(kind, layer)
    return layer


def _validate_layer(kind, layer):
    """Validate that types needing an input map (and column) got one."""
    # The input map key follows the underlying command: d.legend uses 'raster'.
    map_key = "raster" if kind == "legend_raster" else "map"
    needs_map = {"raster", "vector", "labels", "legend_raster", "legend_vector"}
    if kind in needs_map and map_key not in layer:
        gs.fatal(f"Layer type '{kind}' requires an input map.")
    if kind == "labels" and "attribute_column" not in layer:
        gs.fatal("Layer type 'labels' requires the 'attribute_column' option.")
    if kind == "grid" and "size" not in layer:
        gs.fatal("Layer type 'grid' requires the 'grid_size' option.")
    if kind == "image":
        if "image" not in layer:
            gs.fatal("Layer type 'image' requires the 'image' file option.")
        if "at" not in layer:
            gs.fatal("Layer type 'image' requires the 'image_at' placement.")


# ----------------------------------------------------------------------------
# Placeholders
#
# A spec can stand in for many maps by writing ${name} wherever a value should
# vary, and filling those in at render time with replace=. Substitution happens
# on the parsed spec in memory, on the render path only: the operations that
# write the spec back must never see substituted values, or the template would
# lose its placeholders.
# ----------------------------------------------------------------------------
_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")


def _split_entries(value):
    """Split the 'replace' option into its name=value entries. Commas separate
    entries, but a value may contain one by quoting it
    (title='Rainfall, Jan 2000'). A quote opens a quoted value only directly
    after the '=', so an apostrophe in an unquoted value (Cote d'Ivoire) is
    taken literally."""
    entries, current, quote, value_at = [], [], None, None
    for char in value:
        if quote:
            if char == quote:
                quote = None
            else:
                current.append(char)
        elif char == "=" and value_at is None:
            current.append(char)
            value_at = len(current)
        elif char in "\"'" and value_at == len(current):
            quote = char
        elif char == ",":
            entries.append("".join(current))
            current, value_at = [], None
        else:
            current.append(char)
    if quote:
        gs.fatal(f"Unbalanced {quote} quote in replace=<{value}>.")
    entries.append("".join(current))
    return entries


def parse_replacements(value):
    """Parse the 'replace' option into a {name: value} mapping. A repeated name
    is refused rather than silently resolved, as it is nearly always a typo."""
    replacements = {}
    for entry in _split_entries(value):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            gs.fatal(f"replace entry <{entry}> is not of the form name=value.")
        name, _, replacement = entry.partition("=")
        name = name.strip()
        if not name:
            gs.fatal(f"replace entry <{entry}> has an empty placeholder name.")
        if name in replacements:
            gs.fatal(f"Placeholder <{name}> is given more than once in replace.")
        replacements[name] = replacement.strip()
    return replacements


def substitute(obj, replacements):
    """Return a copy of a parsed spec with every ${name} in a string replaced
    by its value. Only values are rewritten, never dict keys: those are the
    spec's own parameter names. A token with no replacement is left as it is,
    so find_placeholders can report it."""
    if isinstance(obj, dict):
        return {key: substitute(value, replacements)
                for key, value in obj.items()}
    if isinstance(obj, list):
        return [substitute(item, replacements) for item in obj]
    if isinstance(obj, str):
        return _PLACEHOLDER.sub(
            lambda match: replacements.get(match.group(1), match.group(0)), obj
        )
    return obj


def find_placeholders(obj):
    """The set of ${name} names present in a parsed spec. Used both to list a
    template's placeholders and to refuse a render that left one unfilled."""
    found = set()
    if isinstance(obj, dict):
        for value in obj.values():
            found |= find_placeholders(value)
    elif isinstance(obj, list):
        for item in obj:
            found |= find_placeholders(item)
    elif isinstance(obj, str):
        found.update(_PLACEHOLDER.findall(obj))
    return found


def _bad_value(key, value, where):
    """Message for a value that cannot be converted to the type the renderer
    needs, pointing at the substitution that most likely produced it."""
    return (f"'{key}' of {where} has the value <{value}>, which is not valid "
            "here. Check the replace= value substituted into it.")


def recoerce_spec(layers, settings):
    """Restore the value types the renderer expects. A parameterized numeric
    field has to be a string in the template ("at": "${pos}"), so after
    substitution it holds e.g. "5,95,101,104". Re-apply the conversions
    build_layer and capture_settings make, so a substituted value is accepted
    exactly as the same value passed on the command line would be. The
    conversions are idempotent, so values that are already numbers are
    unchanged."""
    for index, layer in enumerate(layers, start=1):
        kind = layer.get("kind")
        where = f"layer {index} ({kind})"
        for key in _FLOAT_LIST_KEYS:
            if isinstance(layer.get(key), str):
                try:
                    layer[key] = _coerce_layer_value(key, layer[key], kind)
                except ValueError:
                    gs.fatal(_bad_value(key, layer[key], where))
        if isinstance(layer.get("opacity"), str):
            try:
                layer["opacity"] = float(layer["opacity"])
            except ValueError:
                gs.fatal(_bad_value("opacity", layer["opacity"], where))
    for key in _SETTING_KEYS:
        if key in settings:
            try:
                settings[key] = _coerce_setting(key, settings[key])
            except (TypeError, ValueError):
                gs.fatal(_bad_value(key, settings[key], "the template settings"))


def resolve_placeholders(layers, settings, replace):
    """Fill the spec's placeholders from the 'replace' option and return the
    spec ready to render. Refuses a spec that still has an unfilled
    placeholder: left in place it would reach the d.* command as a literal
    '${name}' and fail there with a far less obvious message."""
    if replace:
        replacements = parse_replacements(replace)
        present = find_placeholders(layers) | find_placeholders(settings)
        unused = sorted(set(replacements) - present)
        if unused:
            gs.warning("replace= gives a value for %s, which the spec does not "
                       "use." % ", ".join(unused))
        layers = substitute(layers, replacements)
        settings = substitute(settings, replacements)
    unfilled = sorted(find_placeholders(layers) | find_placeholders(settings))
    if unfilled:
        gs.fatal(
            "The spec has unfilled placeholder(s): %s. Give a value for each "
            "with replace=, e.g. replace=\"%s=...\"."
            % (", ".join(unfilled), unfilled[0])
        )
    recoerce_spec(layers, settings)
    return layers, settings


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------
def apply_opacity(img, opacity):
    """Apply an opacity factor (0.0 to 1.0) to an RGBA image."""
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    alpha = alpha.point(lambda p: int(p * opacity))
    img.putalpha(alpha)
    return img


# Layer types whose 'at' placement may fall outside the map (0-100).
# Their 'at' is relative to the MAP area, origin bottom-left.
_OUTSIDE_KINDS = {"image", "legend_raster", "legend_vector"}


def compute_layout(width_image, layers, margin=0):
    """Canvas geometry as three nested rectangles:

    * frame  - the mapping area (map + 'margin' px on each side). It is the
      0-100% reference for 'at' and what a 'solid' layer fills. Its width is
      'width_image'.
    * inner  - the actual map, inset by 'margin', where map layers render.
    * canvas - the full image; grows beyond the frame for image/legend layers
      placed outside 0-100.
    """
    region = gs.region()
    margin = max(0, int(margin))
    frame_w = int(width_image)
    inner_w = max(1, frame_w - 2 * margin)
    inner_h = int(
        round(inner_w * (region["n"] - region["s"]) / (region["e"] - region["w"]))
    )
    frame_h = inner_h + 2 * margin

    xs, ys = [0.0, 100.0], [0.0, 100.0]
    legend_right = legend_below = False
    for layer in layers:
        kind = layer.get("kind")
        at = layer.get("at")
        if not at or kind not in _OUTSIDE_KINDS:
            continue
        if len(at) == 4:  # bottom, top, left, right
            ys += [at[0], at[1]]
            xs += [at[2], at[3]]
            right_edge, below_edge = at[3], at[0]
        else:  # legend_vector: x, y
            xs.append(at[0])
            ys.append(at[1])
            right_edge, below_edge = at[0], at[1]
        if kind in ("legend_raster", "legend_vector"):
            legend_right = legend_right or right_edge > 100
            legend_below = legend_below or below_edge < 0

    left_px = int(round(max(0.0, -min(xs)) / 100.0 * frame_w))
    right_px = int(round(max(0.0, max(xs) - 100.0) / 100.0 * frame_w))
    bottom_px = int(round(max(0.0, -min(ys)) / 100.0 * frame_h))
    top_px = int(round(max(0.0, max(ys) - 100.0) / 100.0 * frame_h))

    # d.legend draws its labels beyond the colour-bar box. A legend
    # in the right/bottom margin would have its labels clipped.
    # We need therefore to reserve extra room. The excess space we
    # create here will be cropped to fit the actual content.
    # todo: test if the initial space is enough
    if legend_right:
        right_px += int(round(0.45 * inner_w))
    if legend_below:
        bottom_px += int(round(0.20 * inner_h))

    return {
        "frame_w": frame_w,
        "frame_h": frame_h,
        "frame_x0": left_px,
        "frame_y0": top_px,
        "inner_w": inner_w,
        "inner_h": inner_h,
        "inner_x0": left_px + margin,
        "inner_y0": top_px + margin,
        "left_px": left_px,
        "bottom_px": bottom_px,
        "canvas_w": frame_w + left_px + right_px,
        "canvas_h": frame_h + top_px + bottom_px,
        "margin": margin,
    }


def setup_grass_render(layout, font):
    """Configure GRASS Cairo rendering env vars for the full (possibly
    enlarged) canvas."""
    os.environ["GRASS_RENDER_IMMEDIATE"] = "cairo"
    os.environ["GRASS_RENDER_WIDTH"] = str(layout["canvas_w"])
    os.environ["GRASS_RENDER_HEIGHT"] = str(layout["canvas_h"])
    os.environ["GRASS_RENDER_FILE_READ"] = "FALSE"
    os.environ["GRASS_RENDER_TRANSPARENT"] = "TRUE"
    os.environ["GRASS_FONT"] = font
    os.environ["GRASS_REGION"] = gs.region_env()


def _map_frame(layout):
    """GRASS_RENDER_FRAME (top,bottom,left,right px) for the inner map."""
    top, left = layout["inner_y0"], layout["inner_x0"]
    return f"{top},{top + layout['inner_h']},{left},{left + layout['inner_w']}"


def _full_frame(layout):
    """GRASS_RENDER_FRAME for the whole canvas."""
    return f"0,{layout['canvas_h']},0,{layout['canvas_w']}"


def _translate_at(at, layout):
    """Translate an 'at' from mapping-area percent (may be <0 or >100) to
    whole-canvas percent, so d.legend / d.legend.vect place it correctly in
    the enlarged canvas."""
    fw, fh, cw, ch = (
        layout["frame_w"],
        layout["frame_h"],
        layout["canvas_w"],
        layout["canvas_h"],
    )
    lpx, bpx = layout["left_px"], layout["bottom_px"]

    def cx(v):
        return (lpx + v / 100.0 * fw) / cw * 100.0

    def cy(v):
        return (bpx + v / 100.0 * fh) / ch * 100.0

    if len(at) == 4:
        return [cy(at[0]), cy(at[1]), cx(at[2]), cx(at[3])]
    return [cx(at[0]), cy(at[1])]


def parse_color(spec):
    """Parse a color into an RGBA tuple for Pillow. Accepts GRASS 'R:G:B' and
    'R:G:B:A' formats as well as anything ImageColor understands (#hex, named
    colors, rgb(...))."""
    spec = spec.strip()
    if ":" in spec:
        try:
            values = [int(part) for part in spec.split(":")]
        except ValueError:
            gs.fatal(f"Invalid color specifier: {spec}")
        if len(values) == 3:
            values.append(255)
        if len(values) != 4:
            gs.fatal(f"Invalid color specifier: {spec}")
        return tuple(values)
    rgba = ImageColor.getrgb(spec)
    return rgba if len(rgba) == 4 else rgba + (255,)


def _font_px(points, layout):
    """Convert a point font size to pixels at the render resolution
    (font_px = points * dpi / 96)."""
    return max(1, int(round(float(points) * layout.get("dpi_scale", 1.0))))


def _ratio_font_px(layer, layout, key="font_scale", default=1.0):
    """Pixel font size for an element: the template base font size scaled by
    the element's ratio (spec key 'key', default 'default'), then converted to
    pixels at the render resolution."""
    base = layout.get("base_fontsize", 12.0)
    ratio = float(layer.get(key, default))
    return _font_px(base * ratio, layout)


def _scale_px(value, layout, as_int=False):
    """Convert a point-valued size (line width, symbol size) to pixels at the
    render resolution (px = points * dpi / 96), the same scale as fonts, so
    lines and symbols keep the same physical thickness as the text. At 96 dpi
    one point is one pixel."""
    scaled = max(1.0, float(value) * layout.get("dpi_scale", 1.0))
    return int(round(scaled)) if as_int else round(scaled, 3)


def detect_vector_types(mapname):
    """Return a d.vect 'type' string derived from the map's topology, or None
    if it could not be determined. Areas take precedence over their component
    boundaries and centroids so polygon maps render as filled areas."""
    try:
        info = gs.parse_command("v.info", map=mapname, flags="t")
    except CalledModuleError:
        return None

    def count(key):
        try:
            return int(info.get(key, 0))
        except (TypeError, ValueError):
            return 0

    types = []
    if count("areas"):
        types.append("area")
    else:
        if count("centroids"):
            types.append("centroid")
        if count("boundaries"):
            types.append("boundary")
    if count("points"):
        types.append("point")
    if count("lines"):
        types.append("line")
    return ",".join(types) if types else None


def render_layer(layer, outfile, layout):
    """Render one layer to a canvas-sized PNG. Map layers are confined to the
    map rectangle; image and legend layers may be placed outside it."""
    kind = layer["kind"]
    cw, ch = layout["canvas_w"], layout["canvas_h"]
    fw, fh = layout["frame_w"], layout["frame_h"]
    fx0, fy0 = layout["frame_x0"], layout["frame_y0"]

    if kind == "solid":
        # A solid fills the mapping area (map + margin).
        rgba = parse_color(layer.get("color", "#ffffff"))
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(Image.new("RGBA", (fw, fh), rgba), (fx0, fy0))
        canvas.save(outfile)
        return

    if kind == "image":
        # 'at' is bottom,top,left,right in percent of the mapping area, origin
        # bottom-left (may be <0 or >100). The image keeps its aspect ratio,
        # is fit inside the box, and is anchored at the box's LOWER-LEFT corner.
        bottom, top, left, right = layer["at"]
        box_left = int(round(fx0 + left / 100.0 * fw))
        box_right = int(round(fx0 + right / 100.0 * fw))
        box_bottom = int(round(fy0 + (100.0 - bottom) / 100.0 * fh))  # y from top
        box_top = int(round(fy0 + (100.0 - top) / 100.0 * fh))
        box_w = max(1, box_right - box_left)
        box_h = max(1, box_bottom - box_top)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        fig = Image.open(layer["image"]).convert("RGBA")
        fig.thumbnail((box_w, box_h))  # fit inside the box, keep aspect ratio
        canvas.paste(fig, (box_left, box_bottom - fig.height), fig)
        canvas.save(outfile)
        return

    os.environ["GRASS_RENDER_FILE"] = outfile
    # Legends may sit outside the map, so they get the whole canvas; every
    # other display layer is confined to the inner map rectangle.
    if kind in ("legend_raster", "legend_vector"):
        os.environ["GRASS_RENDER_FRAME"] = _full_frame(layout)
    else:
        os.environ["GRASS_RENDER_FRAME"] = _map_frame(layout)
    gs.run_command("d.erase")

    if kind == "raster":
        params = {"map": layer["map"]}
        if "values" in layer:
            params["values"] = layer["values"]
        gs.run_command("d.rast", **params)

    elif kind == "vector":
        # An explicit 'type' always wins; otherwise auto-detect from the map's
        # topology and fall back to 'area' when nothing could be determined.
        vtype = layer.get("type") or detect_vector_types(layer["map"]) or "area"
        params = {
            "map": layer["map"],
            "type": vtype,
            "color": layer.get("color", "black"),
            "fill_color": layer.get("fill_color", "none"),
            "width": _scale_px(layer.get("width", 1), layout, as_int=True),
        }
        if "size" in layer:  # point symbol size scales like line width
            params["size"] = _scale_px(layer["size"], layout)
        for key in ("cats", "where", "icon"):
            if key in layer:
                params[key] = layer[key]
        gs.run_command("d.vect", **params)

    elif kind == "labels":
        ltype = layer.get("type") or detect_vector_types(layer["map"]) or "area"
        params = {
            "map": layer["map"],
            "type": ltype,
            "attribute_column": layer["attribute_column"],
            "label_size": _ratio_font_px(layer, layout),
            "label_color": layer.get("label_color", "black"),
            "font": layer.get("font", "arial"),
            "xref": layer.get("xref", "center"),
            "yref": layer.get("yref", "center"),
            "fill_color": "none",
            "color": "none",
        }
        for key in ("cats", "where"):
            if key in layer:
                params[key] = layer[key]
        gs.run_command("d.vect", **params)

    elif kind == "legend_raster":
        # Pass only what the user set, for the rest the default
        # values are used.
        params = {"raster": layer["raster"]}
        flags = normalize_flags(layer.get("flags", ""), kind)
        if flags:
            params["flags"] = flags
        params["fontsize"] = _ratio_font_px(layer, layout)
        if "title" in layer:
            params["title_fontsize"] = _ratio_font_px(layer, layout,
                                                      "title_scale")
        for key in (
            "title",
            "use",
            "labelnum",
            "label_values",
            "range",
            "digits",
            "border_color",
            "bgcolor",
        ):
            if key in layer:
                params[key] = layer[key]
        if "at" in layer:
            params["at"] = _translate_at(layer["at"], layout)
        gs.run_command("d.legend", **params)

    elif kind == "legend_vector":
        params = {
            "map": layer["map"],
            "fontsize": _ratio_font_px(layer, layout),
        }
        if "at" in layer:
            params["at"] = _translate_at(layer["at"], layout)
        if "symbol_size" in layer:
            params["symbol_size"] = _scale_px(layer["symbol_size"], layout,
                                              as_int=True)
        for key in ("title", "columns", "font"):
            if key in layer:
                params[key] = layer[key]
        # d.legend.vect draws the background box only with -b; a chosen
        # bgcolor/border color implies the user wants that box.
        bgcolor = layer.get("bgcolor", "none")
        border_color = layer.get("border_color", "none")
        if bgcolor != "none" or border_color != "none":
            params["flags"] = "b"
            if bgcolor != "none":
                params["bgcolor"] = bgcolor
            if border_color != "none":
                params["border_color"] = border_color
        gs.run_command("d.legend.vect", **params)

    elif kind == "barscale":
        params = {}
        for key in (
            "at",
            "style",
            "length",
            "units",
            "segment",
            "color",
            "bgcolor",
            "text_position",
        ):
            if key in layer:
                params[key] = layer[key]
        params["fontsize"] = _ratio_font_px(layer, layout)
        if "flags" in layer:
            params["flags"] = normalize_flags(layer["flags"], kind)
        gs.run_command("d.barscale", **params)

    elif kind == "grid":
        params = {"size": layer["size"]}
        if "width" in layer:  # grid line width scales like fonts
            params["width"] = _scale_px(layer["width"], layout)
        for key in ("color", "border_color", "text_color"):
            if key in layer:
                params[key] = layer[key]
        params["fontsize"] = _ratio_font_px(layer, layout, default=0.5)
        if "flags" in layer:
            params["flags"] = normalize_flags(layer["flags"], kind)
        gs.run_command("d.grid", **params)

    else:
        gs.fatal(f"Unknown layer type: {kind}")


def _composite_cropped(layers, outfiles, crop):
    """Alpha-composite the layers (honouring per-layer opacity) and crop to the
    (left, top, right, bottom) content box. Returns the RGBA image."""
    result = None
    for layer, path in zip(layers, outfiles):
        img = apply_opacity(Image.open(path).convert("RGBA"),
                            float(layer.get("opacity", 1.0)))
        result = img if result is None else Image.alpha_composite(result, img)
    if result is None:
        gs.fatal("Spec file has no layers to render.")
    return result.crop(crop)


def _render_once(layers, mapping_width, font, margin, dpi, base_fontsize):
    """Render every layer at the given mapping-area width and return the
    cropped, composited RGBA image (background not yet applied). 'dpi' sets the
    point-to-pixel scale for fonts (font_px = points * dpi / 96); 'base_fontsize'
    is the point size the per-element *_font_scale ratios multiply."""
    layout = compute_layout(mapping_width, layers, margin)
    layout["dpi_scale"] = (dpi or 300) / 96.0
    layout["base_fontsize"] = base_fontsize
    setup_grass_render(layout, font)
    # Crop box: start from the mapping area (map + margin), then grow to include
    # every layer's drawn content (so reserved-but-empty space is trimmed off).
    crop = [
        layout["frame_x0"],
        layout["frame_y0"],
        layout["frame_x0"] + layout["frame_w"],
        layout["frame_y0"] + layout["frame_h"],
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        outfiles = []
        for index, layer in enumerate(layers):
            outfile = os.path.join(tmpdir, f"layer_{index:03d}.png")
            render_layer(layer, outfile, layout)
            outfiles.append(outfile)
            if layer.get("kind") != "solid":  # solid fills the whole canvas
                bbox = Image.open(outfile).getbbox()
                if bbox:
                    crop[0] = min(crop[0], bbox[0])
                    crop[1] = min(crop[1], bbox[1])
                    crop[2] = max(crop[2], bbox[2])
                    crop[3] = max(crop[3], bbox[3])
        return _composite_cropped(layers, outfiles, tuple(crop))


def _cm_to_px(cm, dpi):
    return int(round(cm / 2.54 * dpi))


def _has_outside(layers):
    """True if any layer is placed (partly) beyond the 0-100 mapping area, so
    the cropped total is larger than the mapping width and must be solved for.
    When false, the cropped total width equals the mapping width exactly."""
    for layer in layers:
        if layer.get("kind") not in _OUTSIDE_KINDS:
            continue
        at = layer.get("at")
        if not at:
            continue
        coords = at if len(at) == 4 else at[:2]
        if min(coords) < 0 or max(coords) > 100:
            return True
    return False


def _solve_mapping_width(render, target_w, target_h):
    """Find the mapping-area width whose cropped total meets the binding target,
    then return that render. The cropped total is exactly linear in the mapping
    width per axis (``total = a*W + b``: the map and colour bar scale with W,
    while outside label text and margins add a fixed ``b``). Two sample renders
    fit ``a`` and ``b``; a third renders at the solved width. Returns the fitted
    image; a sample is reused when it already sits at the solved width."""
    w1 = target_w or target_h or 1200
    w2 = max(1, int(round(0.6 * w1)))
    s1, s2 = render(w1), render(w2)
    best = None
    for target, axis in ((target_w, 0), (target_h, 1)):
        if not target:
            continue
        a = (s1.size[axis] - s2.size[axis]) / (w1 - w2)
        b = s1.size[axis] - a * w1
        solved = (target - b) / a if a else w1
        best = solved if best is None else min(best, solved)
    if not best or best <= 0:  # fixed text alone exceeds the target
        return min((s1, s2), key=lambda s: s.size[0])
    width = max(1, int(round(best)))
    if width == w1:
        return s1
    if width == w2:
        return s2
    return render(width)


def render_spec(layers, outputfile, font, margin=0, background="none",
                width=None, figure=None, dpi=None, base_fontsize=12.0):
    """Render the spec to a PNG. Both modes size the *total cropped figure*:
    pixel mode from 'width' (px); physical mode from 'figure' (width_cm,
    height_cm; either may be None) at 'dpi'. The mapping-area width is solved so
    the cropped output fits the target, keeping aspect ratio. 'base_fontsize'
    (points) is the reference the per-element *_font_scale ratios multiply."""
    if not layers:
        gs.fatal("Spec file has no layers to render.")

    # Target TOTAL size in pixels (either axis may be unconstrained).
    if figure is not None:
        target_w = _cm_to_px(figure[0], dpi) if figure[0] else None
        target_h = _cm_to_px(figure[1], dpi) if figure[1] else None
    else:
        target_w = int(width) if width else 1200
        target_h = None

    def render(mapping_width):
        return _render_once(layers, mapping_width, font, margin, dpi,
                            base_fontsize)

    # Fast path: with nothing outside, the cropped total width equals the
    # mapping width, so a width target is met by a single render (the common
    # case). Otherwise solve the mapping width from two samples.
    if target_w and not target_h and not _has_outside(layers):
        image = render(target_w)
    else:
        image = _solve_mapping_width(render, target_w, target_h)

    if (target_w and image.size[0] > target_w + 1) or (
        target_h and image.size[1] > target_h + 1
    ):
        gs.warning(
            "Could not fit the output within the requested size; the fixed "
            "text/margin pixels may leave no room for the map."
        )

    save_kwargs = {"dpi": (dpi, dpi)} if figure is not None else {}
    if background and background != "none":
        canvas = Image.new("RGBA", image.size, parse_color(background))
        image = Image.alpha_composite(canvas, image)
    image.save(outputfile, **save_kwargs)


# ----------------------------------------------------------------------------
# Operations
# ----------------------------------------------------------------------------
def summarize(layer):
    """One-line human summary of a layer for operation=list."""
    kind = layer.get("kind", "?")
    target = (
        layer.get("map")
        or layer.get("raster")
        or layer.get("image")
        or layer.get("size")
        or layer.get("color")
        or ""
    )
    opacity = layer.get("opacity", 1.0)
    return f"{kind} {target} (opacity={opacity})".strip()


def op_list(path, layers, settings=None):
    if settings:
        pairs = ", ".join(f"{k}={settings[k]}" for k in _SETTING_KEYS
                          if k in settings)
        gs.message(f"Template settings in <{path}>: {pairs}")
    # The placeholders are what a template still needs to be told at render
    # time, so name them rather than leaving them to be spotted in the layers.
    placeholders = sorted(
        find_placeholders(layers) | find_placeholders(settings or {})
    )
    if placeholders:
        gs.message(f"Placeholders in <{path}> (fill with replace=): "
                   f"{', '.join(placeholders)}")
    if not layers:
        gs.message(f"Spec file <{path}> has no layers.")
        return
    gs.message(f"Layers in <{path}> (drawn bottom to top):")
    for index, layer in enumerate(layers, start=1):
        gs.message(f"  {index}: {summarize(layer)}")


def _parse_position(options):
    """Parse the 'position' string option into an int (0 = end)."""
    try:
        return int(options["position"])
    except ValueError:
        gs.fatal(f"position must be an integer, got '{options['position']}'.")


def _target_index(position, count):
    """Resolve a 1-based 'position' (0 = last) to a 0-based index into an
    existing stack of `count` layers. Fatals if out of range."""
    if count == 0:
        gs.fatal("Spec file has no layers.")
    index = count - 1 if position <= 0 else position - 1
    if index < 0 or index >= count:
        gs.fatal(f"position {position} is out of range (1-{count}).")
    return index


def op_add(path, layers, settings, options):
    """Add a layer: append (position 0), or insert at 'position'."""
    layer = build_layer(options)
    position = _parse_position(options)
    if position <= 0:
        layers.append(layer)
        gs.message(f"Appended layer {len(layers)} to <{path}>.")
    else:
        layers.insert(position - 1, layer)
        gs.message(f"Inserted layer at position {min(position, len(layers))}.")
    write_spec(path, layers, settings)


def op_delete(path, layers, settings, options):
    """Delete the layer at 'position' (0 = last)."""
    index = _target_index(_parse_position(options), len(layers))
    removed = layers.pop(index)
    write_spec(path, layers, settings)
    gs.message(f"Deleted layer {index + 1}: {summarize(removed)}")


def op_settings(path, layers, settings, options, provided):
    """Set the template settings (font, fontsize, dpi, margin, background) in
    the spec. Only the options you pass are changed; the rest keep their stored
    value. This is the only operation that writes settings, so building layers
    with 'add' never touches them."""
    updated = capture_settings(settings, options, provided)
    if not updated:
        gs.fatal("operation=settings needs at least one of: %s."
                 % ", ".join(_SETTING_KEYS))
    write_spec(path, layers, settings)
    gs.message("Set template setting(s) %s in <%s>."
               % (", ".join(updated), path))


def _resolve_setting(key, options, provided, settings, cast):
    """Effective value of a template setting: an explicitly-provided option
    overrides the stored template value, which overrides the option default."""
    if key in provided:
        return cast(options[key])
    if key in settings:
        return cast(settings[key])
    return cast(options[key])


def _op_render(options, provided, layers, settings):
    if not options["output"]:
        gs.fatal("operation=render requires the 'output' option.")
    font = _resolve_setting("font", options, provided, settings, str)
    base_fontsize = _resolve_setting("fontsize", options, provided, settings,
                                     float)
    dpi = _resolve_setting("dpi", options, provided, settings, int)
    margin = _resolve_setting("margin", options, provided, settings, int)
    background = _resolve_setting("background", options, provided, settings, str)
    fw, fh = options["figure_width"], options["figure_height"]
    common = dict(margin=margin, background=background, dpi=dpi,
                  base_fontsize=base_fontsize)
    if fw or fh:
        render_spec(layers, options["output"], font,
                    figure=(float(fw) if fw else None,
                            float(fh) if fh else None),
                    **common)
    else:
        render_spec(layers, options["output"], font,
                    width=int(options["width"]) if options["width"] else 1200,
                    **common)
    gs.message(f"Rendered {len(layers)} layers to <{options['output']}>.")


def main():
    options, flags = gs.parser()
    provided = _provided_options()
    # The parser 'required'/'exclusive' rules guarantee exactly one is set.
    # 'new_spec' creates a new file.
    operation = options["operation"]
    if options["new_spec"]:
        path = options["new_spec"]
        layers, settings = [], {}
    else:
        path = options["spec"]
        layers, settings = read_spec(path)

    if operation == "render":
        layers, settings = resolve_placeholders(layers, settings,
                                                options["replace"])
        _op_render(options, provided, layers, settings)
        return 0

    # Substitution is a render-time step: the operations below act on the spec
    # as stored, so a template keeps its placeholders.
    if options["replace"]:
        gs.warning("The replace option only applies to operation=render; "
                   "ignored here.")

    if operation == "settings":
        op_settings(path, layers, settings, options, provided)
        return 0

    # Template settings are only written by operation=settings; passing them to
    # a layer operation does nothing, so say so (they are common GUI fields).
    stray = [o for o in _SETTING_KEYS if o in provided]
    if stray:
        gs.warning("Option(s) %s only apply to operation=settings or render; "
                   "ignored here. Use operation=settings to store them."
                   % ", ".join(stray))

    if operation == "add":
        op_add(path, layers, settings, options)
    elif operation == "list":
        op_list(path, layers, settings)
    elif operation == "delete":
        op_delete(path, layers, settings, options)
    else:
        gs.fatal(f"Unknown operation: {operation}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

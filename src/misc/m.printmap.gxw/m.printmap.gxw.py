#!/usr/bin/env python3

##############################################################################
# MODULE:    m.printmap.gxw
#
# AUTHOR(S): Paulo van Breugel
#
# PURPOSE:   Convert a GRASS workspace (.gxw) into an m.printmap spec file,
#            extracting the visible layers and overlays of a display.
#
# SPDX-FileCopyrightText: 2026 Paulo van Breugel
# SPDX-License-Identifier: GPL-2.0-or-later
#
##############################################################################

# %module
# % description: Convert a GRASS workspace (.gxw) into an m.printmap spec file.
# % keyword: cartography
# % keyword: map
# % keyword: workspace
# % keyword: import
# %end

# %option G_OPT_F_BIN_INPUT
# % key: input
# % description: GRASS workspace (.gxw) file to convert
# %end

# %option G_OPT_F_OUTPUT
# % key: output
# % description: m.printmap spec file to create
# %end

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter

import grass.script as gs

# Spec keys whose value is a list of floats (placement 'at').
_FLOAT_LIST_KEYS = {"at"}

# ----------------------------------------------------------------------------
# Supported d.* parameters per task, as a set: m.printmap spec keys are the
# underlying d.* parameter names, so a parameter maps to itself. The third
# tuple element is the spec key that receives the task's flags.
# ----------------------------------------------------------------------------
def _identity(*names):
    return {name: name for name in names}


_GXW_VECTOR = _identity(
    "map", "type", "color", "fill_color", "width", "cats", "where", "icon", "size",
)
_GXW_LABELS = _identity(
    "map", "type", "attribute_column", "label_size", "label_color", "font",
    "xref", "cats", "where",
)
_GXW_TASKS = {
    "d.rast": ("raster", _identity("map", "values"), None),
    "d.vect": ("vector", _GXW_VECTOR, None),
    "d.legend": ("legend_raster", _identity(
        "raster", "at", "fontsize", "digits", "use", "labelnum",
        "label_values", "border_color", "bgcolor",
    ), "flags"),
    "d.legend.vect": ("legend_vector", _identity(
        "map", "at", "fontsize", "title", "columns", "symbol_size", "font",
        "bgcolor", "border_color",
    ), None),
    "d.barscale": ("barscale", _identity(
        "at", "style", "length", "units", "segment", "fontsize", "color",
        "bgcolor", "text_position",
    ), "flags"),
    "d.grid": ("grid", _identity(
        "size", "color", "border_color", "text_color", "fontsize", "width",
    ), "flags"),
}


# The absolute d.* font-size spec key each kind carries after extraction. The
# new m.printmap renderer no longer reads these; it stores one base font size
# in the template 'settings' block and reads a per-element 'font_scale' ratio
# (effective px = base x ratio x dpi/96). _apply_font_scales() rewrites them.
_FONT_SIZE_KEYS = {
    "labels": "label_size",
    "legend_raster": "fontsize",
    "legend_vector": "fontsize",
    "barscale": "fontsize",
    "grid": "fontsize",
}


def _apply_font_scales(layers, default_base=12.0):
    """Convert each element's absolute d.* font size into a template-relative
    'font_scale' ratio, returning the {'fontsize': base} settings that holds the
    single base point size the ratios multiply. The base is the most common font
    size across the display's text elements (falling back to 'default_base'), so
    the common case yields ratios near 1.0. Grid is scaled the same way; when a
    layer carries no font size it is left alone and the renderer's own default
    ratio applies."""
    sizes = []
    for layer in layers:
        key = _FONT_SIZE_KEYS.get(layer["kind"])
        if key and key in layer:
            try:
                sizes.append(float(layer[key]))
            except (TypeError, ValueError):
                pass
    base = Counter(sizes).most_common(1)[0][0] if sizes else float(default_base)
    for layer in layers:
        key = _FONT_SIZE_KEYS.get(layer["kind"])
        if not key or key not in layer:
            continue
        try:
            size = float(layer.pop(key))
        except (TypeError, ValueError):
            continue
        layer["font_scale"] = round(size / base, 3)
    return {"fontsize": base}


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
    """Write the spec as pretty-printed JSON (matching m.printmap). With
    template settings it is an object {"settings": ..., "layers": [...]};
    without, a bare array of layers."""
    data = {"settings": settings, "layers": layers} if settings else layers
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(_spec_to_json(data) + "\n")


def _gxw_params(element):
    """Collect non-empty <parameter><value> pairs under a gxw element."""
    out = {}
    for p in element.findall("parameter"):
        value = p.find("value")
        if value is not None and value.text and value.text.strip():
            out[p.get("name")] = value.text.strip()
    return out


def _gxw_flags(element):
    """Collect meaningful <flag> names under a gxw element."""
    skip = {"verbose", "quiet", "overwrite"}
    return [f.get("name") for f in element.findall("flag")
            if f.get("name") not in skip]


def _gxw_convert(kind, pmap, params, flags, flag_key, opacity):
    """Build one spec dict from parsed gxw params. Returns (layer, dropped)."""
    layer = {"kind": kind}
    dropped = []
    for name, value in params.items():
        if name not in pmap:
            dropped.append(name)
            continue
        key = pmap[name]
        if key in _FLOAT_LIST_KEYS:
            layer[key] = [float(v) for v in value.split(",")]
        else:
            layer[key] = value
    if flag_key and flags:
        layer[flag_key] = "".join(flags)
    layer["opacity"] = round(float(opacity), 3)
    return layer, dropped


def import_gxw(path):
    """Parse a .gxw and return (layers, settings, region_dict, warnings) for the
    first display. Layer order is reversed to m.printmap's bottom-to-top; a
    d.vect with an attribute_column is split into a vector plus a labels layer.
    Absolute d.* font sizes are folded into a base font size ('settings') plus
    per-element 'font_scale' ratios, matching the current m.printmap format."""
    tree = ET.parse(path)
    displays = tree.getroot().findall("display")
    if not displays:
        gs.fatal(f"No <display> found in workspace <{path}>.")
    if len(displays) > 1:
        names = ", ".join(d.get("name", "?") for d in displays)
        gs.warning(f"Workspace has multiple displays ({names}); importing the first.")
    display = displays[0]

    layers, warnings = [], []
    visible = [l for l in display.findall("layer") if l.get("checked") == "1"]
    for lay in reversed(visible):  # top-to-bottom in file -> bottom-to-top
        task = lay.find("task")
        name = task.get("name") if task is not None else None
        label = lay.get("name", name)
        if name not in _GXW_TASKS:
            warnings.append(f"skipped unsupported layer: {name} ({label})")
            continue
        params = _gxw_params(task)
        flags = _gxw_flags(task)
        opacity = lay.get("opacity", "1")
        kind, pmap, flag_key = _GXW_TASKS[name]
        layer, dropped = _gxw_convert(kind, pmap, params, flags, flag_key, opacity)
        layers.append(layer)
        # Label auto-splitting: a d.vect that also labels becomes two layers.
        if name == "d.vect" and "attribute_column" in params:
            lbl, _ = _gxw_convert("labels", _GXW_LABELS, params, [], None, opacity)
            layers.append(lbl)
            dropped = [d for d in dropped if d not in _GXW_LABELS]
        if dropped:
            warnings.append(f"{label}: dropped params {sorted(set(dropped))}")

    for ov in display.findall("overlay"):  # overlays draw on top
        name = ov.get("name")
        if name not in _GXW_TASKS:
            warnings.append(f"skipped unsupported overlay: {name}")
            continue
        kind, pmap, flag_key = _GXW_TASKS[name]
        layer, dropped = _gxw_convert(
            kind, pmap, _gxw_params(ov), _gxw_flags(ov), flag_key, "1"
        )
        layers.append(layer)
        if dropped:
            warnings.append(f"{name}: dropped params {sorted(set(dropped))}")

    settings = _apply_font_scales(layers)

    region = None
    extent = display.get("extent")
    if extent:
        w, s, e, n = (float(x) for x in extent.split(",")[:4])
        region = {"n": n, "s": s, "e": e, "w": w}
    return layers, settings, region, warnings


def region_command(region):
    def fmt(v):
        return repr(v).rstrip("0").rstrip(".")
    return "g.region n={n} s={s} e={e} w={w}".format(
        n=fmt(region["n"]), s=fmt(region["s"]),
        e=fmt(region["e"]), w=fmt(region["w"]),
    )


def main():
    options, flags = gs.parser()
    layers, settings, region, warnings = import_gxw(options["input"])
    for warning in warnings:
        gs.warning(warning)
    if not layers:
        gs.fatal("No importable layers found in the workspace.")
    write_spec(options["output"], layers, settings)
    if region:
        gs.message("Set the region to match the workspace view with:")
        gs.message(f"  {region_command(region)}")
    gs.message(f"Wrote {len(layers)} layers to <{options['output']}>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

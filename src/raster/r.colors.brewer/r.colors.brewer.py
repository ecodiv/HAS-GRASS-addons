#!/usr/bin/env python3

############################################################################
#
# MODULE:       r.colors.brewer
# AUTHOR:       Paulo van Breugel
# PURPOSE:      Build a ColorBrewer color table for a raster map and either
#               apply it with r.colors or print the color rules to stdout.
#               The user picks a sequential, diverging or qualitative scheme
#               and the number of classes; class boundaries can be equal
#               intervals, percentages, or user-defined breakpoints.
# COPYRIGHT:    (C) 2026
#               This program is free software under the GNU GPL (>=v2).
#
#               The ColorBrewer color values are by Cynthia Brewer
#               (https://colorbrewer2.org), licensed Apache-2.0, and are
#               bundled in the accompanying colorbrewer_data.py.
#
#############################################################################

# %module
# % description: Builds and applies ColorBrewer color tables for raster maps, or prints the r.colors rules.
# % keyword: raster
# % keyword: color table
# % keyword: colors
# % keyword: ColorBrewer
# %end

# %option G_OPT_R_MAP
# % key: map
# % description: Raster map to apply the color table to (omit to only print the rules)
# % required: no
# % guisection: Scheme
# %end

# %option
# % key: sequential
# % type: string
# % label: Sequential scheme
# % description: ColorBrewer sequential scheme (ordered data, low to high)
# % options: Blues,BuGn,BuPu,GnBu,Greens,Greys,OrRd,Oranges,PuBu,PuBuGn,PuRd,Purples,RdPu,Reds,YlGn,YlGnBu,YlOrBr,YlOrRd
# % required: no
# % guisection: Scheme
# %end

# %option
# % key: diverging
# % type: string
# % label: Diverging scheme
# % description: ColorBrewer diverging scheme (emphasizes a mid-range critical value)
# % options: BrBG,PRGn,PiYG,PuOr,RdBu,RdGy,RdYlBu,RdYlGn,Spectral
# % required: no
# % guisection: Scheme
# %end

# %option
# % key: qualitative
# % type: string
# % label: Qualitative scheme
# % description: ColorBrewer qualitative scheme (categorical data; colors mapped to categories 1..classes)
# % options: Accent,Dark2,Paired,Pastel1,Pastel2,Set1,Set2,Set3
# % required: no
# % guisection: Scheme
# %end

# %option
# % key: classes
# % type: integer
# % label: Number of data classes (colors)
# % description: Number of colors to take from the scheme; the valid range depends on the scheme (3-9 for most sequential, 3-11 for diverging, up to 3-12 for qualitative)
# % options: 3-12
# % required: yes
# % guisection: Scheme
# %end

# %option
# % key: breakpoints
# % type: string
# % label: Class breakpoints
# % description: Class boundaries, classes + 1 values, either all plain numbers (absolute) or all percentages (e.g. 0%,20%,...,100%); overrides equal-interval spacing. Sequential and diverging schemes only.
# % multiple: yes
# % required: no
# % guisection: Mapping
# %end

# %option
# % key: range
# % type: string
# % key_desc: min,max
# % label: Data range min,max for absolute breakpoints
# % description: Spread the colors across this range as absolute values instead of percentages; by default an omitted range yields percentage rules that r.colors resolves against each map
# % required: no
# % guisection: Mapping
# %end

# %option
# % key: null_color
# % type: string
# % label: Color for NULL (no-data) cells
# % description: GRASS color name or R:G:B, written as an 'nv' rule; leave empty to keep the current NULL color
# % gisprompt: old,color,color
# % required: no
# % guisection: Mapping
# %end

# %flag
# % key: d
# % label: Discrete class bands
# % description: Hard color steps between classes instead of a continuous (interpolated) gradient
# % guisection: Mapping
# %end

# %flag
# % key: r
# % label: Reverse the color order
# % guisection: Scheme
# %end

# %flag
# % key: n
# % label: Only print the color rules to standard output
# % description: Do not modify the map; print rules usable with r.colors rules=-
# %end

# %rules
# % required: sequential,diverging,qualitative
# % exclusive: sequential,diverging,qualitative
# % exclusive: breakpoints,range
# %end

import os
import sys

import grass.script as gs


def load_brewer():
    """Import the bundled ColorBrewer data module.

    It is installed next to the script in the addon's etc directory; the
    source directory is tried as a fallback so the tool also runs from an
    uninstalled checkout.
    """
    search_dirs = []
    addon_base = os.environ.get("GRASS_ADDON_BASE")
    if addon_base:
        search_dirs.append(os.path.join(addon_base, "etc", "r.colors.brewer"))
    search_dirs.append(os.path.dirname(os.path.abspath(__file__)))
    for directory in search_dirs:
        if os.path.isfile(os.path.join(directory, "colorbrewer_data.py")):
            sys.path.insert(0, directory)
            break
    try:
        from colorbrewer_data import BREWER
    except ImportError:
        gs.fatal(
            _("Could not load the bundled ColorBrewer data (colorbrewer_data.py).")
        )
    return BREWER


def fmt_num(value):
    """Format a computed number compactly, dropping trailing zeros."""
    return f"{value:.10g}"


def parse_float(text, what):
    """Parse a float or fail with a message naming the offending value."""
    try:
        return float(text)
    except ValueError:
        gs.fatal(_("Invalid number in {}: <{}>.").format(what, text))


def parse_breakpoints(raw, nclasses):
    """Validate the breakpoints option and return (strings, values, is_percent).

    strings are the position tokens to write into the rules (percentages keep
    their trailing %), values are the same positions as floats for midpoint
    computation, and is_percent says which kind they are.
    """
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if len(tokens) != nclasses + 1:
        gs.fatal(
            _("The breakpoints option needs classes + 1 = {} values, got {}.").format(
                nclasses + 1, len(tokens)
            )
        )
    is_percent = [t.endswith("%") for t in tokens]
    if all(is_percent):
        percent = True
        values = [parse_float(t[:-1], "breakpoints") for t in tokens]
        strings = [f"{fmt_num(v)}%" for v in values]
    elif not any(is_percent):
        percent = False
        values = [parse_float(t, "breakpoints") for t in tokens]
        strings = [fmt_num(v) for v in values]
    else:
        gs.fatal(
            _(
                "Breakpoints must be either all percentages or all absolute values, not a mix."
            )
        )
    if any(values[i] >= values[i + 1] for i in range(len(values) - 1)):
        gs.fatal(_("Breakpoints must be strictly increasing."))
    return strings, values, percent


def edge_positions(nclasses, vmin, vmax):
    """N+1 equal-interval edge position strings spanning the range or 0-100%."""
    if vmin is None:
        return [f"{fmt_num(i * 100.0 / nclasses)}%" for i in range(nclasses + 1)]
    step = (vmax - vmin) / nclasses
    return [fmt_num(vmin + i * step) for i in range(nclasses + 1)]


def anchor_positions(nclasses, vmin, vmax):
    """N anchor position strings for a continuous gradient (ends at the extremes)."""
    if vmin is None:
        return [f"{fmt_num(i * 100.0 / (nclasses - 1))}%" for i in range(nclasses)]
    step = (vmax - vmin) / (nclasses - 1)
    return [fmt_num(vmin + i * step) for i in range(nclasses)]


def discrete_rules(edges, colors):
    """Doubled-edge rules so each class is a flat band with hard steps."""
    rules = []
    for i, color in enumerate(colors):
        rules.append((edges[i], color))
        rules.append((edges[i + 1], color))
    return rules


def continuous_breakpoint_rules(edge_strings, edge_values, is_percent, colors):
    """Continuous gradient with each class color centered on its interval."""
    suffix = "%" if is_percent else ""
    rules = [(edge_strings[0], colors[0])]
    for i, color in enumerate(colors):
        midpoint = (edge_values[i] + edge_values[i + 1]) / 2.0
        rules.append((f"{fmt_num(midpoint)}{suffix}", color))
    rules.append((edge_strings[-1], colors[-1]))
    return rules


def clamp_to_ends(rules):
    """Extend the first and last colors to -inf and inf.

    r.colors leaves cells outside the rule range uncolored. Repeating the end
    colors at -inf and inf makes below-range cells keep the first color and
    above-range cells the last color (the colors are equal across each outer
    segment, so the extension is flat rather than interpolated).
    """
    return [("-inf", rules[0][1]), *rules, ("inf", rules[-1][1])]


def build_rules(colors, scheme_type, flags, breakpoints, vmin, vmax):
    """Return a list of (position_string, (r, g, b)) rule entries."""
    nclasses = len(colors)
    if scheme_type == "qualitative":
        return [(str(i), color) for i, color in enumerate(colors, start=1)]

    if breakpoints is not None:
        edge_strings, edge_values, is_percent = breakpoints
        if flags["d"]:
            rules = discrete_rules(edge_strings, colors)
        else:
            rules = continuous_breakpoint_rules(
                edge_strings, edge_values, is_percent, colors
            )
        spans_full_range = is_percent and edge_values[0] <= 0 and edge_values[-1] >= 100
    elif flags["d"]:
        rules = discrete_rules(edge_positions(nclasses, vmin, vmax), colors)
        spans_full_range = vmin is None
    else:
        rules = list(zip(anchor_positions(nclasses, vmin, vmax), colors))
        spans_full_range = vmin is None

    # Percentage rules from 0 to 100 already span the map, so they need no
    # extension; fixed-value rules can stop short of the data and must not
    # leave the cells beyond them uncolored.
    if not spans_full_range:
        rules = clamp_to_ends(rules)
    return rules


def main():
    options, flags = gs.parser()

    scheme_type = None
    scheme_name = None
    for candidate in ("sequential", "diverging", "qualitative"):
        if options[candidate]:
            scheme_type = candidate
            scheme_name = options[candidate]
    # The parser rules guarantee exactly one scheme option is set.

    nclasses = int(options["classes"])

    brewer = load_brewer()
    palette = brewer[scheme_type][scheme_name]
    if nclasses not in palette:
        valid = sorted(palette)
        gs.fatal(
            _("Scheme <{s}> supports {lo}-{hi} classes, not {n}.").format(
                s=scheme_name, lo=valid[0], hi=valid[-1], n=nclasses
            )
        )
    colors = list(palette[nclasses])
    if flags["r"]:
        colors.reverse()

    if scheme_type == "qualitative":
        for opt in ("breakpoints", "range"):
            if options[opt]:
                gs.warning(
                    _("Option {} is ignored for qualitative schemes.").format(opt)
                )
        if flags["d"]:
            gs.warning(_("Flag -d is ignored for qualitative schemes."))

    breakpoints = None
    if options["breakpoints"] and scheme_type != "qualitative":
        breakpoints = parse_breakpoints(options["breakpoints"], nclasses)

    vmin = vmax = None
    if options["range"] and scheme_type != "qualitative":
        parts = options["range"].split(",")
        if len(parts) != 2:
            gs.fatal(_("Option range must be given as min,max."))
        vmin = parse_float(parts[0], "range")
        vmax = parse_float(parts[1], "range")
        if vmin >= vmax:
            gs.fatal(_("In range=min,max, min must be smaller than max."))

    rules = build_rules(colors, scheme_type, flags, breakpoints, vmin, vmax)

    lines = [f"{pos} {r}:{g}:{b}" for pos, (r, g, b) in rules]
    if options["null_color"]:
        lines.append(f"nv {options['null_color']}")
    text = "\n".join(lines) + "\n"

    raster = options["map"]
    if flags["n"] or not raster:
        sys.stdout.write(text)
        return 0

    rules_file = gs.tempfile()
    with open(rules_file, "w") as handle:
        handle.write(text)
    gs.run_command("r.colors", map=raster, rules=rules_file)
    gs.message(_("Color table set for raster map <{}>.").format(raster))
    return 0


if __name__ == "__main__":
    sys.exit(main())

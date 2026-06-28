#!/usr/bin/env python3
############################################################################
#
# MODULE:       v.snap
# AUTHOR(S):    Paulo van Breugel
# PURPOSE:      Snap points from a vector point map onto the nearest
#               location on the features of a vector line map.
#               Original categories and attributes are preserved.
# COPYRIGHT:    (C) 2026 by Paulo van Breugel and the GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################

# %module
# % description: Snaps points to the nearest location on a vector line map.
# % keyword: vector
# % keyword: snapping
# % keyword: geometry
# % keyword: points
# % keyword: lines
# %end

# %option G_OPT_V_INPUT
# % key: input
# % label: Name of input vector point map
# % description: Points to be snapped onto the line map
# % guisection: Input
# %end

# %option G_OPT_V_INPUT
# % key: lines
# % label: Name of vector line map to snap onto
# % description: Lines defining the target locations for snapping
# % guisection: Input
# %end

# %option G_OPT_V_OUTPUT
# % key: output
# % description: Name for output vector point map with snapped points
# % guisection: Output
# %end

# %option
# % key: dmax
# % type: double
# % required: no
# % label: Maximum snapping distance
# % description: Points farther than this distance from any line are not snapped (map units). If not set, all points are snapped regardless of distance.
# % guisection: Options
# %end

# %flag
# % key: k
# % label: Keep unsnapped points at their original location
# % description: Points beyond dmax are included in the output at their original position and flagged in the 'snapped' column
# % guisection: Options
# %end

# %option G_OPT_V_FIELD
# % key: layer
# % label: Layer number or name of the input point map
# % description: Only this layer is processed; other layers are not carried to the output
# % answer: 1
# % guisection: Options
# %end

# %flag
# % key: z
# % label: Preserve Z coordinates from 3D input
# % description: If input is 3D, carry the original Z coordinate onto the snapped points. Without this flag, Z is dropped and the output is 2D.
# % guisection: Options
# %end

import atexit
import os
import sys

import grass.script as gs

TMP_MAPS = []


def cleanup():
    """Remove temporary maps on exit."""
    for name in TMP_MAPS:
        gs.run_command(
            "g.remove",
            type="vector",
            name=name,
            flags="f",
            quiet=True,
            errors="ignore",
        )


def _table_of(vector_map, layer):
    """Return the attribute table name for a vector map at a given layer,
    or None if no table is connected at that layer."""
    db = gs.vector_db(vector_map)
    key = int(layer)
    if key not in db:
        return None
    return db[key]["table"]


def main():
    points = options["input"]
    layer = options["layer"]
    lines = options["lines"]
    output = options["output"]
    dmax = options["dmax"]
    keep_unsnapped = flags["k"]
    preserve_z = flags["z"]

    # Input validation
    if not gs.find_file(points, element="vector")["file"]:
        gs.fatal(_("Input vector map <%s> not found") % points)
    if not gs.find_file(lines, element="vector")["file"]:
        gs.fatal(_("Line vector map <%s> not found") % lines)

    info = gs.vector_info_topo(points)
    if info["points"] == 0:
        gs.fatal(_("Input map <%s> does not contain any points") % points)

    linfo = gs.vector_info_topo(lines)
    if linfo["lines"] == 0 and linfo["boundaries"] == 0:
        gs.fatal(_("Line map <%s> does not contain any lines") % lines)

    # 3D detection
    map_is_3d = int(gs.vector_info(points).get("map3d", 0)) == 1
    is_3d = map_is_3d and preserve_z
    if map_is_3d and not preserve_z:
        gs.warning(
            _(
                "Input map <%s> is 3D; Z coordinates will be dropped. "
                "Use the -z flag to preserve them on snapped points."
            )
            % points
        )
    elif preserve_z and not map_is_3d:
        gs.warning(
            _(
                "Flag -z is set but input map <%s> is 2D; no Z coordinates "
                "to preserve."
            )
            % points
        )
    elif is_3d:
        gs.message(
            _(
                "Input map <%s> is 3D; original Z coordinates will be "
                "preserved on snapped points."
            )
            % points
        )

    # Work on a copy
    tmp_points = "tmp_vsnap_pts_%d" % os.getpid()
    TMP_MAPS.append(tmp_points)
    gs.run_command(
        "g.copy", vector=(points, tmp_points), quiet=True, overwrite=True
    )

    # Drop features with cat=-1 (no category) at the chosen layer
    cat_report = gs.read_command(
        "v.category",
        input=tmp_points,
        layer=layer,
        option="print",
        quiet=True,
    )
    n_nocat = sum(
        1 for ln in cat_report.strip().splitlines() if ln.strip() == "-1"
    )
    if n_nocat > 0:
        gs.warning(
            _(
                "%d point(s) in layer %s have no category (cat=-1) "
                "and will be excluded from the output."
            )
            % (n_nocat, layer)
        )
        tmp_extracted = "tmp_vsnap_ext_%d" % os.getpid()
        TMP_MAPS.append(tmp_extracted)
        # Keep everything with a valid cat.
        gs.run_command(
            "v.extract",
            input=tmp_points,
            layer=layer,
            output=tmp_extracted,
            cats="1-999999999",
            quiet=True,
            overwrite=True,
        )
        tmp_points = tmp_extracted

    # Ensure the working copy has an attribute table at the chosen layer
    if int(layer) not in gs.vector_db(tmp_points):
        gs.run_command(
            "v.db.addtable", map=tmp_points, layer=layer, quiet=True
        )

    # Compute nearest location on lines for each point
    extra_cols = (
        "vsnap_x double precision, "
        "vsnap_y double precision, "
        "vsnap_dist double precision"
    )
    if is_3d:
        extra_cols += ", vsnap_z double precision"
    gs.run_command(
        "v.db.addcolumn",
        map=tmp_points,
        layer=layer,
        columns=extra_cols,
        quiet=True,
    )

    # For 3D input, first capture the original z into vsnap_z.
    # v.to.db with option=coor fills x,y,z columns from geometry.
    if is_3d:
        gs.run_command(
            "v.to.db",
            map=tmp_points,
            layer=layer,
            option="coor",
            columns="vsnap_x,vsnap_y,vsnap_z",
            quiet=True,
        )

    vd_kwargs = {
        "from_": tmp_points,
        "from_layer": layer,
        "to": lines,
        "upload": "to_x,to_y,dist",
        "column": "vsnap_x,vsnap_y,vsnap_dist",
        "quiet": True,
    }
    if dmax:
        vd_kwargs["dmax"] = float(dmax)

    gs.run_command("v.distance", **vd_kwargs)

    # build ASCII input for v.in.ascii
    if keep_unsnapped:
        gs.run_command(
            "v.db.addcolumn",
            map=tmp_points,
            layer=layer,
            columns=(
                "vsnap_orig_x double precision, "
                "vsnap_orig_y double precision"
            ),
            quiet=True,
        )
        gs.run_command(
            "v.to.db",
            map=tmp_points,
            layer=layer,
            option="coor",
            columns="vsnap_orig_x,vsnap_orig_y",
            quiet=True,
        )
        table = _table_of(tmp_points, layer)
        if is_3d:
            select_sql = (
                "SELECT cat, "
                "COALESCE(vsnap_x, vsnap_orig_x), "
                "COALESCE(vsnap_y, vsnap_orig_y), "
                "vsnap_z, "
                "CASE WHEN vsnap_x IS NULL THEN 0 ELSE 1 END "
                "FROM %s" % table
            )
        else:
            select_sql = (
                "SELECT cat, "
                "COALESCE(vsnap_x, vsnap_orig_x), "
                "COALESCE(vsnap_y, vsnap_orig_y), "
                "CASE WHEN vsnap_x IS NULL THEN 0 ELSE 1 END "
                "FROM %s" % table
            )
        coords = gs.read_command(
            "db.select", sql=select_sql, separator="|", flags="c"
        )
    else:
        cols = "cat,vsnap_x,vsnap_y"
        if is_3d:
            cols += ",vsnap_z"
        coords = gs.read_command(
            "v.db.select",
            map=tmp_points,
            layer=layer,
            columns=cols,
            where="vsnap_x IS NOT NULL",
            separator="|",
            flags="c",
        )
        coords = (
            "\n".join(
                ln + "|1" for ln in coords.strip().splitlines() if ln
            )
            + "\n"
        )

    if not coords.strip():
        hint = _(" and that dmax is large enough") if dmax else ""
        gs.fatal(
            _(
                "No points could be snapped. Check that point and line "
                "maps overlap%s."
            )
            % hint
        )

    # Rebuild as new point vector
    ascii_kwargs = {
        "input": "-",
        "output": output,
        "separator": "|",
        "stdin": coords,
        "x": 2,
        "y": 3,
        "cat": 1,
        "format": "point",
        "quiet": True,
        "overwrite": gs.overwrite(),
    }
    if is_3d:
        ascii_kwargs["z"] = 4
        ascii_kwargs["flags"] = "z"
        ascii_kwargs["columns"] = (
            "cat integer, x double precision, y double precision, "
            "z double precision, snapped integer"
        )
    else:
        ascii_kwargs["columns"] = (
            "cat integer, x double precision, y double precision, "
            "snapped integer"
        )
    gs.write_command("v.in.ascii", **ascii_kwargs)

    # Join original attributes from the chosen layer
    orig_table = _table_of(points, layer)
    if orig_table:
        orig_db = gs.vector_db(points)
        gs.run_command(
            "v.db.join",
            map=output,
            column="cat",
            other_table=orig_table,
            other_column=orig_db[int(layer)]["key"],
            quiet=True,
        )

    # Summary
    n_total = info["points"]
    n_snapped = sum(
        1 for ln in coords.strip().splitlines() if ln.endswith("|1")
    )
    gs.message(
        _("Snapped %d of %d points to <%s>.")
        % (n_snapped, n_total, lines)
    )
    if keep_unsnapped and n_snapped < (n_total - n_nocat):
        gs.message(
            _("%d unsnapped points kept at their original location.")
            % ((n_total - n_nocat) - n_snapped)
        )


if __name__ == "__main__":
    options, flags = gs.parser()
    atexit.register(cleanup)
    sys.exit(main())

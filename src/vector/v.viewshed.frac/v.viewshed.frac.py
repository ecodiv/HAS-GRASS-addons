#!/usr/bin/env python3

############################################################################
#
# MODULE:       v.viewshed.frac
# 
# AUTHOR(S):    Paulo van Breugel
# 
# PURPOSE:      For each point in an input vector map, computes the fraction
#               of the area within a given radius that is visible to an
#               observer standing at that point, using r.viewshed on a
#               user-provided blocking surface. Visible targets are
#               restricted to a required "standable" mask (cells where a
#               person could actually be). Results are written as attribute
#               columns on the input point layer.
# 
# SPDX-FileCopyrightText: 2026 Paulo van Breugel
# SPDX-FileCopyrightText: Other GRASS authors
# SPDX-License-Identifier: GPL-2.0-or-later
#
############################################################################

# %module
# % label: Per-observer viewshed fraction for points.
# % description: Computes the fraction of a surrounding circle (full or standable-only) that is visible to the observer at each input point. Results are written as new columns on the input vector map.
# % keyword: vector
# % keyword: viewshed
# % keyword: visibility
# % keyword: openness
# % keyword: line of sight
# % keyword: parallel
# %end

# %option G_OPT_V_INPUT
# % key: input
# % label: Name of input point vector map
# % description: Observer points. Results are written as new columns on this map.
# % guisection: Input
# %end

# %option G_OPT_R_INPUT
# % key: surface
# % label: Name of input blocking-surface raster
# % description: Elevation including any obstacles that block sight lines.
# % guisection: Input# %end

# %option G_OPT_V_FIELD
# % key: layer
# % label: Layer number or name
# % description: Vector layer holding the attributes to update. Use for multi-layer point maps.
# % answer: 1
# %end

# %option G_OPT_R_INPUT
# % key: standable
# % label: Name of input standable-cells raster
# % description: Mask raster of cells where a person could stand. Null and zero are treated as excluded; all other values are treated as standable.
# % guisection: Input
# %end

# %option
# % key: max_distance
# % type: double
# % required: no
# % key_desc: value
# % label: Analysis radius in map units
# % description: Cells beyond this distance are treated as invisible.
# % answer: 10.0
# % guisection: Input
# %end

# %option
# % key: column_circle
# % type: string
# % required: no
# % key_desc: name
# % label: Output column for full-circle fraction
# % description: Visible+standable cells divided by all cells within max_distance. Leave empty to skip.
# % answer: vis_frac
# % guisection: Options
# %end

# %option
# % key: column_standable
# % type: string
# % required: no
# % key_desc: name
# % label: Output column for standable-only fraction
# % description: Visible+standable cells divided by standable cells within max_distance. Leave empty to skip.
# % guisection: Options
# %end

# %option
# % key: observer_elevation
# % type: string
# % required: no
# % key_desc: value_or_column
# % label: Observer elevation above the surface
# % description: Either a scalar (e.g. 1.7) applied to all points, or the name of a numeric column in the input map.
# % answer: 1.7
# % guisection: Options
# %end

# %option
# % key: target_elevation
# % type: string
# % required: no
# % key_desc: value_or_column
# % label: Target elevation above the surface
# % description: Either a scalar (e.g. 1.7) applied to all points, or the name of a numeric column in the input map.
# % answer: 1.7
# % guisection: Options
# %end

# %flag
# % key: c
# % label: Consider the curvature of the earth (current ellipsoid)
# % guisection: Options
# %end

# %flag
# % key: r
# % label: Consider the effect of atmospheric refraction
# % guisection: Options
# %end

# %option
# % key: refraction_coeff
# % type: double
# % required: no
# % key_desc: value
# % label: Refraction coefficient (used with -r)
# % options: 0.0-1.0
# % answer: 0.14286
# % guisection: Options
# %end

# %option G_OPT_MEMORYMB
# %end

# %option G_OPT_M_NPROCS
# %end

# %rules
# % required: column_circle,column_standable
# %end


import atexit
import math
import os
import sys
from multiprocessing import Pool

import grass.script as gs
from grass.pygrass.gis.region import Region


# Random prefix for this run's temp rasters
TEMPNAME = gs.tempname(12)


def cleanup():
    """Remove any temp rasters this run created."""
    gs.run_command(
        "g.remove",
        flags="f",
        type="raster",
        pattern=f"{TEMPNAME}_*",
        quiet=True,
        errors="ignore",
    )


def parse_elev(spec, points_map, layer):
    """Return ('scalar', float) or ('column', colname)."""
    try:
        return ("scalar", float(spec))
    except ValueError:
        cols = gs.vector_columns(points_map, layer=layer)
        if spec not in cols:
            gs.fatal(
                f"Elevation '{spec}' is neither a number nor a column "
                f"in '{points_map}' layer {layer}."
            )
        coltype = cols[spec]["type"].upper()
        if coltype not in ("INTEGER", "DOUBLE PRECISION", "REAL", "FLOAT"):
            gs.fatal(
                f"Column '{spec}' in '{points_map}' is type {coltype}; "
                f"must be numeric."
            )
        return ("column", spec)


def read_points(points_map, layer, extra_columns):
    """Read points as list of dicts with x, y, cat, and any extra columns."""
    cols = ["cat"] + [c for c in extra_columns if c]
    raw = gs.read_command(
        "v.out.ascii",
        input=points_map,
        layer=layer,
        format="point",
        separator="|",
        columns=",".join(cols),
    ).strip().splitlines()

    points = []
    for line in raw:
        parts = line.split("|")
        # v.out.ascii format=point emits: x|y|<columns in order>
        x, y = float(parts[0]), float(parts[1])
        rest = parts[2:]
        rec = {"x": x, "y": y, "cat": int(rest[0])}
        for i, col in enumerate(extra_columns):
            if col:
                val = rest[1 + i]
                rec[col] = float(val) if val not in ("", "*") else None
        points.append(rec)
    return points


def ensure_column(points_map, layer, name, sqltype="DOUBLE PRECISION"):
    if not name:
        return
    existing = gs.vector_columns(points_map, layer=layer)
    if name not in existing:
        gs.run_command(
            "v.db.addcolumn",
            map=points_map,
            layer=layer,
            columns=f"{name} {sqltype}",
            quiet=True,
        )


def get_table_info(points_map, layer):
    """Return (table, driver, database) for the given map/layer."""
    conn = gs.vector_db(points_map)
    try:
        layer_key = int(layer)
    except (TypeError, ValueError):
        layer_key = layer
    if layer_key not in conn:
        gs.fatal(
            f"No attribute table connected to '{points_map}' layer {layer}."
        )
    info = conn[layer_key]
    return info["table"], info["driver"], info["database"]


def ensure_cat_index(table, driver, database):
    """Create an index on cat if one doesn't already exist. One-time cost."""
    # CREATE INDEX IF NOT EXISTS works for SQLite, PostgreSQL, and most others.
    sql = f"CREATE INDEX IF NOT EXISTS idx_{table}_cat ON {table}(cat)"
    try:
        gs.write_command(
            "db.execute",
            input="-",
            driver=driver,
            database=database,
            stdin=sql,
            quiet=True,
        )
    except gs.CalledModuleError:
        # Some drivers or schemas don't allow index creation; not fatal.
        gs.warning(f"Could not create index on {table}(cat); writes may be slow.")


def batch_update(table, driver, database, column, updates):
    """Apply many UPDATEs in a single transaction via db.execute.

    updates: iterable of (cat, value) where value is float or None.
    """
    if not column or not updates:
        return

    lines = ["BEGIN;"]
    for cat, value in updates:
        v = "NULL" if value is None else repr(float(value))
        lines.append(f"UPDATE {table} SET {column} = {v} WHERE cat = {cat};")
    lines.append("COMMIT;")
    sql = "\n".join(lines)

    gs.write_command(
        "db.execute",
        input="-",
        driver=driver,
        database=database,
        stdin=sql,
        quiet=True,
    )


def snapped_local_region(x, y, max_dist, reg):
    """Compute a local region around (x, y) aligned to the global raster grid.

    Same math as r.viewshed.exposure: shift each edge by the point's
    within-cell offset so edges land on cell boundaries, then clip to
    the global region.
    """
    delta_n = math.ceil((y - reg.south) / reg.nsres) * reg.nsres - (y - reg.south)
    delta_s = (y - reg.south) - math.floor((y - reg.south) / reg.nsres) * reg.nsres
    delta_e = math.ceil((x - reg.west) / reg.ewres) * reg.ewres - (x - reg.west)
    delta_w = (x - reg.west) - math.floor((x - reg.west) / reg.ewres) * reg.ewres

    n = min(y + max_dist + delta_n, reg.north)
    s = max(y - max_dist - delta_s, reg.south)
    e = min(x + max_dist + delta_e, reg.east)
    w = max(x - max_dist - delta_w, reg.west)
    return n, s, e, w


def process_chunk(args):
    """Worker: process a chunk of points; return list of result dicts."""
    global_vars, chunk = args

    reg              = global_vars["region"]
    surface          = global_vars["surface"]
    standable        = global_vars["standable"]
    obs_spec         = global_vars["obs_spec"]
    tgt_spec         = global_vars["tgt_spec"]
    max_dist         = global_vars["max_dist"]
    memory_per_core  = global_vars["memory_per_core"]
    flagstring       = global_vars["flagstring"]
    refr_coeff       = global_vars["refr_coeff"]
    want_circle      = global_vars["want_circle"]
    want_standable   = global_vars["want_standable"]
    cells_in_circle  = global_vars["cells_in_circle"]
    tempname         = global_vars["tempname"]

    # PID-scoped temp raster names — reused (overwritten) across points
    pid = os.getpid()
    tmp_vs        = f"{tempname}_vs_{pid}"
    tmp_masked    = f"{tempname}_masked_{pid}"
    tmp_disk      = f"{tempname}_disk_{pid}"
    tmp_standcirc = f"{tempname}_standcirc_{pid}"

    results = []

    for pt in chunk:
        x, y, cat = pt["x"], pt["y"], pt["cat"]

        # Per-point elevations (scalar or looked-up column value)
        obs_h = obs_spec[1] if obs_spec[0] == "scalar" else pt.get(obs_spec[1])
        tgt_h = tgt_spec[1] if tgt_spec[0] == "scalar" else pt.get(tgt_spec[1])

        rec = {"cat": cat, "circle": None, "standable": None}

        if obs_h is None or tgt_h is None:
            results.append(rec)
            continue

        # Local region for this point, passed via GRASS_REGION env var.
        # Parallel-safe: each worker's commands get their own region
        # without touching the mapset's shared WIND file.
        n, s, e, w = snapped_local_region(x, y, max_dist, reg)
        env = os.environ.copy()
        env["GRASS_REGION"] = gs.region_env(n=n, s=s, e=e, w=w)

        # Run viewshed
        try:
            gs.run_command(
                "r.viewshed",
                input=surface,
                output=tmp_vs,
                coordinates=f"{x},{y}",
                observer_elevation=obs_h,
                target_elevation=tgt_h,
                max_distance=max_dist,
                refraction_coeff=refr_coeff,
                memory=memory_per_core,
                flags="b" + flagstring,
                overwrite=True,
                quiet=True,
                env=env,
            )
        except gs.CalledModuleError:
            results.append(rec)
            continue

        # Visible-and-standable cells
        gs.mapcalc(
            f"{tmp_masked} = if({tmp_vs} == 1 && "
            f"!isnull({standable}) && {standable} != 0, 1, null())",
            overwrite=True,
            env=env,
        )
        stats = gs.parse_command(
            "r.stats", flags="cn", input=tmp_masked, separator="=", env=env,
        )
        visible = int(stats.get("1", 0))

        if want_circle:
            rec["circle"] = min(visible / cells_in_circle, 1.0)

        if want_standable:
            # Standable cells inside the circle — depends on observer (x, y)
            gs.mapcalc(
                f"{tmp_disk} = if("
                f"sqrt((x() - {x})^2 + (y() - {y})^2) <= {max_dist}, 1, null())",
                overwrite=True, env=env,
            )
            gs.mapcalc(
                f"{tmp_standcirc} = if("
                f"!isnull({tmp_disk}) && "
                f"!isnull({standable}) && {standable} != 0, 1, null())",
                overwrite=True, env=env,
            )
            denom_stats = gs.parse_command(
                "r.stats", flags="cn", input=tmp_standcirc,
                separator="=", env=env,
            )
            denom = int(denom_stats.get("1", 0))
            rec["standable"] = (visible / denom) if denom > 0 else None

        results.append(rec)

    return results


def main():
    options, flags = gs.parser()

    points_map       = options["input"]
    layer            = options["layer"]
    surface          = options["surface"]
    standable        = options["standable"]
    col_circle       = options["column_circle"] or ""
    col_standable    = options["column_standable"] or ""
    obs_spec_raw     = options["observer_elevation"]
    tgt_spec_raw     = options["target_elevation"]
    max_dist         = float(options["max_distance"])
    refr_coeff       = float(options["refraction_coeff"])
    memory_total     = int(options["memory"])
    nprocs           = int(options["nprocs"])

    # Build r.viewshed flag string (the "b" flag is always added in the worker)
    flagstring = ""
    if flags["c"]:
        flagstring += "c"
    if flags["r"]:
        flagstring += "r"

    want_circle    = bool(col_circle)
    want_standable = bool(col_standable)

    if not (want_circle or want_standable):
        gs.fatal(
            "Nothing to compute: specify at least one of "
            "column_circle or column_standable."
        )

    # Parse elevation specs (scalar or column)
    obs_spec = parse_elev(obs_spec_raw, points_map, layer)
    tgt_spec = parse_elev(tgt_spec_raw, points_map, layer)

    # Set region to the surface raster so Region() reflects the working grid
    gs.run_command("g.region", raster=surface)
    reg = Region()

    if abs(reg.ewres - reg.nsres) > 1e-6:
        gs.warning(
            "Non-square cells detected: results may be slightly imprecise "
            "near the circle boundary."
        )

    cell_area = reg.nsres * reg.ewres
    cells_in_circle = math.pi * max_dist**2 / cell_area

    # Ensure output columns exist
    ensure_column(points_map, layer, col_circle)
    ensure_column(points_map, layer, col_standable)

    # Look up the DB connection for the chosen layer, and make sure the cat
    # column is indexed.
    table, driver, database = get_table_info(points_map, layer)
    ensure_cat_index(table, driver, database)

    # Read points (pulling any elevation columns we need)
    extra_cols = []
    if obs_spec[0] == "column":
        extra_cols.append(obs_spec[1])
    if tgt_spec[0] == "column" and tgt_spec[1] not in extra_cols:
        extra_cols.append(tgt_spec[1])
    points = read_points(points_map, layer, extra_cols)

    if not points:
        gs.fatal(f"No points found in '{points_map}' layer {layer}.")

    gs.message(
        f"Processing {len(points)} points on {nprocs} core(s) "
        f"(layer {layer})."
    )

    # Split into chunks, one per worker
    chunk_size = max(1, math.ceil(len(points) / nprocs))
    chunks = [points[i:i + chunk_size]
              for i in range(0, len(points), chunk_size)]

    global_vars = {
        "region":          reg,
        "surface":         surface,
        "standable":       standable,
        "obs_spec":        obs_spec,
        "tgt_spec":        tgt_spec,
        "max_dist":        max_dist,
        "memory_per_core": max(100, int(round(memory_total / nprocs))),
        "flagstring":      flagstring,
        "refr_coeff":      refr_coeff,
        "want_circle":     want_circle,
        "want_standable":  want_standable,
        "cells_in_circle": cells_in_circle,
        "tempname":        TEMPNAME,
    }

    with Pool(nprocs) as pool:
        chunk_results = pool.map(
            process_chunk,
            [(global_vars, c) for c in chunks],
        )

    # Collect and write all results in a single transaction per column.
    gs.message("Writing results to attribute table...")
    updates_circle = []
    updates_standable = []
    for chunk in chunk_results:
        for rec in chunk:
            cat = rec["cat"]
            if want_circle:
                updates_circle.append((cat, rec["circle"]))
            if want_standable:
                updates_standable.append((cat, rec["standable"]))

    if want_circle:
        batch_update(table, driver, database, col_circle, updates_circle)
    if want_standable:
        batch_update(table, driver, database, col_standable, updates_standable)

    gs.message("Done.")


if __name__ == "__main__":
    atexit.register(cleanup)
    sys.exit(main())

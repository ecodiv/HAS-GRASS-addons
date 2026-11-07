#!/usr/bin/env python3

############################################################################
#
# MODULE:       r.niche.espace
# AUTHOR(S):    Paulo van Breugel
# PURPOSE:      Data preparation for niche-overlap analysis with the R
#               package 'humboldt' (Brown & Carnaval 2019). Ports the
#               preparatory half of humboldt to GRASS so it streams over
#               large rasters:
#
#                   thin  ->  trim  ->  sample  ->  humboldt-format tables
#
#               Outputs plug straight into humboldt.g2e() in R (run with
#               env.trim=FALSE and rarefy.dist=0, since GRASS already did
#               the trimming and thinning). The niche statistics, PCA and
#               kernel density stay in humboldt; geographic overlap/diver-
#               gence maps are produced afterwards by r.niche.map.
#
# REQUIRES:     GRASS GIS 8.5+
#
# COPYRIGHT:    (c) 2026 Paulo van Breugel and the GRASS Development Team
#               GNU General Public License (>=v2)
#
############################################################################

# %Module
# % description: Prepares occurrence and environmental data (thin, trim, sample) into humboldt-format tables for niche analysis.
# % keyword: raster
# % keyword: vector
# % keyword: niche modelling
# % keyword: ecology
# %End

# ---------------------------------------------------------------- inputs ---
# %option G_OPT_R_INPUTS
# % key: env
# % description: Environmental raster variables (the E variables)
# % required: yes
# %end

# %option G_OPT_V_INPUT
# % key: occ_1
# % description: Occurrence points, species/population 1
# % required: yes
# %end

# %option G_OPT_V_INPUT
# % key: occ_2
# % description: Occurrence points, species/population 2
# % required: yes
# %end

# ------------------------------------------------------------- thinning ---
# %option
# % key: thin_distance
# % type: double
# % description: Minimum distance between retained occurrences (0 = no thinning)
# % answer: 0
# % guisection: Thinning
# %end

# %option
# % key: thin_units
# % type: string
# % options: map,km,cells
# % answer: km
# % description: Units of thin_distance
# % guisection: Thinning
# %end

# %option
# % key: thin_method
# % type: string
# % options: grid,nn
# % answer: grid
# % description: grid = fast native cell-snap; nn = iterative nearest-neighbour removal
# % guisection: Thinning
# %end

# ------------------------------------------------------------- trimming ---
# %option
# % key: trim_method
# % type: string
# % options: none,mcp,radius,mask
# % answer: none
# % description: Restrict background to species neighbourhood
# % guisection: Trimming
# %end

# %option
# % key: trim_buffer
# % type: double
# % description: Buffer width for mcp/radius trimming (thin_units units)
# % answer: 200
# % guisection: Trimming
# %end

# %option G_OPT_V_INPUT
# % key: trim_mask_1
# % required: no
# % description: Polygon mask for background 1 (trim_method=mask)
# % guisection: Trimming
# %end

# %option G_OPT_V_INPUT
# % key: trim_mask_2
# % required: no
# % description: Polygon mask for background 2 (trim_method=mask)
# % guisection: Trimming
# %end

# -------------------------------------------------------------- outputs ---
# %option G_OPT_F_OUTPUT
# % key: table_1
# % required: no
# % description: CSV of species 1 occurrences with sampled env values (x,y,cat,var...)
# % guisection: Output
# %end

# %option G_OPT_F_OUTPUT
# % key: table_2
# % required: no
# % description: CSV of species 2 occurrences with sampled env values
# % guisection: Output
# %end

# %option G_OPT_F_OUTPUT
# % key: bg_table_1
# % required: no
# % description: CSV of trimmed background 1 cells (x,y,var...)
# % guisection: Output
# %end

# %option G_OPT_F_OUTPUT
# % key: bg_table_2
# % required: no
# % description: CSV of trimmed background 2 cells (x,y,var...)
# % guisection: Output
# %end

# %option G_OPT_MEMORYMB
# %end

# %rules
# % required: table_1,table_2,bg_table_1,bg_table_2
# %end

import atexit
import sys

import grass.script as gs

# --- 8.5+ API (fail on older versions) ---
from grass.tools import Tools

CLEAN_RAST = []
CLEAN_VECT = []


def cleanup():
    for name in reversed(CLEAN_RAST):
        gs.run_command("g.remove", type="raster", name=name, flags="f",
                       quiet=True, errors="ignore")
    for name in reversed(CLEAN_VECT):
        gs.run_command("g.remove", type="vector", name=name, flags="f",
                       quiet=True, errors="ignore")


def tmp_name(prefix, kind="raster"):
    name = gs.append_node_pid(prefix)
    (CLEAN_RAST if kind == "raster" else CLEAN_VECT).append(name)
    return name


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------
def distance_in_map_units(tools, value, units):
    """Translate a thinning/buffer distance into map units.

    NOTE: for a lat/long location this uses a flat-degree approximation for
    'km' (value / 111). humboldt applies a latitude-dependent correction;
    reproject to an equal-distance CRS for exact parity."""
    if units == "map":
        return value
    if units == "cells":
        reg = tools.g_region(flags="g", format="json")
        return value * float(reg["nsres"])
    if units == "km":
        proj = gs.parse_command("g.proj", flags="g")
        if proj.get("unit", "").lower().startswith("degree"):
            return value / 111.0
        return value * 1000.0            # projected location assumed metres
    raise ValueError(f"unknown units: {units}")


# ---------------------------------------------------------------------------
# Stage 1 - thinning  (replaces humboldt.occ.rarefy)
# ---------------------------------------------------------------------------
def thin(tools, occ, distance, units, method, memory):
    """Return the name of a thinned copy of `occ` (or `occ` if distance==0)."""
    if distance <= 0:
        return occ

    if method == "grid":
        # Snap to a grid of cell size == distance, keep one point per cell.
        # Streaming and O(n): no all-pairs distance computation. Points are
        # moved to cell centres (up to half a cell); use nn for exact coords.
        d = distance_in_map_units(tools, distance, units)
        out = tmp_name("thin", "vector")
        binras = tmp_name("thinbin")
        with gs.RegionManager():
            tools.g_region(vector=occ, res=d)
            tools.v_to_rast(input=occ, output=binras, use="cat",
                            type="point", memory=memory)
            tools.r_to_vect(input=binras, output=out, type="point", flags="v")
        return out

    if method == "nn":
        # Iteratively drop one point of the closest pair; keeps the original
        # coordinates, at O(n^3). See _thin_nn for how it differs from
        # humboldt.occ.rarefy.
        return _thin_nn(tools, occ, distance, units)

    raise ValueError(f"unknown thin_method: {method}")


def _thin_nn(tools, occ, distance, units):
    """Drop one point of the closest pair until no pair is within `distance`.

    The stopping rule is humboldt.occ.rarefy's, but the survivors need not be:
    humboldt measures in azimuthal-equidistant metres (or applies a latitude
    polynomial for degrees) and breaks ties on the 2nd..6th nearest-neighbour
    distances, where this measures in map units and drops whichever point of
    the pair comes first by category. On clustered occurrences the two keep
    different subsets.

    The all-pairs scan runs once per removal, so the cost is O(n^3).
    """
    import math

    d = distance_in_map_units(tools, distance, units)
    txt = gs.read_command("v.out.ascii", input=occ, format="point",
                          separator="comma", quiet=True)
    pts = []
    for line in txt.splitlines():
        x, y, cat = line.split(",")
        pts.append((float(x), float(y), int(cat)))

    def nearest_pair(points):
        best = None
        for i in range(len(points)):
            xi, yi, _ = points[i]
            for j in range(i + 1, len(points)):
                xj, yj, _ = points[j]
                dd = math.hypot(xi - xj, yi - yj)
                if best is None or dd < best[0]:
                    best = (dd, i, j)
        return best

    while len(pts) > 1:
        nn = nearest_pair(pts)
        if nn is None or nn[0] >= d:
            break
        del pts[nn[1]]

    keep = ",".join(str(p[2]) for p in pts)
    out = tmp_name("thinnn", "vector")
    tools.v_extract(input=occ, output=out, cats=keep)
    return out


# ---------------------------------------------------------------------------
# Stage 2 - background trimming  (replaces g2e MCP / RADIUS / MASK branches)
# ---------------------------------------------------------------------------
def trim_mask_vector(tools, occ, method, buffer, units, mask_poly):
    """Return a polygon vector delimiting the background for this species,
    or None when trim_method=none (whole region).

    Buffering is done with v.buffer: cost scales with the (small) occurrence
    set, not the raster size -- the right choice for large rasters."""
    if method == "none":
        return None

    if method == "mask":
        if not mask_poly:
            gs.fatal("trim_method=mask requires trim_mask_* to be set")
        return mask_poly

    b = distance_in_map_units(tools, buffer, units)

    if method == "radius":
        out = tmp_name("trim", "vector")
        # The per-point buffers overlap. Without -t they dissolve into one
        # area, which is what r.mask needs; keeping per-point categories
        # would leave the overlaps ambiguous.
        tools.v_buffer(input=occ, output=out, distance=b)
        return out

    if method == "mcp":
        hull = tmp_name("hull", "vector")
        tools.v_hull(input=occ, output=hull)
        out = tmp_name("trim", "vector")
        tools.v_buffer(input=hull, output=out, distance=b)
        return out

    raise ValueError(f"unknown trim_method: {method}")


# ---------------------------------------------------------------------------
# Stage 3 - sampling -> humboldt-format point tables
# ---------------------------------------------------------------------------
def write_occ_table(tools, occ, env_maps, path):
    """x,y,cat,var1..varN for the occurrence points (humboldt sp table; add
    the 'sp' name column in R). Replaces humboldt.sample.spp's distance loop
    with the indexed v.what.rast lookup."""
    sampled = tmp_name("samp", "vector")
    tools.g_copy(vector=[occ, sampled])
    env_columns = []
    for m in env_maps:
        col = m.split("@")[0].replace(".", "_")
        tools.v_db_addcolumn(map=sampled, columns=f"{col} double precision")
        tools.v_what_rast(map=sampled, raster=m, column=col)
        env_columns.append(col)
    # v.out.ascii writes east,north,cat and then the requested columns. Naming
    # the env columns keeps them at fixed positions; asking for all columns
    # would also emit the occurrence map's own attributes, shifting them.
    gs.run_command("v.out.ascii", input=sampled, output=path, format="point",
                   columns=",".join(env_columns), separator="comma",
                   quiet=True, overwrite=True)


def write_bg_table(tools, env_maps, path):
    """x,y,var1..varN over the CURRENT mask/region (humboldt env table).

    Streamed via r.stats; the mask/region bounds the size, so the file stays
    manageable even for continent-scale rasters."""
    gs.run_command("r.stats", input=env_maps, output=path, flags="1gn",
                   separator="comma", quiet=True, overwrite=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(options, flags):
    tools = Tools()

    env_maps = options["env"].split(",")
    thin_d = float(options["thin_distance"])
    thin_u = options["thin_units"]
    thin_m = options["thin_method"]
    trim_m = options["trim_method"]
    trim_b = float(options["trim_buffer"])
    memory = int(options["memory"])

    for idx, occ_key, tab_key, bgtab_key, mask_key in (
        (1, "occ_1", "table_1", "bg_table_1", "trim_mask_1"),
        (2, "occ_2", "table_2", "bg_table_2", "trim_mask_2"),
    ):
        if not options[tab_key] and not options[bgtab_key]:
            continue
        gs.info(f"Species {idx}: thin -> trim -> sample")

        # Stage 1: thin
        occ_t = thin(tools, options[occ_key], thin_d, thin_u, thin_m, memory)

        # Stage 2: trim -> polygon restricting the background for this species
        trim_vec = trim_mask_vector(
            tools, occ_t, trim_m, trim_b, thin_u, options[mask_key]
        )

        # Reads of the background run under the (isolated) trim mask.
        with gs.MaskManager():
            if trim_vec is not None:
                tools.r_mask(vector=trim_vec)
            if options[tab_key]:
                write_occ_table(tools, occ_t, env_maps, options[tab_key])
            if options[bgtab_key]:
                write_bg_table(tools, env_maps, options[bgtab_key])

    gs.message(
        "Done. Read table_*/bg_table_* into humboldt.g2e in R "
        "(env.trim=FALSE, rarefy.dist=0). For geographic overlap/divergence "
        "maps afterwards, see r.niche.map."
    )


if __name__ == "__main__":
    atexit.register(cleanup)
    sys.exit(main(*gs.parser()))

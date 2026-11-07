#!/usr/bin/env python3

############################################################################
#
# MODULE:       r.niche.map
# AUTHOR(S):    Paulo van Breugel
# PURPOSE:      Geographic maps of niche overlap and divergence.
#
#               humboldt works entirely in environmental space (PC1 x PC2);
#               it does not produce maps of where, ON THE GROUND, two
#               species' niches overlap or diverge. This module fills that
#               gap WITHOUT recomputing the analysis: it back-projects
#               humboldt's own E-space niche grids onto geography, using
#               humboldt's own PCA rotation, so the maps stay numerically
#               consistent with the R results.
#
#               Pipeline:
#                 1. rebuild PC1/PC2 as geographic rasters from the env
#                    stack and humboldt's PCA rotation (one r.mapcalc each);
#                 2. for every ground cell, look up its (PC1,PC2) in each
#                    species' E-space niche grid  -> geographic suitability;
#                 3. combine: overlap = min(s1,s2), divergence = s1 - s2.
#
#               Streams over the raster (one pass); no per-cell vectors.
#
# REQUIRES:     GRASS GIS 8.5+ 
#
# COPYRIGHT:    (c) 2026 Paulo van Breugel and the GRASS Development Team
#               GNU General Public License (>=v2)
#
############################################################################

# %Module
# % description: Maps geographic niche overlap and divergence by back-projecting humboldt E-space niche grids.
# % keyword: raster
# % keyword: niche modelling
# % keyword: ecology
# %End

# %option G_OPT_R_INPUTS
# % key: env
# % description: Environmental rasters, in the SAME order/subset as the rotation table rows
# % required: yes
# %end

# %option G_OPT_F_INPUT
# % key: rotation
# % description: CSV of humboldt's PCA rotation with header: variable,center,norm,pc1,pc2
# % required: yes
# %end

# %option G_OPT_R_INPUT
# % key: niche_1
# % description: Species-1 E-space niche grid (raster in PC-space, from humboldt.grid.espace)
# % required: yes
# %end

# %option G_OPT_R_INPUT
# % key: niche_2
# % description: Species-2 E-space niche grid
# % required: yes
# %end

# %option G_OPT_R_OUTPUT
# % key: suit_1
# % required: no
# % description: Geographic suitability map, species 1
# % guisection: Output
# %end

# %option G_OPT_R_OUTPUT
# % key: suit_2
# % required: no
# % description: Geographic suitability map, species 2
# % guisection: Output
# %end

# %option G_OPT_R_OUTPUT
# % key: overlap
# % required: no
# % description: Niche overlap map (min of the two suitabilities)
# % guisection: Output
# %end

# %option G_OPT_R_OUTPUT
# % key: divergence
# % required: no
# % description: Niche divergence map (suitability_1 - suitability_2)
# % guisection: Output
# %end

# %option G_OPT_M_NPROCS
# %end

# %rules
# % required: suit_1,suit_2,overlap,divergence
# %end

import atexit
import csv
import sys

import grass.script as gs

from grass.tools import Tools


CLEAN_RAST = []


def cleanup():
    for name in reversed(CLEAN_RAST):
        gs.run_command("g.remove", type="raster", name=name, flags="f",
                       quiet=True, errors="ignore")


def tmp_name(prefix):
    name = gs.append_node_pid(prefix)
    CLEAN_RAST.append(name)
    return name


def read_rotation(path, env_maps):
    """Parse variable,center,norm,pc1,pc2 and align with the env raster list."""
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((float(r["center"]), float(r["norm"]),
                         float(r["pc1"]), float(r["pc2"])))
    if len(rows) != len(env_maps):
        gs.fatal(f"rotation has {len(rows)} rows but env has "
                 f"{len(env_maps)} rasters; they must match 1:1 and in order.")
    return rows


def build_pc_rasters(tools, env_maps, rot, nprocs):
    """PC score rasters in GEOGRAPHIC space:
        PC = sum_j  load_j * (env_j - center_j) / norm_j
    exactly humboldt/ade4's li = scaled_data %*% c1."""
    def expr(load_idx):
        terms = [f"({l[load_idx]})*(({m})-({c}))/({n})"
                 for m, (c, n, l1, l2) in zip(env_maps, rot)
                 for l in [(l1, l2)]]
        return " + ".join(terms)

    pc1 = tmp_name("pc1")
    pc2 = tmp_name("pc2")
    tools.r_mapcalc(expression=f"{pc1} = {expr(0)}", nprocs=nprocs)
    tools.r_mapcalc(expression=f"{pc2} = {expr(1)}", nprocs=nprocs)
    return pc1, pc2


def niche_extent(niche):
    """PC-space bounds of a niche grid raster (its own region)."""
    info = gs.parse_command("r.info", flags="g", map=niche)
    w, e = float(info["west"]), float(info["east"])
    s, n = float(info["south"]), float(info["north"])
    cols, rows = int(info["cols"]), int(info["rows"])
    return w, e, s, n, cols, rows


def check_same_grid(ext_1, ext_2, name_1, name_2):
    """Fail unless the two niche grids describe the same PC-space raster.

    The catmap is built from niche_1's grid and reused to look up niche_2, so
    a different extent or cell count on niche_2 would map its cells to the
    wrong cat and give a wrong suitability map with no error. Bounds are
    compared against a small fraction of a cell, since r.info reports them as
    rounded decimals."""
    w, e, s, n, cols, rows = ext_1
    if (cols, rows) != (ext_2[4], ext_2[5]):
        gs.fatal(
            f"{name_1} is {cols}x{rows} cells but {name_2} is "
            f"{ext_2[4]}x{ext_2[5]}. Both niche grids must come from "
            f"humboldt.grid.espace calls with the same R."
        )
    tol = 1e-6 * min((e - w) / cols, (n - s) / rows)
    for label, a, b in zip(("west", "east", "south", "north"),
                           ext_1[:4], ext_2[:4]):
        if abs(a - b) > tol:
            gs.fatal(
                f"{name_1} and {name_2} differ in their {label} bound "
                f"({a} vs {b}). Both niche grids must span the same PC-space "
                f"extent, which they do when built from one humboldt.g2e run."
            )


def build_catmap(tools, pc1, pc2, ext, nprocs):
    """Linearise each ground cell's (PC1,PC2) to the niche grid cell id
    cat = row*cols + col, or null() where PC falls outside the niche grid."""
    w, e, s, n, cols, rows = ext
    binx = (e - w) / cols
    biny = (n - s) / rows
    catmap = tmp_name("cat")
    col = f"int(({pc1} - {w}) / {binx})"
    row = f"int(({pc2} - {s}) / {biny})"
    valid = f"{pc1} >= {w} && {pc1} < {e} && {pc2} >= {s} && {pc2} < {n}"
    tools.r_mapcalc(
        expression=f"{catmap} = if({valid}, ({row}) * {cols} + ({col}), null())",
        nprocs=nprocs,
    )
    return catmap


def project(tools, niche, catmap, ext, out):
    """Look up each ground cell's niche value: read the niche grid's cells,
    build a cat->value recode table, and recode the geographic catmap."""
    w, e, s, n, cols, rows = ext
    binx = (e - w) / cols
    biny = (n - s) / rows
    rules_path = gs.tempfile()
    with gs.RegionManager():
        tools.g_region(raster=niche)
        stats = gs.read_command("r.stats", input=niche, flags="1gn",
                                separator="space", quiet=True)
    with open(rules_path, "w") as f:
        for line in stats.splitlines():
            east, north, val = line.split()
            c = int((float(east) - w) / binx)
            r_ = int((float(north) - s) / biny)
            cat = r_ * cols + c
            f.write(f"{cat}:{cat}:{val}:{val}\n")
    tools.r_recode(input=catmap, output=out, rules=rules_path)


def main(options, flags):
    tools = Tools()

    env_maps = options["env"].split(",")
    nprocs = int(options["nprocs"])
    rot = read_rotation(options["rotation"], env_maps)

    # Check the niche grids before any raster work, so a mismatch is cheap.
    ext = niche_extent(options["niche_1"])
    check_same_grid(ext, niche_extent(options["niche_2"]),
                    options["niche_1"], options["niche_2"])

    # PC rasters + linearised cell-id map, all in the current (geographic) region
    pc1, pc2 = build_pc_rasters(tools, env_maps, rot, nprocs)
    catmap = build_catmap(tools, pc1, pc2, ext, nprocs)

    need_1 = bool(options["suit_1"] or options["overlap"] or options["divergence"])
    need_2 = bool(options["suit_2"] or options["overlap"] or options["divergence"])

    s1 = s2 = None
    if need_1:
        s1 = options["suit_1"] or tmp_name("s1")
        project(tools, options["niche_1"], catmap, ext, s1)
        tools.r_colors(map=s1, color="viridis")
    if need_2:
        s2 = options["suit_2"] or tmp_name("s2")
        project(tools, options["niche_2"], catmap, ext, s2)
        tools.r_colors(map=s2, color="viridis")

    if options["overlap"] or options["divergence"]:
        # A null suitability means one of two things: the cell's environment
        # lies outside the species' E-space, which scores 0, or there is no
        # env data at all, which must stay null. pc1 and pc2 are built from
        # the same env maps, so either one is null exactly in the second case.
        z1 = f"if(isnull({s1}), 0, {s1})"
        z2 = f"if(isnull({s2}), 0, {s2})"
        no_data = f"isnull({pc1})"
        if options["overlap"]:
            tools.r_mapcalc(
                expression=f"{options['overlap']} = "
                f"if({no_data}, null(), min({z1}, {z2}))",
                nprocs=nprocs,
            )
            tools.r_colors(map=options["overlap"], color="viridis")
        if options["divergence"]:
            tools.r_mapcalc(
                expression=f"{options['divergence']} = "
                f"if({no_data}, null(), ({z1}) - ({z2}))",
                nprocs=nprocs,
            )
            tools.r_colors(map=options["divergence"], color="differences")

    gs.message("Done. overlap = both niches suitable; "
               "divergence > 0 favours species 1, < 0 favours species 2.")


if __name__ == "__main__":
    atexit.register(cleanup)
    sys.exit(main(*gs.parser()))

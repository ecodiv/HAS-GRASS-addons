#!/usr/bin/env python

############################################################################
#
# MODULE:       r.in.ahn.laz
# AUTHOR:       Paulo van Breugel
# PURPOSE:      Downloads LAZ tiles from the AHN (Actueel Hoogtebestand
#               Nederland (AHN), versions 2–6) overlapping with the
#               computational region. Optionally runs a user-provided
#               Python script for each downloaded tile, and patches the
#               resulting raster layers.
#
# COPYRIGHT:    (c) 2026 Paulo van Breugel, and the GRASS Development
#               Team. This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that comes with
#               GRASS for details.
#
#############################################################################

# %module
# % description: Downloads LAZ tiles from the AHN (Actueel Hoogtebestand Nederland (AHN), versions 2–6, and optionally processes each tile with a user-provided script.
# % keyword: lidar
# % keyword: point cloud
# % keyword: import
# %end

# %option
# % key: version
# % type: string
# % label: AHN version
# % description: AHN version to download
# % options: 2,3,4,5,6
# % required: yes
# %end

# %option G_OPT_M_DIR
# % key: directory
# % label: Output directory for LAZ data
# % description: Output directory to which the LAZ data is downloaded (default = working directory)
# % required: no
# % guisection: Output
# %end

# %option G_OPT_F_OUTPUT
# % key: laz_files
# % label: CSV file with list of downloaded LAZ files
# % description: Save the path + names of the downloaded LAZ files to a file
# % required: no
# % guisection: Output
# %end

# %option G_OPT_F_INPUT
# % key: script
# % label: Python script to run for each LAZ tile
# % description: Python script to process each LAZ tile. First non-comment line must be SUFFIXES = [...] declaring output suffixes. The tile path and output prefix are available as the module-level names LAZ and OUTPUT.
# % required: no
# % guisection: Processing
# %end

# %option G_OPT_R_OUTPUT
# % key: output
# % label: Name of the final patched output raster
# % description: If a script is provided, this is used as the base name for the final patched output raster(s). For multi-output scripts, the suffix from each raster is appended (e.g. output_0_1m, output_1_2m).
# % required: no
# % guisection: Output
# %end

# %option G_OPT_MEMORYMB
# %end

# %option G_OPT_M_NPROCS
# %end

# %option
# % key: max_inputs
# % type: integer
# % label: Maximum number of rasters passed to a single r.patch call
# % description: Larger values reduce number of intermediate batches but may exceed OS command length limits
# % required: no
# % answer: 250
# %end

# %flag
# % key: k
# % label: Keep downloaded LAZ files
# % description: Do not delete LAZ files after processing with the user script. By default, each LAZ file is deleted after the script has been run on it.
# %end

# %rules
# % requires: output, script
# %end

import ast
import atexit
import os
import sys
import traceback
import uuid
from math import floor
from multiprocessing import Pool
from urllib.error import URLError, HTTPError
from urllib.request import urlretrieve

import grass.script as gs
from grass.exceptions import CalledModuleError


# AHN overall 1x1 km grid extent (EPSG:28992)
AHN_MIN_X = 12000.0
AHN_MAX_X = 287000.0
AHN_MIN_Y = 304000.0
AHN_MAX_Y = 621000.0
TILE_SIZE = 1000.0

# List of temporary map names to remove on exit. Populated both by
# create_temporary_name() (for maps this module creates directly) and by
# the per-tile processing loop in main() (for maps produced by the user
# script that need to stay around until patching is done).
CLEAN_LAY = []


def cleanup():
    """Remove temporary maps specified in the global list.

    Note: region restoration is handled by the per-tile gs.RegionManager
    in main(), so no explicit del_temp_region is needed here.
    """
    maps = reversed(CLEAN_LAY)
    mapset = gs.gisenv()["MAPSET"]
    for map_name in maps:
        for element in ("raster", "vector"):
            found = gs.find_file(name=map_name, element=element, mapset=mapset)
            if found["file"]:
                gs.run_command(
                    "g.remove",
                    flags="f",
                    type=element,
                    name=map_name,
                    quiet=True,
                )


def create_unique_name(prefix):
    """
    Create a unique GRASS map name by appending a UUID hex string.
    """
    return f"{prefix}_{uuid.uuid4().hex}"


def create_temporary_name(prefix):
    """
    Create a unique temporary map name and register it for cleanup.
    """
    tmp_name = create_unique_name(prefix)
    CLEAN_LAY.append(tmp_name)
    return tmp_name


def get_laz_tile_url(version, x, y):
    """
    Construct the download URL for a single LAZ 1x1 km tile.

    version: '2','3','4','5','6'
    x, y: lower-left corner coordinates (integers, EPSG:28992)
    """

    base = "https://fsn1.your-objectstorage.com/hwh-ahn"

    # Version-dependent directory and filename prefix
    if version in ("2", "3", "4", "5"):
        vdir = f"AHN{version}_KM"
        prefix_base = f"AHN{version}"
    elif version == "6":
        vdir = "AHN6"
        prefix_base = "AHN6_2025"
    else:
        gs.fatal(_("Unsupported AHN version: {v}").format(v=version))

    subdir = "01_LAZ"
    suffix = "C"
    filename = f"{prefix_base}_{suffix}_{int(x):06d}_{int(y):06d}.COPC.LAZ"
    url = f"{base}/{vdir}/{subdir}/{filename}"
    return url


def overlap_with_ahn(region_current):
    """
    Compute the overlap of the current region with the AHN extent.
    Returns (n_ov, s_ov, w_ov, e_ov) and emits a warning if clamped.
    """

    n_cur = float(region_current["n"])
    s_cur = float(region_current["s"])
    w_cur = float(region_current["w"])
    e_cur = float(region_current["e"])

    n_ov = min(n_cur, AHN_MAX_Y)
    s_ov = max(s_cur, AHN_MIN_Y)
    w_ov = max(w_cur, AHN_MIN_X)
    e_ov = min(e_cur, AHN_MAX_X)

    # Check overlap
    if n_ov <= s_ov or e_ov <= w_ov:
        gs.fatal(
            _(
                "The current computational region lies completely outside "
                "the AHN extent "
                "([{xmin}, {ymin}] – [{xmax}, {ymax}] in EPSG:28992)."
            ).format(
                xmin=AHN_MIN_X,
                ymin=AHN_MIN_Y,
                xmax=AHN_MAX_X,
                ymax=AHN_MAX_Y,
            )
        )

    # Warn if clamped
    if (n_ov != n_cur) or (s_ov != s_cur) or (w_ov != w_cur) or (e_ov != e_cur):
        gs.warning(
            _(
                "The current computational region extends outside the AHN extent "
                "([{xmin}, {ymin}] – [{xmax}, {ymax}] in EPSG:28992). "
                "Only the overlapping part will be imported:\n"
                "  n={n}, s={s}, w={w}, e={e}"
            ).format(
                xmin=AHN_MIN_X,
                ymin=AHN_MIN_Y,
                xmax=AHN_MAX_X,
                ymax=AHN_MAX_Y,
                n=n_ov,
                s=s_ov,
                w=w_ov,
                e=e_ov,
            )
        )

    return n_ov, s_ov, w_ov, e_ov


def tiles_for_region(n, s, w, e):
    """
    Compute the list of 1x1 km tile lower-left coordinates (x,y)
    that intersect the given region [w,e] x [s,n].
    """

    # Tile coordinates are lower-left corners, so the last tile's lower-left
    # must be at most AHN_MAX - TILE_SIZE for the tile to fit inside the
    # AHN extent. The `- 1e-9` avoids picking up an extra tile when the
    # region edge sits exactly on a tile boundary.
    x_start = max(AHN_MIN_X, floor(w / TILE_SIZE) * TILE_SIZE)
    x_end = min(AHN_MAX_X - TILE_SIZE, floor((e - 1e-9) / TILE_SIZE) * TILE_SIZE)

    y_start = max(AHN_MIN_Y, floor(s / TILE_SIZE) * TILE_SIZE)
    y_end = min(AHN_MAX_Y - TILE_SIZE, floor((n - 1e-9) / TILE_SIZE) * TILE_SIZE)

    xs = []
    ys = []

    x_val = x_start
    while x_val <= x_end:
        xs.append(x_val)
        x_val += TILE_SIZE

    y_val = y_start
    while y_val <= y_end:
        ys.append(y_val)
        y_val += TILE_SIZE

    tiles = [(x, y) for y in ys for x in xs]
    return tiles


def _download_laz_tile(args):
    """
    Worker function to download a single LAZ tile.

    args = (url, dest)
    Returns dest on success, or None on failure.
    """
    url, dest = args
    try:
        gs.verbose(_("Downloading LAZ tile to {dest}").format(dest=dest))
        urlretrieve(url, dest)
        return dest
    except (HTTPError, URLError, OSError) as e:
        gs.warning(
            _(
                "Failed to download LAZ tile from {url} to {dest}. "
                "Skipping this tile. Error: {err}"
            ).format(url=url, dest=dest, err=e)
        )
        return None


def patch_in_batches(input_maps, output, memory, nprocs, max_inputs):
    """
    Patch many maps safely, avoiding command-line length / r.patch limits.

    - If len(input_maps) == 0, fatal error (nothing to patch).
    - If len(input_maps) == 1, rename the single map to 'output'.
    - If 2 <= len(input_maps) <= max_inputs, run r.patch once directly
      into 'output'.
    - If len(input_maps) > max_inputs, split into chunks of size
      max_inputs, patch each chunk with r.patch (except chunks of
      size 1, which are passed through), then recurse.
    """

    def _run_patch(inputs, out):
        """Run r.patch with shared options and unified error handling."""
        args = {
            "input": ",".join(inputs),
            "output": out,
            "flags": "s",
        }
        if memory > 0:
            args["memory"] = memory
        if nprocs > 1:
            args["nprocs"] = nprocs

        try:
            gs.run_command("r.patch", **args)
        except CalledModuleError as e:
            msg = getattr(e, "errors", "") or str(e)
            if "Too many open files" in msg:
                gs.fatal(
                    _(
                        "r.patch failed because the system limit for open "
                        "files was exceeded.\n"
                        "Try reducing the 'max_inputs' option, lowering "
                        "'nprocs', or increasing the OS open-files limit "
                        "(ulimit -n)."
                    )
                )
            raise

    if not input_maps:
        gs.fatal(_("No input raster maps provided to patch_in_batches."))

    if len(input_maps) == 1:
        single = input_maps[0]
        gs.message(
            _("Only one input map for patching; renaming <{s}> to <{o}>.").format(
                s=single, o=output
            )
        )
        gs.run_command("g.rename", raster=[single, output])
        return

    if len(input_maps) <= max_inputs:
        _run_patch(input_maps, output)
        return

    gs.message(
        _(
            "{n} maps > max_inputs={m}: patching in batches ..."
        ).format(n=len(input_maps), m=max_inputs)
    )

    intermediate = []
    for i in range(0, len(input_maps), max_inputs):
        chunk = input_maps[i : i + max_inputs]
        chunk_idx = i // max_inputs + 1

        if len(chunk) == 1:
            single = chunk[0]
            gs.message(
                _(
                    "  Batch {i}: single map <{s}> reused as intermediate "
                    "(no r.patch needed)."
                ).format(i=chunk_idx, s=single)
            )
            intermediate.append(single)
            continue

        tmp = create_temporary_name(f"{output}_batch")
        gs.message(
            _("  Creating intermediate mosaic from {n} maps").format(n=len(chunk))
        )
        _run_patch(chunk, tmp)
        intermediate.append(tmp)

    patch_in_batches(
        input_maps=intermediate,
        output=output,
        memory=memory,
        nprocs=nprocs,
        max_inputs=max_inputs,
    )


def extract_suffixes(script_path):
    """
    Extract the SUFFIXES list from the user script.

    The first non-comment, non-blank line of the script must be a
    SUFFIXES declaration, e.g.:

        SUFFIXES = ["_0_1m", "_1_2m"]

    For single-output scripts:

        SUFFIXES = [""]

    The value is parsed safely with ast.literal_eval (no code execution).

    Returns a list of suffix strings.
    """
    # Find the first non-comment, non-blank line.
    first_line = None
    with open(script_path, "r") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                first_line = stripped
                break

    if first_line is None:
        gs.fatal(
            _(
                "User script is empty or contains only comments. "
                "The first non-comment line must be a SUFFIXES declaration."
            )
        )

    if not first_line.startswith("SUFFIXES"):
        gs.fatal(
            _(
                "The first non-comment line in the user script must "
                "be a SUFFIXES declaration, e.g.:\n"
                '  SUFFIXES = ["_0_1m", "_1_2m"]\n'
                "or for a single output:\n"
                '  SUFFIXES = [""]\n'
                "Got: {line}"
            ).format(line=first_line)
        )

    # Parse the right-hand side of "SUFFIXES = ..." safely.
    _lhs, _eq, value = first_line.partition("=")
    try:
        suffixes = ast.literal_eval(value.strip())
    except Exception as e:
        gs.fatal(
            _(
                "Could not parse SUFFIXES line in user script.\n"
                "Line: {line}\n"
                "Error: {err}\n"
                'Expected format: SUFFIXES = ["_suffix1", "_suffix2", ...]'
            ).format(line=first_line, err=e)
        )

    # Validate the parsed value.
    if not isinstance(suffixes, (list, tuple)):
        gs.fatal(
            _("SUFFIXES must be a list of strings, got {t}.").format(
                t=type(suffixes).__name__
            )
        )
    if not suffixes:
        gs.fatal(
            _(
                'SUFFIXES list is empty. For a single output, use: SUFFIXES = [""]'
            )
        )
    for s in suffixes:
        if not isinstance(s, str):
            gs.fatal(
                _(
                    "All entries in SUFFIXES must be strings, got {t}: {v}"
                ).format(t=type(s).__name__, v=s)
            )

    return list(suffixes)


def run_script_on_tile(script_path, laz_path, output_prefix):
    """
    Run the user-provided Python script for a single LAZ tile.

    The LAZ file path and output prefix are injected into the user
    script's namespace as the module-level names LAZ and OUTPUT, so
    the user script can simply refer to them:

        import grass.script as gs
        gs.run_command("r.in.pdal", input=LAZ, output=OUTPUT + "_dtm", ...)

    Returns two dicts: raster_by_suffix and vector_by_suffix, mapping
    each suffix to the per-tile map name.
    """
    with open(script_path, "r") as fh:
        script_code = fh.read()

    # The user script runs with a fresh globals dict. LAZ and OUTPUT are
    # the user-facing interface; the rest are the standard modules we
    # make available to avoid forcing every script to re-import them.
    script_globals = {
        "__builtins__": __builtins__,
        "LAZ": laz_path,
        "OUTPUT": output_prefix,
        "os": os,
        "gs": gs,
    }

    try:
        exec(script_code, script_globals)
    except Exception as e:
        gs.warning(
            _(
                "User script failed for tile {laz}.\n"
                "Error: {err}\n"
                "Traceback:\n{tb}"
            ).format(laz=laz_path, err=e, tb=traceback.format_exc())
        )
        return {}, {}

    # Find all rasters and vectors created by the script
    # (names starting with output_prefix)
    mapset = gs.gisenv()["MAPSET"]

    created_rasters = [
        r for r in gs.list_grouped("raster").get(mapset, [])
        if r.startswith(output_prefix)
    ]
    created_vectors = [
        v for v in gs.list_grouped("vector").get(mapset, [])
        if v.startswith(output_prefix)
    ]

    if not created_rasters and not created_vectors:
        gs.warning(
            _(
                "User script did not produce any raster or vector with prefix "
                "'{pfx}' for tile {laz}."
            ).format(pfx=output_prefix, laz=laz_path)
        )
        return {}, {}

    # Group by suffix
    raster_by_suffix = {}
    for name in created_rasters:
        suffix = name[len(output_prefix):]
        raster_by_suffix[suffix] = name

    vector_by_suffix = {}
    for name in created_vectors:
        suffix = name[len(output_prefix):]
        vector_by_suffix[suffix] = name

    return raster_by_suffix, vector_by_suffix


def main(options, flags):
    """
    Download AHN LAZ tiles overlapping the computational region.
    Optionally run a user script on each tile, then patch the results.
    """

    # Check if the projection is RD New (EPSG:28992)
    proj_info = gs.parse_command("g.proj", flags="g")
    if proj_info["srid"] != "EPSG:28992" and proj_info["name"] != "Amersfoort / RD New":
        gs.fatal(_("This module only works with locations with projection EPSG=28992"))

    version = options["version"]
    directory = options["directory"]
    laz_files = options["laz_files"]
    script = options["script"]
    outname = options["output"]
    memory = int(options["memory"])
    nprocs = int(options["nprocs"])
    max_inputs = int(options["max_inputs"])
    keep_laz = flags["k"]

    if nprocs < 1:
        nprocs = 1

    # When a raster mask is active, GRASS can't run r.patch's workers in
    # parallel reliably. This is known behaviour upstream; rather than
    # work around it we just report and fall back to serial processing.
    if nprocs > 1 and gs.find_file(name="MASK", element="cell")["name"] == "MASK":
        gs.warning(
            _(
                "A raster mask is active; parallel processing is not "
                "supported in this case. Falling back to nprocs=1."
            )
        )
        nprocs = 1

    # Validate script file if provided and extract SUFFIXES
    suffixes = None
    if script:
        if not os.path.isfile(script):
            gs.fatal(_("Script file not found: {s}").format(s=script))
        if not outname:
            gs.fatal(
                _(
                    "When a script is provided, the 'output' parameter "
                    "is required to name the final patched output."
                )
            )
        suffixes = extract_suffixes(script)
        intended_names = [f"{outname}{s}" for s in suffixes]
        gs.message(
            _("Script declares {n} output(s): {names}").format(
                n=len(intended_names), names=", ".join(intended_names)
            )
        )

    # Check for existing rasters/vectors that would conflict with the output
    if outname:
        overwrite = gs.overwrite()
        mapset = gs.gisenv()["MAPSET"]

        if not script:
            intended_names = [outname]

        existing = []
        for element in ("raster", "vector"):
            existing_maps = gs.list_grouped(element).get(mapset, [])
            for name in intended_names:
                if name in existing_maps:
                    existing.append(f"{name} [{element}]")

        if existing and not overwrite:
            gs.fatal(
                _(
                    "The following map(s) already exist and would be "
                    "overwritten: {maps}\n"
                    "Use --overwrite to allow overwriting."
                ).format(maps=", ".join(existing))
            )

    # Read the user's computational region once and extract all values we
    # need. The per-tile gs.RegionManager below saves and restores this
    # region around every tile, so user scripts cannot leak region changes
    # past the end of a tile.
    region_current = gs.parse_command("g.region", flags="gu")
    ewres = float(region_current["ewres"])
    nsres = float(region_current["nsres"])

    # Compute overlap of region with AHN extent
    n_ov, s_ov, w_ov, e_ov = overlap_with_ahn(region_current)

    # Compute which tiles we need based on this overlap
    tiles = tiles_for_region(n_ov, s_ov, w_ov, e_ov)
    if not tiles:
        gs.fatal(_("No AHN tiles intersect the requested region."))

    gs.message(_("Preparing to download {} LAZ tiles").format(len(tiles)))

    # Build download jobs. Each job carries its tile's lower-left (x, y)
    # so the per-tile loop can set the region to that tile's extent before
    # running the user script.
    jobs = []
    for x, y in tiles:
        url = get_laz_tile_url(version, x, y)
        filename = os.path.basename(url)
        if directory:
            dest = os.path.join(directory, filename)
        else:
            dest = os.path.join(os.getcwd(), filename)
        jobs.append((url, dest, x, y))

    # --- Mode 1: download only (no script) ---
    if not script:
        download_args = [(url, dest) for url, dest, _x, _y in jobs]
        if nprocs > 1 and len(jobs) > 1:
            gs.message(_("Downloading {} LAZ tiles").format(len(jobs)))
            with Pool(processes=nprocs) as pool:
                results = pool.map(_download_laz_tile, download_args)
        else:
            gs.message(_("Downloading {} LAZ tiles sequentially").format(len(jobs)))
            results = [_download_laz_tile(job) for job in download_args]

        downloaded = [p for p in results if p is not None]

        if not downloaded:
            gs.fatal(_("Download of all requested LAZ tiles failed."))

        # Print or save list of full paths
        if laz_files:
            with open(laz_files, "w") as fh:
                for p in downloaded:
                    fh.write(p + "\n")
        else:
            for path in downloaded:
                print(path)

        gs.message(_("Finished downloading {} LAZ tiles").format(len(downloaded)))
        return 0

    # --- Mode 2: download + run script per tile + patch ---
    gs.message(
        _(
            "Downloading LAZ tiles and processing each with script: {s}"
        ).format(s=script)
    )

    # Dictionaries mapping suffix -> list of per-tile map names
    # e.g. {"_0_1m": ["laz_tile_abc_0_1m", "laz_tile_def_0_1m"], ...}
    # A suffix of "" means the script created a map named exactly OUTPUT
    raster_groups = {}
    vector_groups = {}
    downloaded_paths = []
    tile_count = 0

    for url, dest, tile_x, tile_y in jobs:
        tile_count += 1
        # Progress bar (g.message -p). Shown at default verbosity; picked
        # up by GUI tools as a proper progress indicator.
        gs.percent(tile_count, len(jobs), 1)
        gs.verbose(
            _("Processing tile {n} of {total}").format(
                n=tile_count, total=len(jobs)
            )
        )

        # Download tile
        result = _download_laz_tile((url, dest))
        if result is None:
            continue

        downloaded_paths.append(result)

        # Compute this tile's extent, clipped to the requested overlap so
        # the outer edge tiles don't extend beyond what the user asked for.
        # Tiles are 1x1 km with lower-left (tile_x, tile_y) on the AHN grid.
        tile_w = max(float(tile_x), w_ov)
        tile_e = min(float(tile_x) + TILE_SIZE, e_ov)
        tile_s = max(float(tile_y), s_ov)
        tile_n = min(float(tile_y) + TILE_SIZE, n_ov)

        # Run the user script inside a per-tile region so its outputs
        # match the tile extent (and so any region changes made by the
        # user script are discarded when the block exits).
        with gs.RegionManager(
            n=tile_n,
            s=tile_s,
            w=tile_w,
            e=tile_e,
            ewres=ewres,
            nsres=nsres,
            flags="a",
        ):
            # Create a unique output prefix for this tile
            tile_prefix = create_temporary_name("laz_tile")

            # Run user script
            gs.verbose(_("Running user script on {laz}").format(laz=result))
            raster_by_suffix, vector_by_suffix = run_script_on_tile(
                script, result, tile_prefix
            )

        if not raster_by_suffix and not vector_by_suffix:
            gs.warning(
                _(
                    "Script did not produce output for tile {laz}; skipping."
                ).format(laz=result)
            )
        else:
            produced_suffixes = set(raster_by_suffix.keys()) | set(
                vector_by_suffix.keys()
            )

            # On the first tile, validate produced suffixes against SUFFIXES
            if tile_count == 1:
                expected = set(suffixes)
                extra = produced_suffixes - expected
                missing = expected - produced_suffixes
                if extra:
                    gs.warning(
                        _(
                            "User script created maps with suffixes not "
                            "declared in SUFFIXES: {extra}\n"
                            "These will be treated as intermediate maps "
                            "and removed."
                        ).format(extra=", ".join(sorted(extra)))
                    )
                if missing:
                    gs.warning(
                        _(
                            "User script did not produce maps for all "
                            "declared SUFFIXES. Missing: {miss}"
                        ).format(miss=", ".join(sorted(missing)))
                    )

            # Collect expected outputs, clean up intermediates
            expected_set = set(suffixes)

            for suffix, raster_name in raster_by_suffix.items():
                if suffix in expected_set:
                    if suffix not in raster_groups:
                        raster_groups[suffix] = []
                    raster_groups[suffix].append(raster_name)
                    CLEAN_LAY.append(raster_name)
                else:
                    # Intermediate raster — remove it
                    gs.run_command(
                        "g.remove",
                        type="raster",
                        name=raster_name,
                        flags="f",
                        quiet=True,
                    )

            for suffix, vector_name in vector_by_suffix.items():
                if suffix in expected_set:
                    if suffix not in vector_groups:
                        vector_groups[suffix] = []
                    vector_groups[suffix].append(vector_name)
                    CLEAN_LAY.append(vector_name)
                else:
                    # Intermediate vector — remove it
                    gs.run_command(
                        "g.remove",
                        type="vector",
                        name=vector_name,
                        flags="f",
                        quiet=True,
                    )

        # Delete LAZ file after processing unless -k flag is set
        if not keep_laz:
            try:
                os.remove(result)
                gs.verbose(_("Deleted LAZ file: {f}").format(f=result))
            except OSError as e:
                gs.warning(
                    _("Could not delete LAZ file {f}: {err}").format(f=result, err=e)
                )

    # Save list of downloaded files if requested
    if laz_files:
        with open(laz_files, "w") as fh:
            for p in downloaded_paths:
                fh.write(p + "\n")

    if not raster_groups and not vector_groups:
        gs.fatal(_("No raster or vector output was produced from any LAZ tile."))

    patched_outputs = []

    # Patch raster groups
    if raster_groups:
        gs.message(
            _("Found {n} raster output group(s) to patch: {groups}").format(
                n=len(raster_groups),
                groups=", ".join(
                    f"'{outname}{s}'" if s else f"'{outname}'"
                    for s in sorted(raster_groups.keys())
                ),
            )
        )

        for suffix, tile_rasters in sorted(raster_groups.items()):
            final_name = f"{outname}{suffix}"
            number_of_tiles = len(tile_rasters)

            gs.message(
                _("Patching {n} per-tile rasters into {out}").format(
                    n=number_of_tiles, out=final_name
                )
            )

            patch_in_batches(
                input_maps=tile_rasters,
                output=final_name,
                memory=memory,
                nprocs=nprocs,
                max_inputs=max_inputs,
            )

            patched_outputs.append(f"{final_name} [raster]")

            # Metadata
            gs.run_command(
                "r.support",
                map=final_name,
                title=f"AHN{version} LAZ-derived raster",
                units="meters",
                source1="https://www.ahn.nl",
            )
            gs.run_command(
                "r.support",
                map=final_name,
                history=f"Created by r.in.ahn.laz from {number_of_tiles} LAZ tiles "
                f"using script: {script}",
            )

    # Patch vector groups
    if vector_groups:
        gs.message(
            _("Found {n} vector output group(s) to patch: {groups}").format(
                n=len(vector_groups),
                groups=", ".join(
                    f"'{outname}{s}'" if s else f"'{outname}'"
                    for s in sorted(vector_groups.keys())
                ),
            )
        )

        for suffix, tile_vectors in sorted(vector_groups.items()):
            final_name = f"{outname}{suffix}"
            number_of_tiles = len(tile_vectors)

            gs.message(
                _("Patching {n} per-tile vectors into {out}").format(
                    n=number_of_tiles, out=final_name
                )
            )

            if number_of_tiles > 1:
                try:
                    gs.run_command(
                        "v.patch",
                        input=",".join(tile_vectors),
                        output=final_name,
                        flags="e",
                        quiet=True,
                    )
                except CalledModuleError as e:
                    msg = getattr(e, "errors", "") or str(e)
                    if (
                        "Too many open files" in msg
                        or "Argument list too long" in msg
                    ):
                        gs.fatal(
                            _(
                                "v.patch failed because the number of input "
                                "vectors ({n}) exceeded an OS limit (command-"
                                "line length or open-files limit).\n"
                                "This module does not batch v.patch calls; "
                                "consider reducing the computational region "
                                "or raising the OS limits (ulimit -n, "
                                "ARG_MAX)."
                            ).format(n=number_of_tiles)
                        )
                    raise
            else:
                gs.run_command(
                    "g.rename", vector=[tile_vectors[0], final_name]
                )

            patched_outputs.append(f"{final_name} [vector]")

            # Metadata
            gs.run_command(
                "v.support",
                map=final_name,
                comment=f"Created by r.in.ahn.laz from {number_of_tiles} LAZ tiles "
                f"using script: {script}",
            )

    gs.message(
        "-----------------\n"
        "Finished processing {n} LAZ tiles.\n"
        "Output map(s): {out}\n"
        "-----------------\n\n".format(
            n=len(downloaded_paths),
            out=", ".join(patched_outputs),
        )
    )

    return 0


if __name__ == "__main__":
    atexit.register(cleanup)
    sys.exit(main(*gs.parser()))

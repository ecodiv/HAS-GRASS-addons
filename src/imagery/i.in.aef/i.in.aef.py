#!/usr/bin/env python3

############################################################################
#
# MODULE:       i.in.aef
# AUTHOR(S):    Paulo van Breugel
# PURPOSE:      Downloads and imports AlphaEarth Foundations (AEF) satellite
#               embedding GeoTIFFs, made available by Source Cooperative into
#               GRASS GIS, with region-based COG subsetting, per-zone 
#               patching, and (optionally) de-quantization.
# COPYRIGHT:    (C) 2026 by Paulo van Breugel and the GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
# This program is free software under the GNU General Public
# License (>=v2). Read the file COPYING that comes with GRASS
# for details.
# ############################################################################

# %module
# % description: Imports AlphaEarth Foundations satellite embedding COGs into GRASS GIS.
# % keyword: raster
# % keyword: import
# % keyword: satellite
# % keyword: embeddings
# %end

# %option G_OPT_F_INPUT
# % key: input
# % description: Path to the AEF tile index JSON file
# % required: yes
# % guisection: input
# %end

# %option
# % key: prefix
# % type: string
# % label: Prefix layers
# % description: Prefix for output map names (default: aef_<zone>)
# % required: no
# % guisection: output
# %end

# %option
# % key: mapset
# % type: string
# % label: mapset name
# % description: Mapset name
# % required: no
# % guisection: output
# %end

# %option
# % key: year
# % type: integer
# % description: Year to import (e.g. 2018, 2021)
# % answer: 2024
# % required: no
# % guisection: selection
# %end

# %option
# % key: utm_zone
# % type: string
# % description: UTM zone code to import (e.g. 44N)
# % required: no
# % guisection: selection
# %end

# %option
# % key: memory
# % type: integer
# % description: Maximum memory to be used (in MB)
# % answer: 300
# % required: no
# %end

# %option
# % key: nprocs
# % type: integer
# % description: Number of threads for parallel processing
# % answer: 1
# % required: no
# %end

# %flag
# % key: l
# % description: List available UTM zones, years, and tile counts, then exit
# % guisection: output
# %end

# %flag
# % key: q
# % description: Keep quantized (int8) bands, skip de-quantization
# % guisection: output
# %end

# %rules
# % required: year,-l
# % collective: year,mapset
# %end

import json
import os
import sys
import tempfile
from collections import defaultdict

import grass.script as gs
from grass.tools import Tools

# ---------------------------------------------------------------------------
# AEF de-quantization parameters (Brown et al.)
#   Quantization:   q = clamp(sign(x) * |x|^(1/POWER) * SCALE, MIN, MAX)
#   De-quantization: x = sign(q/SCALE) * |q/SCALE|^POWER
# ---------------------------------------------------------------------------
POWER = 2.0
SCALE = 127.5
NODATA_QUANTIZED = -128

REGION_VECTOR = "aef_tmp_region__"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def s3_to_https(s3_path):
    """Convert S3-style Source Cooperative path to HTTPS URL.

    s3://us-west-2.opendata.source.coop/tge-labs/aef/v1/annual/...
    -> https://data.source.coop/tge-labs/aef/v1/annual/...
    """
    without_scheme = s3_path.replace("s3://", "", 1)
    idx = without_scheme.find("/")
    remainder = without_scheme[idx + 1 :]
    return "https://data.source.coop/{}".format(remainder)


def bboxes_intersect(a_w, a_s, a_e, a_n, b_w, b_s, b_e, b_n):
    """Return True if two bounding boxes overlap."""
    return not (a_e <= b_w or b_e <= a_w or a_n <= b_s or b_n <= a_s)


def compute_bbox_intersection(a_w, a_s, a_e, a_n, b_w, b_s, b_e, b_n):
    """Return (west, south, east, north) of the intersection, or None."""
    w = max(a_w, b_w)
    s = max(a_s, b_s)
    e = min(a_e, b_e)
    n = min(a_n, b_n)
    if w >= e or s >= n:
        return None
    return (w, s, e, n)


def load_records(json_path):
    """Load and return records from the AEF tile index JSON file."""
    try:
        with open(json_path) as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        gs.fatal(_("Cannot read JSON file '{}': {}").format(json_path, e))

    if "records" not in data:
        gs.fatal(_("JSON file does not contain a 'records' key"))

    return data["records"]


def list_tiles(records):
    """Print summary table of UTM zones, years, and tile counts."""
    zone_year_count = defaultdict(int)
    zones = set()
    years = set()
    for rec in records:
        zone = rec["utm_zone"]
        year = rec["year"]
        zone_year_count[(zone, year)] += 1
        zones.add(zone)
        years.add(year)

    sorted_zones = sorted(zones)
    sorted_years = sorted(years)

    gs.message(_("Available data in tile index:"))
    gs.message("\n")
    gs.message(_("UTM zones: {}").format(", ".join(sorted_zones)))
    gs.message(_("Years: {}").format(", ".join(str(y) for y in sorted_years)))
    gs.message("\n")

    hdr = "{:<12s}".format("UTM Zone")
    for y in sorted_years:
        hdr += "{:>8s}".format(str(y))
    gs.message(hdr)
    gs.message("-" * len(hdr))

    for zone in sorted_zones:
        row = "{:<12s}".format(zone)
        for y in sorted_years:
            count = zone_year_count.get((zone, y), 0)
            row += "{:>8d}".format(count)
        gs.message(row)

    gs.message("\n")
    gs.message(_("Total tiles: {}").format(len(records)))


def sanitize_name(name):
    """Make a string safe for use as a GRASS map name."""
    return (
        name.replace(".tiff", "")
        .replace(".tif", "")
        .replace("-", "_")
    )


def fetch_cog_subset(vsicurl_path, dst_path, proj_win):
    """Fetch a spatial subset of a remote COG via /vsicurl/.

    Uses ``gdal.Translate`` with ``projWin`` to read only the COG
    internal tiles that intersect the requested window.  The output
    retains the original pixel layout (bottom-up).

    Parameters
    ----------
    vsicurl_path : str
        GDAL virtual path, e.g. ``/vsicurl/https://data.source.coop/...``
    dst_path : str
        Local output file path.
    proj_win : (ulx, uly, lrx, lry)
        Crop window in the source CRS (UTM).  For bottom-up images the
        "upper left" in pixel space corresponds to the geographic
        south-west, so this must be (west, south, east, north).
    """
    from osgeo import gdal

    gs.message(_("Fetching COG subset from {}").format(vsicurl_path))
    gs.verbose(
        _("  projWin (ulx, uly, lrx, lry): {pw}").format(
            pw=proj_win,
        )
    )

    try:
        opts = gdal.TranslateOptions(
            format="GTiff",
            creationOptions=["COMPRESS=DEFLATE", "BIGTIFF=YES", "TILED=YES"],
            projWin=list(proj_win),
        )
        result = gdal.Translate(dst_path, vsicurl_path, options=opts)
        del result
    except RuntimeError as e:
        gs.fatal(
            _("gdal.Translate failed for {}: {}").format(vsicurl_path, e)
        )


def warp_north_up(src_path, dst_path):
    """Warp a local GeoTIFF from bottom-up to north-up orientation.

    The AEF COGs have the origin at bottom-left (positive y-resolution).
    ``gdal.Warp`` re-orients the raster to the standard north-up layout
    expected by GRASS GIS.

    Parameters
    ----------
    src_path : str
        Path to the downloaded (bottom-up) GeoTIFF.
    dst_path : str
        Output path for the north-up GeoTIFF.
    """
    from osgeo import gdal

    gs.message(_("Warping to north-up..."))

    try:
        opts = gdal.WarpOptions(
            format="GTiff",
            creationOptions=["COMPRESS=DEFLATE", "BIGTIFF=YES", "TILED=YES"],
        )
        result = gdal.Warp(dst_path, src_path, options=opts)
        del result
    except RuntimeError as e:
        gs.fatal(_("gdal.Warp failed for {}: {}").format(src_path, e))


def patch_bands(band_maps, prefix, tools, memory=300, nprocs=1):
    """Patch (mosaic) per-tile maps for each band.

    Parameters
    ----------
    band_maps : dict[int, list[str]]
        Mapping from band number to list of per-tile GRASS map names.
    prefix : str
        Output name prefix, e.g. "aef_44N".
    memory : int
        Memory in MB for r.patch.
    nprocs : int
        Number of threads for r.patch.

    Returns list of patched GRASS map names.
    """
    patched = []
    for band_num in sorted(band_maps):
        tiles = band_maps[band_num]
        out_name = "{}_{}".format(prefix, band_num)
        if len(tiles) == 1:
            tools.g_rename(raster="{},{}".format(tiles[0], out_name), overwrite=True)
        else:
            gs.message(
                _("  Patching {n} tiles for band {b} -> {o}").format(
                    n=len(tiles), b=band_num, o=out_name
                )
            )
            # Set region to cover all input tiles before patching
            tools.g_region(raster=",".join(tiles))
            tools.r_patch(
                input=",".join(tiles), output=out_name,
                memory=memory, nprocs=nprocs, overwrite=True,
            )
            tools.g_remove(type="raster", name=",".join(tiles), flags="f")
        patched.append(out_name)
    return patched


def dequantize(patched_maps, prefix, tools, nprocs=1):
    """Apply AEF de-quantization via r.mapcalc.

    De-quantization (Brown et al.):
        rescaled = q / 127.5
        x = sign(rescaled) * |rescaled|^2.0
    Value -128 -> NULL (masked pixel).

    The output maps use the same prefix as the input, replacing
    the quantized bands in place (callers remove originals after).

    Returns list of de-quantized GRASS map names.
    """
    dequantized = []
    for qmap in patched_maps:
        # Input: prefix_1, prefix_2, ... — extract the band number
        band_suffix = qmap.rsplit("_", 1)[-1]
        # Temporary name to avoid overwriting the input during mapcalc
        dq_tmp = "{}_dq_{}".format(prefix, band_suffix)
        gs.message(_("  De-quantizing {q} -> {d}").format(q=qmap, d=dq_tmp))

        expr = (
            '"{dq}" = '
            "if({q} == {nd}, null(), "
            "if({q} >= 0, 1, -1) * "
            "pow(abs(float({q}) / {s}), {p}))"
        ).format(dq=dq_tmp, q=qmap, nd=NODATA_QUANTIZED, s=SCALE, p=POWER)

        tools.r_mapcalc(expression=expr, nprocs=nprocs, overwrite=True)
        dequantized.append(dq_tmp)
    return dequantized


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    json_path = options["input"]
    year_str = options["year"]
    utm_zone_opt = options["utm_zone"]
    user_prefix = options["prefix"]
    mapset_name = options["mapset"]
    memory = int(options["memory"])
    nprocs = int(options["nprocs"])
    list_flag = flags["l"]
    skip_dequantize = flags["q"]

    # ------------------------------------------------------------------
    # Load tile index
    # ------------------------------------------------------------------
    records = load_records(json_path)
    if not records:
        gs.fatal(_("Tile index contains no records"))

    # ------------------------------------------------------------------
    # List mode
    # ------------------------------------------------------------------
    if list_flag:
        list_tiles(records)
        return

    # ------------------------------------------------------------------
    # Import mode — validate required options
    # ------------------------------------------------------------------
    if not year_str:
        gs.fatal(_("Option <year> is required when not using the -l flag"))
    year = int(year_str)

    # Filter by year
    records = [r for r in records if r["year"] == year]
    if not records:
        gs.fatal(_("No tiles found for year {}").format(year))

    # Validate and filter by UTM zone
    available_zones = sorted(set(r["utm_zone"] for r in records))
    if utm_zone_opt:
        if utm_zone_opt not in available_zones:
            gs.fatal(
                _("UTM zone '{z}' not found in tile index for year {y}. "
                  "Available zones: {a}").format(
                    z=utm_zone_opt, y=year, a=", ".join(available_zones)
                )
            )
        records = [r for r in records if r["utm_zone"] == utm_zone_opt]

    # ------------------------------------------------------------------
    # Save original session info
    # ------------------------------------------------------------------
    env = gs.gisenv()
    orig_gisdbase = env["GISDBASE"]
    orig_project = env["LOCATION_NAME"]
    orig_mapset = env["MAPSET"]

    tools = Tools(overwrite=True)

    # ------------------------------------------------------------------
    # Create a vector from the current computational region
    # ------------------------------------------------------------------
    gs.message(_("Saving current region as vector for reprojection..."))
    tools.v_in_region(output=REGION_VECTOR, overwrite=True)

    # ------------------------------------------------------------------
    # Get WGS84 bounds of the current region for initial tile filtering
    # ------------------------------------------------------------------
    region_ll = gs.parse_command("g.region", flags="bg")
    ll_n = float(region_ll["ll_n"])
    ll_s = float(region_ll["ll_s"])
    ll_e = float(region_ll["ll_e"])
    ll_w = float(region_ll["ll_w"])

    gs.message(
        _("Region extent (WGS84): W={w}, S={s}, E={e}, N={n}").format(
            w=ll_w, s=ll_s, e=ll_e, n=ll_n
        )
    )

    # Filter tiles that intersect the region
    filtered = []
    for rec in records:
        if bboxes_intersect(
            ll_w, ll_s, ll_e, ll_n,
            rec["wgs84_west"], rec["wgs84_south"],
            rec["wgs84_east"], rec["wgs84_north"],
        ):
            filtered.append(rec)
        else:
            gs.verbose(
                _("Skipping tile {} (outside region)").format(
                    rec["path"].split("/")[-1]
                )
            )
    records = filtered
    if not records:
        tools.g_remove(type="vector", name=REGION_VECTOR, flags="f")
        gs.fatal(_("No tiles intersect the current computational region"))

    gs.message(
        _("Selected {n} tile(s) for year {y}").format(n=len(records), y=year)
    )

    # Group by UTM zone
    by_zone = defaultdict(list)
    for rec in records:
        by_zone[rec["utm_zone"]].append(rec)

    # ------------------------------------------------------------------
    # Configure GDAL
    # ------------------------------------------------------------------
    from osgeo import gdal

    gdal.UseExceptions()

    # vsicurl settings for efficient COG access
    gdal.SetConfigOption("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
    gdal.SetConfigOption("GDAL_INGESTED_BYTES_AT_OPEN", "32768")
    gdal.SetConfigOption("VSI_CACHE", "TRUE")
    gdal.SetConfigOption("VSI_CACHE_SIZE", "128000000")  # 128 MB

    # User-Agent to avoid 403 from Cloudflare
    gdal.SetConfigOption("GDAL_HTTP_USERAGENT", "i.in.aef/1.0 (GRASS GIS)")

    # ------------------------------------------------------------------
    # Process each UTM zone
    # ------------------------------------------------------------------
    for utm_zone, tiles in by_zone.items():
        epsg_code = tiles[0]["crs"].split(":")[1]
        project_name = "UTM{}".format(utm_zone)
        project_path = os.path.join(orig_gisdbase, project_name)

        # Layer name prefix
        if user_prefix:
            prefix = user_prefix
        else:
            prefix = "aef_{}".format(utm_zone)

        gs.message("=" * 60)
        gs.message(
            _("Processing UTM zone {z} (EPSG:{e}, {n} tile(s))").format(
                z=utm_zone, e=epsg_code, n=len(tiles)
            )
        )
        gs.message("=" * 60)

        # Create the UTM project if it does not exist
        if not os.path.isdir(project_path):
            gs.message(
                _("Creating project '{p}' with EPSG:{e}").format(
                    p=project_name, e=epsg_code
                )
            )
            gs.create_project(project_path, epsg=epsg_code)

        # Switch to PERMANENT to set up region
        gs.run_command("g.mapset", mapset="PERMANENT", project=project_name)

        # Reproject the region vector from the original project
        gs.message(_("Reprojecting region to UTM zone {}...").format(utm_zone))
        tools.v_proj(
            input=REGION_VECTOR,
            project=orig_project,
            mapset=orig_mapset,
            overwrite=True,
        )

        # Set the computational region from the reprojected vector
        # and save as default region for this project (-s flag)
        tools.g_region(vector=REGION_VECTOR, flags="s")

        # Create (or switch to) the user's mapset
        gs.message(
            _("Switching to mapset '{}'...").format(mapset_name)
        )
        tools.g_mapset(flags="c", mapset=mapset_name)

        # Set the region in this mapset from the reprojected vector
        # (accessible from PERMANENT)
        tools.g_region(vector=REGION_VECTOR)

        # Read back the UTM region bounds
        region_utm = gs.parse_command("g.region", flags="g")
        reg_w = float(region_utm["w"])
        reg_s = float(region_utm["s"])
        reg_e = float(region_utm["e"])
        reg_n = float(region_utm["n"])

        gs.message(
            _("UTM region: W={w}, S={s}, E={e}, N={n}").format(
                w=reg_w, s=reg_s, e=reg_e, n=reg_n
            )
        )

        # band_num -> [list of per-tile map names]
        band_maps = defaultdict(list)

        tmpdir = tempfile.mkdtemp(prefix="aef_")
        try:
            for idx, tile in enumerate(tiles):
                url = s3_to_https(tile["path"])
                vsicurl = "/vsicurl/{}".format(url)
                tile_file = tile["path"].split("/")[-1]
                base = sanitize_name(tile_file)

                subset_path = os.path.join(
                    tmpdir, "subset_{}".format(tile_file)
                )
                warped_path = os.path.join(
                    tmpdir, "northup_{}".format(tile_file)
                )

                gs.message(
                    _("Tile {i}/{t}: {f}").format(
                        i=idx + 1, t=len(tiles), f=tile_file
                    )
                )

                # Compute intersection of region and tile extent (UTM)
                isect = compute_bbox_intersection(
                    reg_w, reg_s, reg_e, reg_n,
                    tile["utm_west"], tile["utm_south"],
                    tile["utm_east"], tile["utm_north"],
                )
                if isect is None:
                    gs.warning(
                        _("Tile {} does not intersect UTM region, "
                          "skipping").format(tile_file)
                    )
                    continue

                clip_w, clip_s, clip_e, clip_n = isect

                # Step 1: Fetch only the intersecting subset from the COG
                #         Bottom-up image: pixel origin is at south-west,
                #         so projWin (ulx, uly, lrx, lry) = (west, south, east, north)
                fetch_cog_subset(
                    vsicurl, subset_path,
                    proj_win=(clip_w, clip_s, clip_e, clip_n),
                )

                # Step 2: Warp locally to fix bottom-up orientation
                warp_north_up(subset_path, warped_path)
                os.remove(subset_path)

                # Step 3: Import all bands; r.in.gdal creates
                #         maps named base.1, base.2, ... base.64
                #         Flag -r restricts import to the current region
                gs.message(_("Importing {}...").format(base))
                tools.r_in_gdal(
                    input=warped_path,
                    output=base,
                    memory=memory,
                    overwrite=True,
                    flags="or",
                )

                # Discover the number of imported bands
                ds = gdal.Open(warped_path)
                n_bands = ds.RasterCount
                del ds

                for band_num in range(1, n_bands + 1):
                    band_maps[band_num].append(
                        "{}.{}".format(base, band_num)
                    )

                # Remove warped file
                os.remove(warped_path)

        finally:
            try:
                os.rmdir(tmpdir)
            except OSError:
                pass

        if not band_maps:
            gs.warning(
                _("No bands imported for UTM zone {}").format(utm_zone)
            )
            continue

        # Patch tiles per band (region is set from rasters inside
        # patch_bands before each r.patch call)
        gs.message(_("Patching bands for UTM zone {}...").format(utm_zone))
        patched = patch_bands(band_maps, prefix, tools,
                              memory=memory, nprocs=nprocs)

        # Set region from the patched result
        tools.g_region(raster=patched[0])

        if skip_dequantize:
            # Keep quantized bands as-is
            final_maps = patched
        else:
            # De-quantize
            gs.message(
                _("De-quantizing bands for UTM zone {}...").format(utm_zone)
            )
            dq_maps = dequantize(patched, prefix, tools, nprocs=nprocs)

            # Remove the original quantized bands
            tools.g_remove(
                type="raster", name=",".join(patched), flags="f"
            )

            # Rename de-quantized maps to final names (prefix_1, prefix_2, ...)
            final_maps = []
            for dq_map in dq_maps:
                band_suffix = dq_map.rsplit("_", 1)[-1]
                final_name = "{}_{}".format(prefix, band_suffix)
                tools.g_rename(
                    raster="{},{}".format(dq_map, final_name),
                    overwrite=True,
                )
                final_maps.append(final_name)

        # Apply grey color table to all output layers
        gs.message(_("Setting grey color table..."))
        for map_name in final_maps:
            gs.run_command("r.colors", map=map_name, color="grey")

        # Register all bands in an imagery group
        group_name = prefix
        tools.i_group(group=group_name, input=",".join(final_maps))
        gs.message(
            _("Imagery group '{g}' created in project '{p}', "
              "mapset '{m}' with {n} bands").format(
                g=group_name, p=project_name, m=mapset_name,
                n=len(final_maps)
            )
        )

        # Clean up the temporary region vector in PERMANENT
        tools.g_mapset(mapset="PERMANENT")
        tools.g_remove(type="vector", name=REGION_VECTOR, flags="f")

    # ------------------------------------------------------------------
    # Switch back to the original project and mapset
    # ------------------------------------------------------------------
    gs.run_command(
        "g.mapset", mapset=orig_mapset, project=orig_project
    )

    # Clean up temporary region vector in the original project
    tools.g_remove(type="vector", name=REGION_VECTOR, flags="f")

    gs.message(_("All zones processed successfully"))


if __name__ == "__main__":
    options, flags = gs.parser()
    main()

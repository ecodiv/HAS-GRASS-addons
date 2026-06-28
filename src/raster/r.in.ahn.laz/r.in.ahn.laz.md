## DESCRIPTION

_r.in.ahn.laz_ downloads 1 × 1 km LAZ point-cloud tiles from the _Actueel Hoogtebestand Nederland (AHN)_ that intersect the current computational region, and optionally processes each tile with a user-provided Python script and patches the per-tile results into a seamless mosaic.

The module supports AHN versions 2 to 6. For versions 2–5 the filename prefix is `AHN{version}`; for version 6 it is `AHN6_2025`. All tiles are COPC-compressed LAZ (`.COPC.LAZ`) in EPSG:28992 (Amersfoort / RD New). The module will refuse to run in any other projection.

_r.in.ahn.laz_ has two modes of operation, selected by whether the **script=** option is given:

**Mode 1, download only.** If **script=** is not provided, the module just downloads every LAZ tile that intersects the current region and either prints their full paths to standard output or, if **laz\_files=** is given, writes them to that file. No raster output is produced.

**Mode 2, download + process + patch.** If **script=** points to a user Python script, the module processes tiles one at a time: download the tile, run the script on it, delete the LAZ file (unless **\-k** is set), and collect the script's raster and/or vector outputs. After all tiles are processed, the per-tile outputs are patched into one or more final maps whose names are built from **output=** and the suffixes declared by the script (see _User script interface_ below). In this mode, **output=** is required; **laz\_files=** is still honored and writes the list of downloaded files as a side effect.

## Tile selection

r.in.ahn.laz selects and downloads every AHN tile whose footprint overlaps the user's region. If a script is provided, each tile is processed inside a computational region clipped to the user's region, so only the overlapping part is imported into GRASS and passed to the script.

Note that if the computational region extends outside the AHN extent (EPSG:28992: x ∈ \[12000, 287000\], y ∈ \[304000, 621000\]), a warning is emitted and only the overlap is imported. If the region lies entirely outside, the module aborts.

## User script interface

A user script is a plain Python file. Its structure is:

1.  The **first non-comment, non-blank line** must be a `SUFFIXES` declaration — a list of strings, one per output map the script produces. Example: `SUFFIXES = ["_dtm", "_dsm"]`. For a single-output script, use `SUFFIXES = [""]`.
2.  The rest of the file is arbitrary Python. When the script runs, the following names are pre-injected into its global namespace:
    1.  `LAZ`: Full path to the LAZ tile file that was just downloaded.
    2.  `OUTPUT`: Unique per-tile name prefix. Every map the script creates whose name starts with `OUTPUT + suffix` (where suffix is one of the strings in `SUFFIXES`) is collected for patching.
    3.  `os`: Standard `os` module, pre-imported for convenience; the script can use it without import os.
    4.  `gs`: grass.script, pre-imported for convenience; no need to import it in the script.

The script must produce one raster or vector map per declared suffix, named exactly `OUTPUT + suffix`. Maps whose names match `OUTPUT*` but whose suffix is not in `SUFFIXES` are treated as intermediate and removed automatically after the tile completes (the module warns once, on the first tile, when this happens). Maps that do not start with `OUTPUT` are left alone — the user script is responsible for cleaning those up itself.

After all tiles are processed, each declared suffix produces one patched map named **output + suffix** (for a single-output script with `SUFFIXES = [""]`, the final map is simply **output**).

## NOTES

### Projection

The current project must use EPSG:28992 (Amersfoort / RD New). The module aborts otherwise. This is the native AHN CRS; reprojecting LAZ data on the fly is out of scope.

### Parallel processing and masks

When a raster mask is active in the mapset, parallel processing is not supported. If **nprocs=** is set to more than 1 and a mask is active, the module warns and falls back to **nprocs=1** for the entire run. Disable the mask if parallel processing is needed.

### Disk usage

Each LAZ tile is downloaded to **directory=** (or the current working directory if not set). By default, each tile is deleted after the user script has processed it. Use **\-k** to keep the LAZ files on disk.

### Batching of patch operations

When many tiles are requested, _r.in.ahn.laz_ patches raster outputs in batches of at most **max\_inputs=** inputs (default 50), recursing until a single mosaic remains. This avoids hitting the OS command-line length limit and the "too many open files" limit. If you do hit the latter, lower **max\_inputs=**, lower **nprocs=**, or raise your OS file-descriptor limit (`ulimit -n`).

**max\_inputs=** is not (yet) implemented for the patching of vetor outputs. Therefore, vector outputs are patched in a single _v.patch_ call, and **max\_inputs=** has no effect on them. If the number of per-tile vectors is large enough to exceed an OS limit, _r.in.ahn.laz_ aborts with a clear fatal message naming the limit. 

### Requirements

*   GRASS GIS ≥ 8.5 (uses `gs.RegionManager`, which was introduced in version 8.5).
*   Network access to the AHN LAZ object storage bucket.
*   Whatever the user script itself needs. For instance, _r.in.pdal_ must be installed if the script uses it.

### KNOWN ISSUES

*   A single failed tile download is reported as a warning and the tile is skipped; the module continues with the remaining tiles. If _all_ downloads fail, the module aborts.
*   When **nprocs > 1** and a mask is active, processing silently falls back to serial (a warning is emitted). This is by design — GRASS parallel `r.patch` does not reliably honor masks.

## EXAMPLES

All examples assume the current project is in EPSG:28992 and the computational region has been set to an area of interest inside the Netherlands.

### Example 1

Download every AHN4 LAZ tile that intersects the current region into `/tmp/laz`, and save the list of file paths to `ahn_files.txt`:

```sh
g.region n=436948 s=430912 w=90450 e=98479 res=0.5
r.in.ahn.laz version=4 directory=/tmp/laz laz_files=ahn_files.txt
```

No GRASS raster is produced; the downloaded files remain on disk.

### Example 2

Create a DTM mosaic with the user script `make_dtm.py`:

```python
SUFFIXES = [""]

gs.run_command(
    "r.in.pdal",
    input=LAZ,
    output=OUTPUT,
    method="mean",
    resolution=0.5,
    class_filter="2", 
    flags="o",
)
```

Run it:

```sh
g.region n=436948 s=430912 w=90450 e=98479 res=0.5
r.in.ahn.laz \
    version=4 \
    script=make_dtm.py \
    output=ahn4_dtm \
    nprocs=4 \
    memory=8000
```

Result: a single raster **ahn4\_dtm** covering the region, patched from per-tile rasters. The LAZ files are deleted as they are processed. Note, normally one would want to import the AHN DTM directly using the `r.in.ahn` module.

### Example 3

DTM + DSM in one pass with user script `dtm_dsm.py`:

```python
SUFFIXES = ["_dtm", "_dsm"]

# DTM from ground points
gs.run_command(
    "r.in.pdal",
    input=LAZ,
    output=OUTPUT + "_dtm",
    method="mean",
    resolution=0.5,
    class_filter="2",
    flags="o",
)

# DSM from first returns
gs.run_command(
    "r.in.pdal",
    input=LAZ,
    output=OUTPUT + "_dsm",
    method="max",
    resolution=0.5,
    return_filter="first",
    flags="o",
)
```

Run it:

```sh
r.in.ahn.laz \
    version=5 \
    script=dtm_dsm.py \
    output=zuiderpark \
    nprocs=8 memory=20000 max_inputs=25
```

Result: two rasters, **zuiderpark\_dtm** and **zuiderpark\_dsm**. The suffixes declared in `SUFFIXES` are appended to **output=** to form the final map names. Note, normally one would want to import the AHN DTM and DSM directly using the `r.in.ahn` module.

### Example 4

If the user script produces extra maps whose suffix is not in `SUFFIXES`, those are cleaned up automatically. This lets a script use intermediate maps without polluting the mapset: user script `chm.py`:

```python
SUFFIXES = ["_chm"]

# Intermediate DTM (ground points, class 2). Not in SUFFIXES -> removed
# after this tile.
gs.run_command(
    "r.in.pdal",
    input=LAZ, output=OUTPUT + "_dtm",
    method="mean", resolution=0.5,
    class_filter="2",
    flags="o",
)

# Intermediate DSM (first returns, highest surface). Also not in SUFFIXES.
gs.run_command(
    "r.in.pdal",
    input=LAZ, output=OUTPUT + "_dsm",
    method="max", resolution=0.5,
    return_filter="first",
    flags="o",
)

# Intended output: Canopy Height Model = DSM - DTM. Clamp tiny negatives
# (from noise or misclassified ground) to zero.
gs.mapcalc(
    f"{OUTPUT}_chm = max(0.0, {OUTPUT}_dsm - {OUTPUT}_dtm)",
)
```

The `_dtm` and `_dsm` per-tile rasters are intermediates and get cleaned up after each tile; only `_chm` is kept and patched into the final mosaic `output_chm`.

```
r.in.ahn.laz \
    version=5 \
    script=chm.py \
    output=zuiderpark \
    nprocs=8 memory=20000 max_inputs=25
```

Result: a raster **zuiderpark\_chm**. Note, in most cases it will be faster to use the `r.in.ahn` module to obtain the CHM. Use the example above if you want the CHM at an higher resultion.

## SEE ALSO

[_r.in.pdal_](https://grass.osgeo.org/grass-stable/manuals/r.in.pdal.html)_,_ [_r.in.ahn_](https://grass.osgeo.org/grass-stable/manuals/addons/r.in.ahn.html)

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl), [Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/), [Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)
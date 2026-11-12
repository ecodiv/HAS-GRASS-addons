#!/usr/bin/env python3

##############################################################################
# MODULE:    t.rast.import.cru
#
# AUTHOR(S): Paulo van Breugel <paulo ecodiv earth>
#
# PURPOSE:   Import a CRU TS climate data file (NetCDF) as a space time
#            raster dataset (STRDS)
#
# COPYRIGHT: (C) 2026 by Paulo van Breugel and the GRASS Development Team
#
#            This program is free software under the GNU General Public
#            License (>=v2). Read the file COPYING that comes with GRASS
#            for details.
#
# SPDX-License-Identifier: GPL-2.0-or-later
##############################################################################

# %module
# % description: Imports a CRU TS climate data file (NetCDF) as a space time raster dataset.
# % keyword: temporal
# % keyword: import
# % keyword: raster
# % keyword: time
# % keyword: netcdf
# % keyword: climate
# %end

# %option G_OPT_F_INPUT
# % key: input
# % label: Name of the input CRU TS NetCDF file
# % description: Uncompressed (.nc) and gzip compressed (.nc.gz) files are both accepted
# %end

# %option
# % key: variable
# % type: string
# % required: no
# % label: Name of the climate variable to import
# % description: Defaults to the only climate variable in the input file, e.g. pre, tmp, tmn or tmx
# %end

# %option G_OPT_STRDS_OUTPUT
# % key: output
# % description: Name of the output space time raster dataset
# %end

# %option G_OPT_R_BASENAME_OUTPUT
# % key: basename
# % required: no
# % label: Basename of the imported raster maps
# % description: Maps are named basename_YYYY_MM; defaults to the name of the variable
# %end

# %option
# % key: title
# % type: string
# % required: no
# % description: Title of the output space time raster dataset
# %end

# %option
# % key: description
# % type: string
# % required: no
# % description: Description of the output space time raster dataset
# %end

# %option
# % key: semantictype
# % type: string
# % required: no
# % options: min,max,sum,mean
# % answer: mean
# % description: Semantic type of the output space time raster dataset
# %end

# %option G_OPT_MEMORYMB
# %end

# %flag
# % key: o
# % label: Override projection check (use current project's CRS)
# % description: Assume that the input file has the same CRS as the current project
# %end

# %flag
# % key: r
# % description: Limit import to the current region
# %end

# %flag
# % key: a
# % description: Append the imported maps to an existing space time raster dataset
# %end

import atexit
import gzip
import os
import re
import shutil
import sys
from datetime import datetime, timedelta

import grass.script as gs
import grass.temporal as tgis

# A CRU TS file holds the climate variable itself next to "stn", the number of
# stations that contributed to each cell. Only the former is data to import,
# so "stn" is passed over when the variable is detected rather than given.
AUXILIARY_VARIABLES = {"stn"}

# CF time units, mapped onto the datetime.timedelta keyword they correspond to.
# Calendar-dependent units ("months since", "years since") are absent on
# purpose: they have no fixed length, and CRU TS does not use them.
TIME_STEPS = {
    "seconds": "seconds",
    "second": "seconds",
    "minutes": "minutes",
    "minute": "minutes",
    "hours": "hours",
    "hour": "hours",
    "days": "days",
    "day": "days",
}

# Calendars whose dates this module can compute with datetime, which counts
# days the proleptic Gregorian way. CRU TS uses "gregorian".
SUPPORTED_CALENDARS = {"standard", "gregorian", "proleptic_gregorian"}

# What the module created, to be removed again when it does not run to the end,
# so that a failure does not leave a partial import behind. The maps are first
# imported under temporary names and renamed afterwards, hence the two entries:
# "raster_pattern" covers the maps while they still carry temporary names.
CREATED = {"directory": None, "raster_pattern": None, "rasters": []}


def cleanup():
    """Remove the scratch directory and any maps that should not survive"""
    if CREATED["directory"]:
        shutil.rmtree(CREATED["directory"], ignore_errors=True)
    if CREATED["raster_pattern"]:
        gs.run_command(
            "g.remove",
            type="raster",
            pattern=CREATED["raster_pattern"],
            flags="f",
            quiet=True,
        )
    if CREATED["rasters"]:
        gs.run_command(
            "g.remove", type="raster", name=CREATED["rasters"], flags="f", quiet=True
        )


def parse_time_units(units):
    """Split a CF "<step> since <reference>" string into its two parts

    :param str units: value of the NetCDF time#units attribute of the input
                      file, for example "days since 1900-1-1"

    :return: the datetime.timedelta keyword for the step, and the moment the
             time coordinates are counted from
    :rtype: tuple(str, datetime.datetime)
    """
    match = re.match(r"(\w+)\s+since\s+(.+)", units.strip())
    if not match:
        gs.fatal(
            _(
                "Cannot read the time units <{}> of the input file. Expected "
                "a CF time unit of the form 'days since 1900-1-1'."
            ).format(units)
        )
    step = match.group(1).lower()
    if step not in TIME_STEPS:
        gs.fatal(
            _(
                "The time unit <{}> of the input file is not supported. Use one of: {}."
            ).format(step, ", ".join(sorted(TIME_STEPS)))
        )
    # The reference moment may or may not carry a time of day, and CRU TS
    # writes single digit months and days ("1900-1-1"), which rules out a
    # fixed strptime format.
    reference = re.match(
        r"(\d{1,4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?",
        match.group(2).strip(),
    )
    if not reference:
        gs.fatal(
            _(
                "Cannot read the reference date in the time units <{}> of the input file."
            ).format(units)
        )
    year, month, day = (int(part) for part in reference.group(1, 2, 3))
    hour, minute, second = (int(part or 0) for part in reference.group(4, 5, 6))
    return TIME_STEPS[step], datetime(year, month, day, hour, minute, second)


def month_around(moment):
    """First day of the month holding *moment*, and first day of the next month

    The pair spans the whole month and thus forms the time interval of a
    monthly map.

    :param datetime.datetime moment: a moment within the month

    :return: start and end of the month
    :rtype: tuple(datetime.datetime, datetime.datetime)
    """
    start = datetime(moment.year, moment.month, 1)
    if start.month == 12:
        return start, datetime(start.year + 1, 1, 1)
    return start, datetime(start.year, start.month + 1, 1)


def monthly_intervals(offsets, units):
    """Turn the time axis of the input file into one time interval per layer

    CRU TS stamps every layer in the middle of the month it describes. Each
    stamp is therefore widened to the whole month, which gives the gapless
    series of intervals that t.register expects.

    :param list offsets: time coordinate of each layer, in *units*
    :param str units: value of the NetCDF time#units attribute

    :return: start and end of the month described by each layer
    :rtype: list of tuple(datetime.datetime, datetime.datetime)
    """
    step, reference = parse_time_units(units)
    intervals = [
        month_around(reference + timedelta(**{step: offset})) for offset in offsets
    ]
    # Both the map names (basename_YYYY_MM) and the gapless intervals rely on
    # there being exactly one layer per consecutive month, so anything else is
    # refused rather than silently misdated.
    for (start, end), (next_start, _next_end) in zip(intervals, intervals[1:]):
        if next_start != end:
            gs.fatal(
                _(
                    "The input file is not a continuous monthly series: the "
                    "layer for {current} is followed by one for {found} "
                    "instead of {expected}."
                ).format(
                    current=start.strftime("%Y-%m"),
                    found=next_start.strftime("%Y-%m"),
                    expected=end.strftime("%Y-%m"),
                )
            )
    return intervals


def select_variable(dataset, requested, input_file, netcdf_file):
    """Pick the variable to import and the GDAL name that reads its layers

    :param dataset: the input file, opened with GDAL
    :param str requested: the variable asked for, empty when it is to be
                          detected
    :param str input_file: name of the file as given, for messages
    :param str netcdf_file: name of the file GDAL reads, which is the
                            decompressed copy for a compressed input file

    :return: the name of the variable, and the GDAL dataset name that holds
             its layers
    :rtype: tuple(str, str)
    """
    # A subdataset is named NETCDF:"<file>":<variable>, and the file name is
    # quoted, so the variable is what follows the last colon.
    subdatasets = {
        name.rsplit(":", 1)[-1]: name for name, _description in dataset.GetSubDatasets()
    }

    if not subdatasets:
        # A NetCDF file that holds a single variable has no subdatasets: GDAL
        # offers the layers of that variable as the bands of the file itself.
        if not dataset.RasterCount:
            gs.fatal(
                _(
                    "The file <{}> holds no raster data. Is it a CRU TS NetCDF file?"
                ).format(input_file)
            )
        variable = dataset.GetRasterBand(1).GetMetadataItem("NETCDF_VARNAME")
        if not variable:
            gs.fatal(
                _(
                    "The file <{}> holds no NetCDF variables. Is it a CRU TS "
                    "NetCDF file?"
                ).format(input_file)
            )
        if requested and requested != variable:
            gs.fatal(
                _("The file <{}> holds no variable <{}>. It holds: {}.").format(
                    input_file, requested, variable
                )
            )
        return variable, netcdf_file

    if requested:
        if requested not in subdatasets:
            gs.fatal(
                _("The file <{}> holds no variable <{}>. It holds: {}.").format(
                    input_file, requested, ", ".join(sorted(subdatasets))
                )
            )
        return requested, subdatasets[requested]
    candidates = sorted(set(subdatasets) - AUXILIARY_VARIABLES)
    if len(candidates) != 1:
        gs.fatal(
            _(
                "Cannot tell which variable of <{}> to import. Name one with "
                "the variable option. The file holds: {}."
            ).format(input_file, ", ".join(sorted(subdatasets)))
        )
    return candidates[0], subdatasets[candidates[0]]


def read_time_axis(layers, variable, input_file):
    """Read the time coordinate of every layer of the variable

    :param layers: the layers of the variable, opened with GDAL
    :param str variable: name of the variable, for messages
    :param str input_file: name of the input file, for messages

    :return: the time coordinates and the NetCDF time#units attribute
    :rtype: tuple(list, str)
    """
    metadata = layers.GetMetadata()
    units = metadata.get("time#units")
    if not units:
        gs.fatal(
            _(
                "The variable <{}> of <{}> has no time axis, so its layers "
                "cannot be dated."
            ).format(variable, input_file)
        )
    calendar = metadata.get("time#calendar", "standard").lower()
    if calendar not in SUPPORTED_CALENDARS:
        gs.fatal(
            _(
                "The input file uses the <{}> calendar, which this module "
                "cannot convert into calendar dates."
            ).format(calendar)
        )
    offsets = []
    for band in range(1, layers.RasterCount + 1):
        offset = layers.GetRasterBand(band).GetMetadataItem("NETCDF_DIM_time")
        if offset is None:
            gs.fatal(
                _(
                    "Layer {} of variable <{}> of <{}> carries no time coordinate."
                ).format(band, variable, input_file)
            )
        offsets.append(float(offset))
    return offsets, units


def check_output_names(map_names, strds, append):
    """Refuse to start when the output maps or dataset are in the way

    Both are checked before anything is imported, so that a name clash costs
    nothing more than the message reporting it.

    :param list map_names: names the imported maps will get
    :param str strds: name of the output space time raster dataset
    :param bool append: whether the dataset is to be appended to
    """
    existing = set(gs.read_command("g.list", type="raster", mapset=".").splitlines())
    clashes = sorted(existing.intersection(map_names))
    if clashes and not gs.overwrite():
        gs.fatal(
            _(
                "The raster maps {maps} already exist in the current mapset "
                "({count} of the {total} maps to import do). Use --overwrite "
                "to replace them, or the basename option to import under "
                "other names."
            ).format(
                maps=", ".join("<{}>".format(name) for name in clashes[:3]),
                count=len(clashes),
                total=len(map_names),
            )
        )

    # grass.temporal answers this exactly, where t.list output would have to
    # be told apart from the header it is printed under.
    tgis.init()
    dataset_id = strds if "@" in strds else "{}@{}".format(strds, gs.gisenv()["MAPSET"])
    exists = tgis.dataset_factory("strds", dataset_id).is_in_db()
    if append and not exists:
        gs.fatal(
            _(
                "The space time raster dataset <{}> does not exist, so there "
                "is nothing to append to. Leave out the a flag to create it."
            ).format(strds)
        )
    if exists and not append and not gs.overwrite():
        gs.fatal(
            _(
                "The space time raster dataset <{}> already exists. Use "
                "--overwrite to replace it, or the a flag to append to it."
            ).format(strds)
        )


def main():
    # The GDAL Python bindings are imported here rather than at the top of
    # the module. Importing them at the top would also be needed to print the
    # interface description, which is what builds the manual page, and that
    # should not depend on them.
    try:
        from osgeo import gdal
    except ImportError:
        gs.fatal(
            _(
                "Cannot import the GDAL Python bindings (osgeo.gdal), which "
                "this module needs to read the time axis of the input file."
            )
        )
    gdal.UseExceptions()

    input_file = options["input"]
    if not os.path.isfile(input_file):
        gs.fatal(_("The input file <{}> does not exist.").format(input_file))

    # One scratch directory for the decompressed input file and for the two
    # lists exchanged with r.in.gdal and t.register.
    CREATED["directory"] = gs.tempdir()

    # The GDAL NetCDF driver reads a plain file only, so a compressed input
    # file has to be written out before it can be opened.
    if input_file.endswith(".gz"):
        netcdf_file = os.path.join(
            CREATED["directory"], os.path.basename(input_file[: -len(".gz")])
        )
        gs.message(_("Decompressing <{}>...").format(input_file))
        with gzip.open(input_file, "rb") as compressed:
            with open(netcdf_file, "wb") as plain:
                shutil.copyfileobj(compressed, plain)
    else:
        netcdf_file = input_file

    variable, gdal_name = select_variable(
        gdal.Open(netcdf_file), options["variable"], input_file, netcdf_file
    )
    layers = gdal.Open(gdal_name)
    offsets, time_units = read_time_axis(layers, variable, input_file)
    intervals = monthly_intervals(offsets, time_units)

    # The variable's own description and unit travel with the maps, as
    # r.in.gdal does not carry them over from the NetCDF attributes.
    metadata = layers.GetMetadata()
    long_name = metadata.get("{}#long_name".format(variable), variable)
    data_units = metadata.get("{}#units".format(variable), "")

    basename = options["basename"] or variable
    strds = options["output"]
    map_names = [
        "{}_{:04d}_{:02d}".format(basename, start.year, start.month)
        for start, _end in intervals
    ]
    check_output_names(map_names, strds, flags["a"])

    gs.message(
        _("Importing {count} monthly layers of variable <{variable}>...").format(
            count=len(map_names), variable=variable
        )
    )
    # The flags that only concern the import itself are passed on as they are.
    import_flags = "".join(flag for flag in ("o", "r") if flags[flag])
    temporary_basename = gs.append_node_pid("t_rast_import_cru")
    CREATED["raster_pattern"] = "{}*".format(temporary_basename)
    # The names r.in.gdal gives the layers depend on the file and on its own
    # options, so they are read back instead of being guessed.
    names_file = os.path.join(CREATED["directory"], "imported.txt")
    gs.run_command(
        "r.in.gdal",
        input=gdal_name,
        output=temporary_basename,
        memory=options["memory"],
        map_names_file=names_file,
        flags=import_flags,
        quiet=True,
    )
    if os.path.exists(names_file):
        with open(names_file) as names:
            imported = [line.strip() for line in names if line.strip()]
    else:
        # r.in.gdal writes no list when there is only one layer to import: it
        # then imports it under the given name itself, without a suffix.
        imported = [temporary_basename]
    if len(imported) != len(map_names):
        gs.fatal(
            _(
                "The input file holds {expected} layers, but {imported} raster "
                "maps were imported."
            ).format(expected=len(map_names), imported=len(imported))
        )

    gs.verbose(_("Renaming the imported raster maps..."))
    renames = []
    for temporary_name, map_name in zip(imported, map_names):
        renames.extend([temporary_name, map_name])
    gs.run_command("g.rename", raster=renames, overwrite=gs.overwrite(), quiet=True)
    CREATED["raster_pattern"] = None
    CREATED["rasters"] = map_names

    gs.message(_("Writing the metadata of the imported raster maps..."))
    # r.support leaves the unit of a map alone when it is not given a new one,
    # which is what should happen when the NetCDF variable has none.
    unit = {"units": data_units} if data_units else {}
    for number, (map_name, (start, _end)) in enumerate(zip(map_names, intervals), 1):
        gs.run_command(
            "r.support",
            map=map_name,
            title="{} {}".format(long_name, start.strftime("%Y-%m")),
            quiet=True,
            **unit,
        )
        gs.percent(number, len(map_names), 1)

    if not flags["a"]:
        gs.run_command(
            "t.create",
            type="strds",
            output=strds,
            temporaltype="absolute",
            semantictype=options["semantictype"],
            title=options["title"] or long_name,
            description=options["description"]
            or _("CRU TS variable {variable}, imported from {file}").format(
                variable=variable, file=os.path.basename(input_file)
            ),
            overwrite=gs.overwrite(),
            quiet=True,
        )

    # One t.register call with a list of maps and their time intervals, which
    # for a series of over a thousand months is a great deal faster than
    # registering each map on its own.
    register_file = os.path.join(CREATED["directory"], "register.txt")
    with open(register_file, "w") as register:
        for map_name, (start, end) in zip(map_names, intervals):
            register.write(
                "{}|{}|{}\n".format(
                    map_name, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
                )
            )
    gs.run_command(
        "t.register",
        type="raster",
        input=strds,
        file=register_file,
        separator="pipe",
        quiet=True,
    )

    # The import is complete, so the maps are the user's from here on.
    CREATED["rasters"] = []
    gs.message(
        _("Registered {count} monthly maps, {first} to {last}, in <{strds}>.").format(
            count=len(map_names),
            first=intervals[0][0].strftime("%Y-%m"),
            last=intervals[-1][0].strftime("%Y-%m"),
            strds=strds,
        )
    )
    return 0


if __name__ == "__main__":
    options, flags = gs.parser()
    atexit.register(cleanup)
    sys.exit(main())

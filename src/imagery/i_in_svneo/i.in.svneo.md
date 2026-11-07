## DESCRIPTION

*i.in.svneo* imports SuperView-NEO multispectral imagery into GRASS GIS
and, when requested, performs radiometric and atmospheric preprocessing.
The module supports four-band SuperView-NEO products in the order blue,
green, red and near infrared (NIR).

The module can be used in two main ways. For bottom-of-atmosphere (BOA)
surface reflectance products, it imports the bands, optionally rescales
the values, and writes raster metadata such as semantic labels, units and
the acquisition timestamp. For digital number (DN) products, it can keep
the DN values, convert them to top-of-atmosphere (TOA) radiance, estimate
surface reflectance with dark object subtraction (DOS), or run
*i.atcorr* using 6S atmospheric correction.

Metadata are read from either the NSO ISO 19115 XML file or the raw
SuperView-NEO L1B MUX XML file. When both files are available, the NSO
XML is used for the product-level metadata and acquisition information,
while the L1B XML can provide scene geometry, solar irradiance, spectral
ranges, and radiometric calibration coefficients.

The output raster names are derived from **output** and the band name.
For example, **output**=`svneo` may create maps such as `svneo_blue`,
`svneo_red_rad`, `svneo_green_dos1`, or `svneo_nir_atcorr`, depending on
the selected processing level.

## NOTES

### Input data

The module accepts either an external GeoTIFF through **input** or a set
of already imported raster maps through **input_bands**. Exactly one of
these options should normally be used.

When **input** is used, the GeoTIFF is imported with *r.in.gdal*. The
input file must contain the four SuperView-NEO bands in the order blue,
green, red and NIR. The **-r** flag limits the import to the current
computational region; otherwise the full image extent is imported.

When **input_bands** is used, the import step is skipped. The existing
raster maps must be named `basename.1`, `basename.2`, `basename.3` and
`basename.4`, again in the order blue, green, red and NIR. These input
maps are not removed or renamed by the module.

The **metadata** option is required. It may point to the NSO ISO 19115 XML
file or to the raw L1B MUX XML file. The optional
**geometry_metadata** option can be used to provide the raw L1B MUX XML
when **metadata** points to the NSO XML. This is recommended for
atmospheric correction and required for DOS when the sun elevation angle
is not available from the primary metadata file.

### Processing levels

The **processing_level** option describes the input product. With the
default value **processing_level**=`auto`, the module attempts to detect
the product type from the metadata. Use **processing_level**=`boa` for
BOA surface reflectance products and **processing_level**=`dn` for raw or
geometry-corrected DN products.

The **target_level** option describes the desired output. The value
**target_level**=`as_is` keeps the input values and only imports or tags
the rasters. For BOA input this means BOA reflectance output. For DN
input this means DN output. The value **target_level**=`dn` keeps DN
values explicitly. The value **target_level**=`radiance` converts DN to
TOA radiance. The values **target_level**=`dos1` and
**target_level**=`dos2` produce approximate surface reflectance using DOS.
The value **target_level**=`atcorr` runs *i.atcorr* and produces
surface reflectance using 6S.

Only DN input can be converted to radiance, DOS reflectance or
*i.atcorr* reflectance. If the metadata identify the input as a BOA
product but the product is actually a DN product, set
**processing_level**=`dn` explicitly.

### BOA reflectance products

For BOA products, no radiance conversion is applied. The module assumes
that the image already represents surface reflectance. The option
**boa_scale** is a divisor used to convert stored pixel values to
unitless reflectance. Use **boa_scale**=`1.0` when the GeoTIFF already
stores reflectance as floating point values in the range 0 to 1. Use
**boa_scale**=`10000` when the BOA values are stored as integers scaled
by 10000.

The **-p** flag can be used when rescaling BOA data to write
single-precision floating point output instead of double precision.

### DN to radiance conversion

For DN products, TOA radiance is calculated per band as:

```text
L = DN * GAIN + BIAS
```

Here `L` is TOA radiance, `DN` is the digital number, and `GAIN` and
`BIAS` are the band-specific calibration coefficients read from the
metadata. This multiplicative gain convention is important for
SuperView-NEO products. It is not the same convention as used by some
other optical sensors.

The radiance output is written in units of `W m-2 sr-1 um-1`. DN values
equal to the nodata value, normally 0, are converted to NULL.

### Dark object subtraction

The values **target_level**=`dos1` and **target_level**=`dos2` estimate
surface reflectance from TOA radiance using dark object subtraction. DOS
is an image-based correction method. It does not require external
atmospheric data, but it is approximate and should be used with this
limitation in mind.

The **dark_method** option controls how the dark object DN is estimated.
With **dark_method**=`histogram`, the module selects the lowest DN value
that occurs in at least **dark_parameter** pixels. This follows the
convention used by *i.landsat.toar*. With
**dark_method**=`quantile`, the module uses the DN value at
**dark_percentile**. With **dark_method**=`ols_intercept`, the module fits
a regression through the darkest **dark_parameter** pixels and uses the
intercept as the dark object estimate.

By default, dark object estimation is restricted to pixels that are dark
in the NIR band. The NIR threshold is set by **dark_percentile**. This
multi-band dark mask is intended to reduce the chance that bright or
mixed pixels influence the dark object estimate. Use the **-d** flag to
disable this mask.

The **cloud_mask** option can be used to exclude clouds and cloud shadows
from dark object estimation. Non-NULL cells in **cloud_mask** are treated
as pixels to exclude. The mask affects only the dark object estimation,
not the final reflectance calculation.

When **tile_size** is greater than 0, the dark object DN is estimated per
tile and interpolated across the scene. This can account for spatially
variable haze, but it can also introduce artefacts when tiles contain too
few valid dark pixels. The default **tile_size**=`0` uses one whole-scene
dark object estimate per band.

The DOS2 option applies a simple transmittance approximation for bands
below 1000 nm. It is best treated as an experimental option for
SuperView-NEO rather than as a fully validated atmospheric correction.

### Atmospheric correction with i.atcorr

With **target_level**=`atcorr`, the module first converts DN to TOA
radiance, then creates one *i.atcorr* parameter file per band and runs
*i.atcorr*. The **rescale** option controls the output range passed to
*i.atcorr*. The default **rescale**=`0,1` writes reflectance in the range
0 to 1.

The **aod_source** option specifies the aerosol input for 6S. With
**aod_source**=`manual`, **visibility_or_aod** can contain either a
visibility value in kilometres or an AOD value written as
`aod:value`, for example `aod:0.12`. With **aod_source**=`visibility`,
**visibility_or_aod** is interpreted as visibility in kilometres. With
**aod_source**=`aeronet_file`, AOD at 550 nm is derived from a local
AERONET all-points file. With **aod_source**=`cams`, AOD at 550 nm is
derived from a local CAMS NetCDF or GRIB file.

The **atmospheric_model** option sets the 6S atmospheric model. With the
default value **atmospheric_model**=`auto`, the model is selected from the
scene latitude and acquisition date. Use an explicit numerical model code
when the automatic choice is not appropriate for the study area or season.

The **aerosol_model** option sets the 6S aerosol model. The default is
continental aerosol. This is a reasonable default for many land scenes,
but it may be unsuitable for coastal, urban, desert or biomass-burning
conditions.

The **elevation** option gives a single mean target elevation in metres.
When **elevation_map** is provided, the raster is passed to *i.atcorr*
for spatially variable elevation instead. Elevation should refer to the
target surface, not to the sensor altitude.

The **-a** flag creates the *i.atcorr* parameter files but does not run
*i.atcorr*. In this mode **icnd_basename** is required. This is useful for
checking or editing the 6S input files before running atmospheric
correction.

### Intermediate maps and summaries

By default, imported DN maps and temporary radiance maps are removed after
processing when they are no longer needed. Use the **-k** flag to keep
these intermediate maps. Keeping intermediate maps is useful for
diagnostics and teaching, but it increases disk use.

The **summary_file** option writes the processing summary to a text file.
The same information is also printed to the GRASS message stream.

The module refuses to run when a GRASS `MASK` is active. This avoids
unintended masking during radiometric processing. Use **cloud_mask** to
exclude clouds or shadows from dark object estimation.

### Metadata written to output maps

Output rasters receive a title, units, semantic label and, when available,
an acquisition timestamp. The semantic labels are generic optical labels:
`gen_b`, `gen_g`, `gen_r` and `gen_nir`.

Scene-specific ESUN values and spectral ranges are read from the raw L1B
XML when available. If they are not available, the module uses fallback
values for SuperView-NEO. These fallback values allow processing to
continue, but scene metadata should be preferred when possible.

## EXAMPLES

Import a BOA product and tag the output rasters:

```sh
i.in.svneo input=scene_boa.tif metadata=metadata.xml output=svneo \
  processing_level=boa
```

Import a BOA product stored as integer reflectance scaled by 10000:

```sh
i.in.svneo input=scene_boa.tif metadata=metadata.xml output=svneo \
  processing_level=boa boa_scale=10000
```

Import a DN product and keep DN values:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml output=svneo \
  processing_level=dn target_level=dn
```

Convert a DN product to TOA radiance:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml output=svneo \
  processing_level=dn target_level=radiance
```

Run DOS1 correction using the raw L1B XML for sun geometry:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml \
  geometry_metadata=l1b_mux.xml output=svneo processing_level=dn \
  target_level=dos1
```

Run DOS1 correction with a low-percentile dark object estimate and a
cloud mask:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml \
  geometry_metadata=l1b_mux.xml output=svneo processing_level=dn \
  target_level=dos1 dark_method=quantile dark_percentile=0.5 \
  cloud_mask=cloud_shadow_mask
```

Run spatially variable DOS using 1000 by 1000 pixel tiles:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml \
  geometry_metadata=l1b_mux.xml output=svneo processing_level=dn \
  target_level=dos1 tile_size=1000
```

Create *i.atcorr* parameter files only:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml \
  geometry_metadata=l1b_mux.xml output=svneo processing_level=dn \
  target_level=atcorr aod_source=manual visibility_or_aod=aod:0.12 \
  icnd_basename=svneo_icnd -a
```

Run *i.atcorr* using manual AOD at 550 nm:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml \
  geometry_metadata=l1b_mux.xml output=svneo processing_level=dn \
  target_level=atcorr aod_source=manual visibility_or_aod=aod:0.12 \
  elevation=15
```

Run *i.atcorr* using an AERONET file:

```sh
i.in.svneo input=scene_dn.tif metadata=metadata.xml \
  geometry_metadata=l1b_mux.xml output=svneo processing_level=dn \
  target_level=atcorr aod_source=aeronet_file \
  aeronet_file=aeronet_all_points.txt aeronet_time_window=120
```

Use already imported bands named `raw_svneo.1` to `raw_svneo.4`:

```sh
i.in.svneo input_bands=raw_svneo metadata=metadata.xml \
  geometry_metadata=l1b_mux.xml output=svneo processing_level=dn \
  target_level=radiance
```

## REFERENCES

Chavez, P. S. Jr., 1988. An improved dark-object subtraction technique
for atmospheric scattering correction of multispectral data. *Remote
Sensing of Environment*, 24, 459-479.

Moran, M. S., Jackson, R. D., Slater, P. N. and Teillet, P. M., 1992.
Evaluation of simplified procedures for retrieval of land surface
reflectance factors from satellite sensor output. *Remote Sensing of
Environment*, 41, 169-184.

Vermote, E. F., Tanré, D., Deuzé, J. L., Herman, M. and Morcrette, J. J.,
1997. Second simulation of the satellite signal in the solar spectrum,
6S: an overview. *IEEE Transactions on Geoscience and Remote Sensing*,
35, 675-686.

## SEE ALSO

*[i.atcorr](i.atcorr.md), [i.landsat.toar](i.landsat.toar.md),
[r.in.gdal](r.in.gdal.md), [r.mapcalc](r.mapcalc.md),
[r.mask](r.mask.md), [r.support](r.support.md)*

## AUTHORS

[Paulo van Breugel](https://ecodiv.earth)

<a href="https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/"><img src="../logos/logo_IBM.png" height=100/></a> <a href="https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/"><img src="../logos/logo_KRL.png" height=100/></a> <a href="https://www.combined-project.eu/"><img src="../logos/logo_combined.png" height=80/></a> <a href="https://savethetiger.nl/"><img src="../logos/logo_STGW.png" height=80/></a>

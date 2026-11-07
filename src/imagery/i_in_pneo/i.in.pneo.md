## DESCRIPTION

**i.in.pneo** preprocesses Pléiades-NEO multispectral imagery (6 bands: red,
green, blue, NIR, red-edge, deep-blue). It supports the workflow from raw
digital numbers (DN) to top-of-atmosphere (TOA) radiance and, optionally, to
surface reflectance using either physically based or image-based atmospheric
correction.

### Input

The module accepts either:

- **input=**: path to a 6-band Pléiades-NEO GeoTIFF
- **input_bands=**: basename of six already imported rasters in the
  current mapset

Exactly one of these must be provided. When **input_bands=** is used, the module
expects rasters named `<input_bands>.1` through `<input_bands>.6` in the
following order: red, green, blue, NIR, red-edge, deep-blue.

Pre-imported bands are never renamed or deleted, which allows repeated
processing with different correction settings without re-importing the source
data.

When **input=** is used, the GeoTIFF is imported and the full scene is imported.
With the **-r** flag, only the portion overlapping the current computational
region is imported. After import, the computational region is adjusted to the
processed scene extent.

### Processing levels

The processing path is determined automatically by **aod_source** and the **-a**
flag.

1. **Full atmospheric correction with *i.atcorr***: When **aod_source** is set
   to **manual**, **visibility**, **aeronet_file**, or **cams**, the module
   converts DN to radiance, writes *i.atcorr* control files, and runs *i.atcorr*
   for 6S-based atmospheric correction.

2. **Parameter files only for manual *i.atcorr***: With atmospheric input as
   above and the **-a** flag, the module converts DN to radiance and writes
   *i.atcorr* control files, but does not run *i.atcorr*. Output consists of
   radiance maps and parameter files only. In this mode, **icnd_basename** is
   required.

3. **Image-based atmospheric correction (DOS1 or DOS2)**: When
   **aod_source=dos1** or **aod_source=dos2**, the module converts DN to
   radiance and applies dark-object subtraction to derive approximate surface
   reflectance.

The full *i.atcorr* workflow is the most physically complete option, but its
quality depends on the representativeness of the input atmospheric parameters.
The DOS methods require no external atmospheric data and can be more robust
where aerosol conditions are uncertain or spatially heterogeneous.

### DN to radiance conversion

Radiance is computed as follows:

```text
L = DN / GAIN + BIAS
```

where **GAIN** and **BIAS** are read from the DIMAP metadata.

## DARK OBJECT SUBTRACTION

For DOS processing, atmospheric path radiance is estimated from dark pixels and
removed to produce approximate surface reflectance. A minimum reflectance of 1%
is assumed for the dark object.

### Multi-band dark mask

By default, dark-object estimation uses only pixels that are spectrally dark
across bands. These are identified from the NIR band as pixels below the
**dark_percentile** percentile (default = 1.0, valid range = 0.01 -50). This
approach is inspired by the Dark Spectrum Fitting (DSF) approach of Vanhellemont
& Ruddick (2018), adapted here to a DOS workflow.

If both a dark mask and a **cloud_mask** are provided, they are combined:
only pixels that are both dark and not masked as cloud or cloud shadow
are used for dark-object estimation.

To determine dark pixels for each band independently, use the **-d** flag.

### Dark-object estimation methods

Dark-object estimation is performed in DN space. The DN–radiance relationship is
linear, so the dark-object estimate translates directly to radiance without loss
of physical meaning.

Three methods are available via the **dark_method** parameter:

- **histogram** (default): the lowest DN value that occurs in at least
  **dark_parameter** pixels. This avoids single-pixel noise and outliers.
- **quantile**: the DN at the **dark_percentile** percentile of the
  distribution. 
- **ols_intercept**: ordinary least-squares regression through the
  **dark_parameter** darkest pixels, returning the intercept at rank 0. Inspired
  by the Dark Spectrum Fitting method of Vanhellemont & Ruddick (2018), this
  method fits DN as a function of rank among the darkest pixels and extrapolates
  to rank 0 to estimate the atmospheric dark floor. But unlike full DSF, this is
  a one-dimensional, per-band simplification that operates only on the DN
  distribution within a single band. The method is less sensitive to
  noise, outliers, and mixed pixels than minimum- or histogram-based methods.

### Tiled processing for spatially variable correction

When **tile_size** is greater than 0, the scene is divided into square tiles and
the dark-object DN is estimated independently per tile. This produces a
spatially varying path-radiance surface and can capture within-scene atmospheric
variability, such as haze gradients across urban areas or coastal–inland
transitions.

Per-tile estimates are interpolated to a smooth full-resolution raster in three
stages:

1. **Coarse-grid interpolation**: inverse distance weighting is applied to
   tile-centre values on a reduced-resolution grid.
2. **Smoothing**: moving-window averaging with a circular kernel removes
   residual interpolation artefacts.
3. **Upscaling**: the smoothed coarse grid is resampled to full resolution using
   bilinear interpolation.

Tiles where the active dark mask leaves fewer than 0.1% of pixels as
valid are skipped and later filled during interpolation using the median
of valid tiles.

This tiled approach is inspired by the spatially varying processing
strategy used in ACOLITE and described by Vanhellemont (2019).

### DOS1 and DOS2

Both DOS methods follow the simplified framework of Moran et al. (1992):

```text
sun_radiance = TAUv * [ESUN * sin(e) * TAUz + Esky] / (π * d²)
L_p          = L_dark - 0.01 * sun_radiance
ρ            = (L - L_p) / sun_radiance
```

where:

- **TAUv** is the atmospheric transmittance from target to sensor
- **TAUz** is the atmospheric transmittance from sun to target
- **Esky** is diffuse sky irradiance
- **e** is sun elevation
- **d** is Earth–Sun distance in astronomical units

The two methods differ only in the value for TAUz. For DOS1, this is 1.0. For
DOS2, this is sin(e) for bands with max wavelength < 1 µm; 1.0 otherwise. Note
that since all Pléiades-NEO bands have maximum wavelengths below 1 µm, DOS2
applies **TAUz = sin(e)** to all bands.

DOS2 extends DOS1 with an approximate sun-path transmittance term and may reduce
low-sun-angle bias, but it remains a heuristic approximation that has not been
independently validated for Pléiades-NEO. It is therefore provided as an
experimental option.

## ATMOSPHERIC CORRECTION WITH I.ATCORR

### Aerosol sources

The **aod_source** parameter determines how aerosol optical depth (AOD) or
visibility is specified:

- **manual**: use the value in **visibility_or_aod** directly, either as
  visibility in km or as AOD with the prefix `aod:`
- **aeronet_file**: derive AOD550 from a local AERONET all-points file
- **cams**: derive AOD550 from a CAMS NetCDF or GRIB file, averaged over the
  processed scene footprint
- **visibility**: use **visibility_or_aod** as visibility in km
- **dos1**: skip *i.atcorr* and use DOS1
- **dos2**: skip *i.atcorr* and use DOS2

#### AERONET

AERONET (AErosol RObotic NETwork) provides ground-based aerosol measurements
([more information](https://www.knmiprojects.nl/projects/globe/aerosolen/calitoo/aeronet-data)).
The module reads local AERONET all-points CSV/TXT files
[download here](https://aeronet.gsfc.nasa.gov/new_web/aerosols.html), selects
the observation closest in time to scene acquisition within the configured
**aeronet_time_window**, and derives AOD at 550 nm. If no direct 550 nm value is
available, AOD550 is interpolated using the Ångström relation.

#### CAMS

CAMS (Copernicus Atmosphere Monitoring Service) provides gridded global
atmospheric data
([See here](https://ads.atmosphere.copernicus.eu/datasets/cams-global-reanalysis-eac4?tab=download)).
The module reads a pre-downloaded CAMS NetCDF or GRIB file, finds the time step
closest to scene acquisition within **cams_time_window**, and computes the mean
AOD550 over the actual processed scene footprint. This requires the Python
package *xarray* (and *cfgrib* for GRIB files).

### Atmospheric model

The 6S atmospheric model can be specified manually or set to **auto**. When
**auto** is used, the model is derived from scene-centre latitude and
acquisition month. 

Available models are: 0: no gaseous absorption, 1: tropical, 2: midlatitude
summer, 3: midlatitude winter, 4: subarctic summer, 5: subarctic winter, 6: US
Standard 1962. 

For auto-selection, the warm season is April–September in the Northern
Hemisphere and October–March in the Southern Hemisphere. For more information,
see the [i.attcor](https://grass.osgeo.org/grass-stable/manuals/i.atcorr.html)
manual page.

### Geometry, elevation, and output scaling

The *i.atcorr* control files use viewing and solar geometry from DIMAP metadata
when available; otherwise they fall back to time and scene centre coordinates.

If an **elevation_map** is provided, it is passed to *i.atcorr* to account for
spatially varying terrain elevation. Otherwise the scalar **elevation** value is
used. The scalar elevation is also written to the parameter file.

The *i.atcorr* **range** parameter is derived internally from the sensor’s
theoretical DN limits and the radiometric calibration coefficients. The output
reflectance scaling is controlled by **rescale** (default = 0,1).

## NOTES

### Choosing a correction method

The most appropriate atmospheric correction method depends on the application
and the availability of representative atmospheric information.

**DOS1** is the simplest image-based method. It requires no external atmospheric
data and is often suitable for single-scene vegetation index calculation and
other relative within-scene analyses. It corrects only for additive path
radiance and does not model atmospheric transmittance, gas absorption, or
adjacency effects.

**DOS2** extends DOS1 by including an approximate sun-path transmittance term.
It may improve results at low sun elevations, but differences from DOS1 are
generally small under high sun conditions.

Unlike i.atcorr (6S), the DOS methods do not rely on external atmospheric
measurements. This makes them useful when aerosol conditions are uncertain or
spatially heterogeneous, such as in urban or coastal environments where a single
AOD value (e.g., from AERONET or CAMS) may not represent the full scene.

**i.atcorr (6S)** provides a physically based atmospheric correction and can
yield more accurate surface reflectance when reliable atmospheric inputs are
available. However, its performance depends on the accuracy and
representativeness of aerosol and atmospheric parameters, as well as the
approximation of the sensor’s spectral response. In practice, results may vary
depending on input quality, and comparison with simpler methods (e.g., DOS) can
be useful.

### Cloud mask and existing MASK

The **cloud_mask** parameter excludes clouds and cloud shadows from dark-object
estimation. It does not remove those pixels from the final DOS reflectance
calculation; it only affects the estimation of the dark-object level. A cloud
mask can be created with the `i.omnicloudmask` plugin.

Any existing GRASS **MASK** must be removed before running the module. The
module checks for an active MASK and aborts if one is found.

### Spectral metadata fallback

Band-specific **GAIN**, **BIAS**, **ESUN**, and spectral ranges are read from
DIMAP metadata whenever available. If **ESUN** or spectral ranges are missing,
internal fallback values are used and a warning is reported in the processing
summary.

### Intermediate maps and precision

By default, imported DN bands and intermediate radiance maps are removed after
processing to save disk space. Use the **-k** flag to keep them. When tiled DOS
processing is used, the interpolated DNmin rasters are also retained with
**-k**.

The **-p** flag uses single-precision floating point output for radiance and DOS
maps, reducing disk usage at the cost of minor precision loss.

### Summary output and performance

If **summary_file** is provided, the module writes a processing summary to a
text file. The **memory** parameter controls GDAL cache during import and memory
allocation for raster processing. The **nprocs** parameter controls parallel
computation where supported.

## EXAMPLES

The following examples illustrate common processing workflows.

### Full atmospheric correction with manual AOD

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=manual \
  visibility_or_aod=aod:0.20 \
  aerosol_model=3 \
  elevation_map=dem \
  rescale=0,1
```

### Basic DOS1 correction

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1
```

### DOS1 with OLS dark-object estimation and tiled processing

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1 \
  dark_method=ols_intercept \
  dark_parameter=1000 \
  tile_size=2000
```

### DOS1 with quantile dark-object estimation

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1 \
  dark_method=quantile \
  dark_percentile=1.5
```

### DOS1 with cloud and shadow exclusion

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1 \
  cloud_mask=cloud_shadow_map
```

### DOS1 with disabled dark mask

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1 \
  dark_method=histogram -d
```

### Import using pre-imported DN bands

```sh
i.in.pneo input_bands=myimage \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1
```

### Limit import to the current computational region

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1 -r
```

### DOS2 correction

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos2
```

### Full atmospheric correction with AERONET

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=aeronet_file \
  aeronet_file=20030101_20261231_Cabauw.lev20 \
  aerosol_model=1
```

### Full atmospheric correction with CAMS

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=cams \
  cams_file=cams_aod_20240502.nc \
  aerosol_model=1
```

### Generate *i.atcorr* parameter files only

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  icnd_basename=/tmp/pneo_icnd \
  aod_source=manual \
  visibility_or_aod=aod:0.20 \
  aerosol_model=1 -a
```

### Keep intermediate radiance maps

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1 -k
```

### Write a processing summary to file

```sh
i.in.pneo input=20240502_PNEO03_RGBNED.tif \
  dimap=DIM_PNEO3_202405021108320.XML \
  output=P20240502 \
  aod_source=dos1 \
  summary_file=/tmp/i_in_pneo_summary.txt
```

## REFERENCES

- Chavez, P.S. Jr., 1988. An improved dark-object subtraction
  technique for atmospheric scattering correction of multispectral
  data. *Remote Sensing of Environment*, 24(3), 459–479.

- Moran, M.S., Jackson, R.D., Slater, P.N. and Teillet, P.M., 1992.
  Evaluation of simplified procedures for retrieval of land surface
  reflectance factors from satellite sensor output. *Remote Sensing of
  Environment*, 41(2–3), 169–184.

- Vanhellemont, Q. and Ruddick, K., 2018. Atmospheric correction of
  metre-scale optical satellite data for inland and coastal water
  applications. *Remote Sensing of Environment*, 216, 586–597.

- Vanhellemont, Q., 2019. Adaptation of the dark spectrum fitting
  atmospheric correction for aquatic applications of the Landsat and
  Sentinel-2 archives. *Remote Sensing of Environment*, 225, 175–192.

- Vermote, E.F., Tanré, D., Deuzé, J.L., Herman, M. and
  Morcrette, J.J., 1997. Second Simulation of the Satellite Signal in
  the Solar Spectrum, 6S: An overview. *IEEE Transactions on
  Geoscience and Remote Sensing*, 35(3), 675–686.

- Airbus Defence & Space, 2022. *Pléiades Neo Imagery User Guide*, v2.0.

## SEE ALSO

*[i.atcorr](i.atcorr.md),
[r.in.gdal](r.in.gdal.md),
[i.landsat.toar](https://grass.osgeo.org/grass-stable/manuals/addons/i.landsat.toar.html),
[i.sentinel.preproc](https://grass.osgeo.org/grass-stable/manuals/addons/i.sentinel.preproc.html)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green
academy](https://has.nl), [Innovative Biomonitoring research
group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research
group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)

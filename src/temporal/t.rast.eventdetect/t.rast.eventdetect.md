## DESCRIPTION

*t.rast.eventdetect* detects relatively rapid changes (events) in a space-time
raster dataset (STRDS), counts them, and describes the recovery after each
event. Detection is performed independently for every pixel and uses the
actual acquisition dates, so observations do not need to be evenly spaced.

The method generalizes the grassland mowing-frequency approach of Kolecka et
al. (2018). In addition to mowing, it can be used for other abrupt disturbances
and subsequent recovery, such as harvesting, flood or hail damage, fire, and
drought-related dieback.

Before running the module, clouds, shadows, and any other unsuitable
pixels should be set to NULL. The module treats every non-NULL pixel as a valid observation;
it does not identify clouds or assess pixel quality itself. Raw or composited
observations are generally more suitable than smoothed or harmonically fitted
time series, such as a HANTS climatology. Smoothing can suppress the short,
sharp changes that the module is designed to detect. The module handles gaps
in the input series directly.

### EVENT DETECTION

#### Observation history and gaps

At each acquisition date (*AD*), the module compares the current value with
the most recent valid (non-NULL) observation (*AD-1*). With `lookback=2`, it
also compares the value with the second most recent valid observation
(*AD-2*). An event is detected when a change in the selected `direction`
exceeds the specified `threshold`.

The additional *AD-2* comparison can detect an event when the most recent
valid observation is noisy or already partly affected by the change. NULL
observations are skipped: they do not become *AD-1* or *AD-2* and are not
included in the pre-event baseline.

The `max_gap` option limits comparisons across time. A change is ignored when
the observations being compared are more than `max_gap` days apart. This
reduces false detections across long gaps, such as periods masked because of
cloud cover, where a difference is more likely to reflect seasonal development
than an abrupt event. The same limit is used when constructing the pre-event
baseline described below.

### Detection thresholds

The interpretation of `threshold` is controlled by `threshold_type`:

- `absolute` — the threshold is expressed in the units of the input data. The
  default is `0.2`.
- `relative` — the threshold is a fraction of the absolute value of the
  previous observation used in the comparison.
- `mad` — the threshold is a multiple of the per-pixel robust standard
  deviation, calculated as 1.4826 × the median absolute deviation (MAD) over
  the analyzed period.

When `direction=both`, `threshold_drop` and `threshold_rise` can be used to set
different thresholds for the two directions. If either option is omitted,
`threshold` is used for that direction.

#### Event magnitude

The change from *AD-1* or *AD-2* triggers an event, but the reported event
magnitude is measured from a separate pre-event reference level, *R*. This
prevents a single unusually low or high observation immediately before an
event from distorting its estimated magnitude.

The module derives *R* from the last `baseline_window` valid observations
before the event. It uses the highest value for a drop (`direction=drop`) and
the lowest value for a rise (`direction=rise`). With `baseline_window=1`, *R*
is simply the value immediately before the event, reproducing the method of
Kolecka et al. (2018).

For example, consider three valid observations followed by a cut:

```text
time →   0.80    0.78    0.72   |  0.50
         AD-3    AD-2    AD-1   |  event date
```

Suppose the value at *AD-1* is slightly depressed by haze. With
`baseline_window=1`, *R* = 0.72 and the event magnitude is 0.72 − 0.50 = 0.22.
With `baseline_window=3`, *R* = max(0.80, 0.78, 0.72) = 0.80 and the magnitude
is 0.80 − 0.50 = 0.30. The larger window therefore provides a more
representative pre-event level in this example.

For a drop, `magnitude = R - value_at_event`. For a rise, the magnitude is the
corresponding upward distance. Magnitudes are always reported in the units of
the input data, regardless of `threshold_type`. With `baseline=observed`, the
same *R* is also used as the recovery reference, ensuring that event magnitude
and recovery are measured from a consistent baseline.

The baseline window contains only a contiguous sequence of valid observations
from the current signal level. Starting at *AD-1*, it stops at either the first
gap longer than `max_gap` or the previous detected event. Consequently, a
second event is measured from the level reached after the first event rather
than from the earlier, pre-event level. *AD-1* is always included.

#### Preventing duplicate detections

With `lookback=2`, a single change can be detected twice: once on the event
date and again at the next observation, while the *AD-2* comparison still spans
the same change. Kolecka et al. (2018) removed these overlapping detections by
prioritizing the single-interval detection.

This module applies an equivalent day-based rule through `min_separation`.
Detections less than `min_separation` days apart are treated as one event, and
the earlier detection is retained. Expressing the rule in days makes it
independent of observation frequency and allows it to represent the shortest
plausible interval between genuine events.

Choose a value shorter than the shortest realistic interval between separate
events. For grassland mowing, regrowth generally takes weeks, so the default of
2 × `step` removes the duplicate detection without normally merging successive
cuts.

### RECOVERY

After detecting an event, the module tracks how far the signal returns toward
a reference level. An event is classified as recovered when the recovered
fraction reaches `recovery_target` (default `0.8`).

The recovery reference is selected with `baseline`:

- `observed` — recovery is measured toward the pre-event level *R* described
  above. The recovered fraction is `(value - extreme) / (R - extreme)`, where
  *extreme* is the most extreme value observed since the event: the lowest
  value for a drop or the highest value for a rise.
- `reference` — recovery is measured toward the expected value for that time
  of year. Expected values come from the climatology STRDS specified by
  `reference`, which is a relative-time STRDS indexed by day of year. Recovery
  is measured by how far the observed-minus-expected anomaly closes. The
  reference STRDS is used only for recovery, never for event detection.

Each event has exactly one of three outcomes. The number of interrupted events
can therefore be calculated as
`count - n_recovered - n_incomplete`:

- **Recovered** — the signal reached `recovery_target` before another event or
  the end of the input series.
- **Interrupted** — another event occurred before recovery was complete. The
  maximum recovered fraction reached before interruption contributes to
  `mean_percent_restored`. This outcome indicates whether the signal recovered
  before the next event.
- **Incomplete** — the event was still open at the end of the input series
  because no later observations were available. These events contribute to
  `n_incomplete` but not to `mean_percent_restored`, preventing events near the
  end of the series from biasing that statistic downward.

### OUTPUTS

The module writes summary rasters using the prefix given by `output`. Each
raster contains one value per pixel. In `vector` mode, each raster instead has
one value per parcel, repeated for all pixels in that parcel. Outputs are
limited to locations with at least one valid observation and honor the current
raster `MASK`.

- `<output>_count` — number of detected events.
- `<output>_first_doy` and `<output>_last_doy` — day of year of the first and
  last event.
- `<output>_mean_magnitude` and `<output>_max_magnitude` — mean and maximum
  event magnitude.
- `<output>_n_recovered` and `<output>_frac_recovered` — number and fraction of
  events that recovered.
- `<output>_mean_recovery_days` — mean time to recovery, calculated over
  recovered events.
- `<output>_mean_percent_restored` — mean maximum recovered fraction (0–100%),
  calculated over interrupted events.
- `<output>_n_incomplete` — number of events still open at the end of the input
  series.
- `<output>_n_drops` and `<output>_n_rises` — number of events in each
  direction; created only with `direction=both`.

Count outputs are zero where observations are available but no qualifying
events occur. Statistics that cannot be calculated, such as mean magnitude
where no event occurs, are NULL.

### PARCEL-LEVEL

By default, *t.rast.eventdetect* detects events independently for each pixel.
In landscapes divided into management units, such as agricultural parcels,
mown meadows, or forest stands, parcel-level analysis may be more accurate.
Mixed and boundary pixels are often an important source of noise; Kolecka et
al. (2018), for example, found parcel and shrunken-parcel units more accurate
than individual pixels.

The module supports two parcel-level workflows. They answer different
questions.

#### Detecting events from parcel medians (`vector`)

Provide a parcel vector map with `vector` to reduce every observation to a
per-parcel median before detection. Detection then runs once per parcel, and
the output rasters contain a constant value throughout each parcel.

This workflow is well suited to parcels managed as single units. Detection
uses a nonlinear threshold, so detecting changes in a denoised parcel-median
time series is not equivalent to aggregating event decisions made for many
noisy pixels. A parcel median can also preserve an observation date when only
part of the parcel contains valid pixels, for example after cloud masking,
reducing the number of temporal gaps.

```sh
g.region raster=grassland_mask -p

t.rast.eventdetect input=S2_ndvi year=2021 output=mow vector=parcels \
  direction=drop threshold=0.2 lookback=2 recovery_target=0.8
```

The median is robust to a small number of off-parcel pixels or pixels affected
by residual cloud. The `min_clear` option specifies the minimum fraction of a
parcel that must have valid pixels on a date. With the default `min_clear=0`,
one valid pixel is sufficient; `min_clear=0.5` requires at least half of the
parcel's pixels to be valid.

Boundary handling is left to preprocessing. To analyze shrunken parcels that
exclude boundary pixels, first buffer the parcel map inward with *v.buffer*
using the `-s` flag and a negative distance, then pass the buffered map to
`vector`. This allows the boundary rule, aggregation method, and valid-pixel
fraction to be controlled explicitly.

#### Summarizing pixel results by parcel (`v.rast.stats`)

Alternatively, run the module on individual pixels and summarize each output
raster in the parcel attribute table with *v.rast.stats*. This workflow retains
within-parcel variation because it does not reduce each parcel to a single
input time series.

Use `method=average` for continuous outputs such as `mean_magnitude`,
`max_magnitude`, `frac_recovered`, `mean_recovery_days`, and
`mean_percent_restored`. For integer count outputs such as `count`,
`n_recovered`, and `n_incomplete`, use `method=median` as a representative
value. *v.rast.stats* does not provide a mode; to calculate a true majority
value, rasterize the parcels and use a raster mode tool.

```sh
t.rast.eventdetect input=S2_ndvi year=2021 output=mow \
  direction=drop threshold=0.2 lookback=2 recovery_target=0.8

v.rast.stats map=parcels raster=mow_mean_magnitude \
  column_prefix=mag method=average
v.rast.stats map=parcels raster=mow_count \
  column_prefix=n_events method=median
```

The same commands can be used after running with `vector`. Because the output
is constant within each parcel in that case, any summary statistic, including
`method=average`, returns the parcel value.

To use an aggregation statistic other than the median, or to retain the
parcel-level time series, aggregate each input map before running the module.
For example, use
`r.stats.quantile base=parcels cover=<index_map> percentiles=50 output=<parcel_median>`
to calculate parcel medians, register the resulting maps in a new STRDS, and
run *t.rast.eventdetect* on that STRDS without `vector`.

### Choosing a parcel workflow

Use `vector` when parcels are managed as single units and the goal is robust
event detection at parcel level. It is also computationally cheaper because
detection runs once per parcel. Use *v.rast.stats* on pixel-level results when
within-parcel variation is important. In either workflow, select the
aggregation statistic and valid-pixel fraction that best match the application.

## NOTES

The module uses the current computational region and honors the current raster
`MASK`. Set the region to the input maps before running the analysis.

The implementation processes the time series one observation at a time and
performs spatial calculations with vectorized arrays. Processing time depends on both the number of maps and
the number of cells in the computational region. Memory normally holds only a
small number of full-region arrays. With `threshold_type=mad`, the complete
input stack for the analyzed period is also loaded into memory.

The `year` option limits the input series to a calendar year. The
`season_start` and `season_end` options limit event detection to an inclusive
day-of-year range, but observations outside that range can still contribute to
the observation history or to recovery tracking.

## EXAMPLE

The following example detects grassland mowing events in an NDVI STRDS for
2021. It uses the rule set of Kolecka et al. (2018): an absolute drop greater
than 0.2 compared with either of the two most recent valid observations. It
also characterizes regrowth after each detected event.

```sh
g.region raster=grassland_mask -p

t.rast.eventdetect input=S2_ndvi year=2021 output=mow \
  direction=drop threshold=0.2 threshold_type=absolute \
  lookback=2 min_separation=10 recovery_target=0.8

r.colors map=mow_count color=viridis
```

## REFERENCES

Kolecka, N., Ginzler, C., Pazur, R., Price, B., Verburg, P.H. (2018).
*Regional Scale Mapping of Grassland Mowing Frequency with Sentinel-2 Time
Series.* Remote Sensing 10(8), 1221. doi:10.3390/rs10081221

## SEE ALSO

*[t.rast.algebra](t.rast.algebra.md)*,
*[t.rast.accdetect](t.rast.accdetect.md)*,
*[t.rast.aggregate](t.rast.aggregate.md)*,
*[t.rast.mapcalc](t.rast.mapcalc.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth),
[Innovative Biomonitoring](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/)
and
[Climate-robust Landscapes](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)
research groups at the [HAS green academy](https://has.nl)

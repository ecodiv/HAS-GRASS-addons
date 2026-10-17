## DESCRIPTION

> This is work in progress. Consider this an alpha version.

*t.rast.event* detects and counts relatively rapid changes ("events") in a
space-time raster dataset (strds). It furthermore records the recovery time
after each event. An event is one continuous descent (a drop) or ascent (a
rise). For a drop, the event is measured by its peak-to-trough amplitude. For a
rise, the opposite is measured. This generalizes the grassland mowing-frequency
method of Kolecka et al. (2018) to any abrupt disturbance and recovery (harvest,
flood or hail defoliation, fire and drought die-back) and, with
`direction=rise`, to rapid increases such as green-up.

Clouds and shadows are expected to be masked to NULL beforehand. Note that the
module does not interpolate across gaps. It connects successive observations,
with the important condition that it will not connect observations further than
*max_gap* apart. Pre-filling the gaps (even linearly) is not needed and, in
fact, not recommended. It is also not recommended to use smoothed or
harmonically fitted series (e.g. a HANTS climatology). Such curves suppress the
short, sharp changes that this module is meant to find.

By default the analysis is done per yearly cycle (`groupby=year`). Give `year` to
restrict it to a single cycle, or leave `year` unset to analyze every cycle
present in the input, each on its own. Note that a partial cycle is analyzed as
given, so it is up to the user to provide complete cycles.

The cycle need not be the calendar year. `year_start` sets the month-day on which
each cycle begins (default `01-01`). Use it for a monsoon or hydrological year,
for example `year_start=06-01`, so that a drop and its recovery straddling
1 January stay in one cycle instead of being split across two. A cycle is
identified by the calendar year in which it starts, so `year=2020` with
`year_start=06-01` selects the cycle from 1 June 2020 to 31 May 2021.

Set `groupby=none` to treat the whole dataset as one continuous series instead of
grouping it into yearly cycles. This suits data with a single value per year (or
any coarse series): with `direction=drop` a multi-year decline and its
subsequent recovery are then detected as one event, turning the module into a
drop-and-recovery detector across years. In this mode `year` and `year_start` do
not apply, and the time-based settings (`max_gap`, `max_event_days`, recovery
times) are still expressed in days, so they scale with the observation interval
(e.g. about 365 days between annual maps).

### HOW EVENTS ARE DETECTED

For the chosen `direction` (*drop* or *rise*) the module walks the observations
of a pixel in time and follows each descent (or rise) to its turning point,
tolerating gaps between successive observations of up to `max_gap` days and
measuring how far the signal moves (its peak-to-trough amplitude). A descent or
rise ends when the signal rebounds by more than `noise_tolerance`, when a gap
longer than `max_gap` interrupts it, or at the end of the season.
`noise_tolerance` is the rebound expressed as a fraction of the current
peak-to-trough amplitude (default `0.15`). A closed descent is counted as an
event when its peak-to-trough amplitude reaches `threshold`.

`threshold_type` sets how `threshold` is read. When set to `absolute`, the
threshold is the value units of the data (default `0.2`, suitable for NDVI).
When set to `relative`, it represents a fraction of the pre-event level. And
when set to `mad`, the threshold represents a multiple of the per-pixel robust
standard deviation (1.4826 × MAD) computed over the analyzed year. Note that
this option loads the year stack into memory, so keep the computational region
to a reasonable size.

`max_gap` limits how far a descent is followed across missing data, so that
gradual seasonal development is not interpreted as one abrupt event. Set it
directly in days, or leave it unset to use the default of 3 × `step`. `step` is
the nominal observation interval. When `step` is not given, it is derived from
the dataset granularity if that is a whole number of days. Otherwise, it is
computed as the median spacing between the observation dates.

`max_event_days` determines what is considered abrupt. A descent that takes
longer than this many days from peak to trough is treated as a gradual
(seasonal) change and not counted. It defaults to `30` (about one month) with
`groupby=year`, and to `1.5 × step` with `groupby=none`, so that a single step of
a coarse series still qualifies. Set a large value to disable it. `season_start`
and `season_end` (calendar days of year, applied regardless of `year_start`)
restrict detection to a user-defined season.

### RECOVERY

After each event the module tracks how far the signal returns toward a reference
level. An event counts as *recovered* when the recovered fraction reaches
`recovery_target` (default `0.8`).

The reference depends on `baseline`. When set to `observed`, the recovery target
is the pre-event peak. The recovered fraction is computed as
`(value - trough) / (peak - trough)`. When set to `reference`, the recovery
target is the level expected for the time of year, taken from a climatology
strds (`reference`, keyed by day-of-year). Recovery is measured as the anomaly
(observed minus expected). Note that early-January and late-December dates will
be matched across the year boundary.

There are three possible recovery outcomes. An event can reach the
`recovery_target` before the next event or the end of the series. This is
counted as *recovered*. If a new event began before recovery was completed, the
maximum recovered fraction reached before the interruption is recorded (see
`mean_percent_restored`). This answers the question "does the signal restore
before the next event?". The third possibility is that the event was still open
at the end of the series, or continuity was broken by a gap longer than
`max_gap`. These are counted separately in `n_incomplete` and are excluded from
`mean_percent_restored`.

### OUTPUTS

The module creates a number of summary rasters listed below. 

- `<output>_count`: Number of detected events.
- `<output>_first_doy`, `<output>_last_doy`: Day-of-year of the trough (or peak)
  of the first and last event. With `groupby=none` these instead hold the number
  of days since the first observation, since a single day-of-year would be
  ambiguous across years. Either way the calendar date is the category label.
- `<output>_mean_magnitude`, `<output>_max_magnitude`: Mean and largest event magnitude (peak-to-trough) or smalles trough (through-to-peak).
- `<output>_n_recovered`, `<output>_frac_recovered`: Number and fraction of
  events that recovered.
- `<output>_mean_recovery_days`: Mean time to recovery over recovered events.
- `<output>_mean_percent_restored`: Mean maximum recovered fraction (0-100) over
  interrupted events.
- `<output>_n_incomplete`: Number of events that are still open at the end of
  the series, or with continuity broken by a gap longer than `max_gap`.

Each day-of-year raster also carries the matching calendar date (`YYYY-MM-DD`)
as the category label of its value, so *r.category* and the legend show real
dates.

With the `-g` flag, three diagnostic rasters are also written from the in-season
observations to help validate the settings against the available observations:

- `<output>_n_obs`: number of observations used (integer `CELL`).
- `<output>_mean_gap`, `<output>_max_gap_obs`: mean and largest gap in days
  between consecutive observations.

If `max_gap_obs` is well above `max_gap`, real changes may be split by long
cloud periods. If `n_obs` is low, results should be interpreted with care.

For a single cycle (a `year` restriction, or `groupby=none`), the outputs are
plain rasters named as above. When several cycles are analyzed, the result of
each cycle is written as a raster with the start-year suffix
(`<output>_count_2021`, `<output>_count_2022`, etc). And they are registered into
one space-time dataset named after the metric (`<output>_count`,
`<output>_first_doy`, ...), each layer time-stamped at its cycle start.

### PARCEL-LEVEL ANALYSIS

*t.rast.event* can also detect events at the parcel level. To do so, pass
a parcel vector map with `vector`. The module will in that case compute the
median per-parcel median and use this as input for event detection. This will
result in summary rasters with constant values within each parcel. Use the
`min_clear` parameter to set how much of a parcel must have a value for a date
to contribute (a fraction between 0 and 1). With the default (`0`), a single
valid pixel is enough. With `min_clear=0.5`, the majority of the pixels within a
parcel should have a value.

## NOTES


The module runs on the current computational region and honors the current
raster `MASK`.

Runtime scales with the number of maps times the number of cells. Most memory is
used with `threshold_type=mad`. Use the `memory` option to set the maximum
available RAM.

The module requires GRASS GIS 8.5 or newer. The input must be an absolute-time
STRDS.

## EXAMPLE

Detect grassland mowing events in an NDVI strds for 2021 (a 0.2 drop counts as
an event), characterize regrowth, and also write the gap diagnostics:

```sh
g.region -a raster=S160312_B01 vector=natura2000 -p
g.region n=n+100 s=s-100 w=w-100 e=e+100
r.mask vector=natura2000

t.rast.event input=S2_ndvi year=2021 output=mow -g \
  direction=drop threshold=0.2 threshold_type=absolute \
  season_start=60 season_end=300 recovery_target=0.8

r.colors map=mow_count color=viridis
```

Analyze several years at once by leaving `year` unset. Each metric is written as
a space-time dataset with one raster per year, which can then be queried or
aggregated over time:

```sh
t.rast.event input=S2_ndvi output=mow \
  direction=drop threshold=0.2 season_start=60 season_end=300

t.rast.list input=mow_count
t.rast.univar input=mow_count
```

For a monsoon or hydrological year, start each cycle on another date with
`year_start` so a disturbance around 1 January is not split between two years:

```sh
t.rast.event input=S2_ndvi output=mons \
  direction=drop threshold=0.2 year_start=06-01
```

Detect multi-year drops and their recovery in an annual series (one map per
year, e.g. annual maximum NDVI or a yearly drought index) by analyzing the whole
series at once with `groupby=none`:

```sh
t.rast.event input=ndvi_annual output=decline groupby=none \
  direction=drop threshold=0.15 recovery_target=0.8
```

## REFERENCES

Kolecka, N., Ginzler, C., Pazur, R., Price, B., & Verburg, P. H. (2018).
Regional Scale Mapping of Grassland Mowing Frequency with Sentinel-2 Time
Series. Remote Sensing, 10(8), 1221. https://doi.org/10.3390/rs10081221


## SEE ALSO

*[t.rast.stl](t.rast.stl)*,
*[t.rast.accdetect](t.rast.accdetect.md)*,
*[t.rast.aggregate](t.rast.aggregate.md)*

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth),
[Innovative Biomonitoring](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/)
and
[Climate-robust Landscapes](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)
research groups at the [HAS green academy](https://has.nl)

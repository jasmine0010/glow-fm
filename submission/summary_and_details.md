# GLOWfm: Space Apps 2026 submission draft

---

## Summary (192 words, 1,177 characters)

GLOWfm (Gauge-checked L-band Observation of Woodland flood maps) is an interactive dashboard and pipeline that maps floods hidden under forest canopies using the L-band radar on NASA and ISRO’s new NISAR satellite, whose 24 cm waves reveal flooded forest by passing through leaves and reflecting off water and tree trunks. These are areas that today’s flood map, Copernicus GFM, cannot observe. On October 24, 2026, it showed 0 hectares flooded along Georgia’s Satilla River, whereas gauges and lidar estimated 1,149. From a single NISAR pass near the crest, GLOWfm found 79% of the inundated area the gauges indicated, with 92% precision, using a method fixed in advance. Each map includes a built-in trust light, and users can follow a flood using both NISAR passes and river gauges. Of the 132 floods reported worldwide in the last 60 days, NISAR imaged 43 that GLOWfm could read. Through a live dashboard, an in-browser pipeline, and a one-page brief for emergency operators and aid groups, GLOWfm aims to give communities a view of floods today’s maps miss. Worldwide, 2.4 million km^2 of floodplain lies under trees, beside towns inhabited by more than 80 million people.

---

## Project details

### 1. What is GLOWfm?

GLOWfm is an open-source interactive dashboard and data pipeline that maps floods hidden under forest canopies, using the L-band radar on NASA and ISRO's NISAR satellite. Anyone can explore it in a web browser.

It is built on open data:
- NISAR L2 GCOV
- USGS 3DEP lidar and river gauges
- FABDEM and Copernicus GLO-30 elevation
- ESA WorldCover
- NASA GPM IMERG rainfall
- OpenStreetMap

We made it for emergency managers, aid groups, insurers and anyone wondering whether their local flood map can see under trees.

How it maps a flood:
- It compares each pixel of NISAR's flood pass with the median of earlier passes on the same track, and flooded forest shows up as a jump in brightness.
- It keeps only low ground near the river (within 6 m of its height) and lets each scene set its own cut-off with Otsu's method, which never drops below 0.5 dB.
- It grades every map with a trust light, and US maps are also scored against river gauges and lidar. On Georgia's Satilla River, GLOWfm found 79% of the flooded area with 92% precision where the official map's first scene showed none.

### 2. What gap does it fill?

The global standard flood map, Copernicus Global Flood Monitoring (GFM), relies on C-band radar with a 5.6 cm wavelength. These short waves scatter in the leaves before they ever reach the water, so GFM leaves forest out by design. We measured how much it misses:
- **Satilla River, GA:** On GFM's first scene of the flooded stretch (Oct 24, 2026), it mapped 0 ha, whereas gauges and lidar estimated 1,149 ha. 97% of the flooding sat inside GFM's own mask, and the missed water covered 8.2 km of road.
- **Three more Gulf Coast rivers (six passes):** GFM mapped at most 0.75 ha where gauges and lidar estimated anywhere from 832 to 17,972 ha.
- **Worldwide:** Our blind-spot atlas, which crosses Copernicus GloFAS 100-year flood-hazard maps with ESA WorldCover, finds 2.4 million km² of river floodplain under trees, beside about 1,900 towns home to about 80 million people.

GLOWfm maps exactly that excluded ground, since NISAR's longer waves reach the water under the canopy. We tested it on US rivers against gauges and lidar after freezing the method, and every map reports how far it can be trusted.

### 3. Exploring a flood: the interactive tools

**Live dashboard**
- **The map:** NISAR's flood map in magenta over satellite imagery, alongside every flood reported worldwide in the past 60 days.
- **Two modes:** *Live now* reads USGS gauges every 5 minutes, while *Past flood* replays a flood hour by hour with a time strip marking each NISAR pass.
- **The view switch:** You can look at NISAR's map, an independent gauge-and-lidar estimate computed in the browser, or both overlaid.
- **"What if the river rose?":** A slider redraws the flood for a rise of up to 5 m.
- **Layers and river cards:** Layers show roads under water and the blind-spot map, and each river's card gives its trust light, gauge trends, next NISAR pass and a "Likely cause" from NASA GPM IMERG rainfall.

**Interactive story.** The story takes you from orbit down to a single flooded tree, with an X-ray lens that reveals NISAR's map through the official map's blank one, a divider comparing Sentinel-1 and NISAR, and to-scale radar waves. Along the way you can replay a flood, play a game to find the hidden water and search for your own town.

**Run it yourself.**
- **What it runs:** GLOWfm's frozen method, ported to JavaScript and checked against the Python original on every case, runs right in the browser on 69 of this season's floods.
- **Explained and shareable:** Users can change the settings, see figures that explain each run (including a map of hits, misses and false alarms for gauged floods) and download a one-page brief, the map and the run's data.

**Results.** This page holds the full method and validation, with nine downloadable figures.

### 4. The science: why L-band sees through trees

NISAR, launched in 2025, is the first mission to image nearly all of Earth's land with L-band radar every 12 days. Its 24 cm waves are 4.3 times longer than Sentinel-1's 5.6 cm C-band waves, which lets them pass between leaves and branches.

When the forest floor floods, the water and trunks form a corner reflector, so the wave bounces off the water, hits a trunk and heads straight back to the satellite. This double bounce makes flooded forest turn brighter in HH polarization.

- **Pearl River forest, July 2026:** Flooded forest brightened by only 0.2 dB for Sentinel-1 but by 1.1 dB for NISAR.
- **Satilla:** The median flooded-forest pixel brightened by 3.0 dB, compared with 0.4 dB for dry forest.

### 5. How GLOWfm maps a flood

GLOWfm reads NISAR's L2 GCOV backscatter (γ⁰) at 50 m resolution. Every step is a fixed rule, written and hashed before any test data was opened.

1. **Change since before the flood.** Each pixel is compared with the median of the earlier passes on the same track from the 60 days before the flood (at least three, and the newest six in the live runs).
   Δ = 10·log₁₀ γ⁰<sub>HH, flood</sub> − median<sub>k</sub> ( 10·log₁₀ γ⁰<sub>HH, k</sub> )
   If higher ground also brightened by more than 0.5 dB, which points to rain-soaked soil rather than flooding, GLOWfm switches to Δ<sub>HH</sub> − Δ<sub>HV</sub>. Cross-polarized HV comes mainly from volume scattering in the canopy, so subtracting it removes the scene-wide wetting while keeping most of the flood signal.
2. **Where a flood is possible.** A pixel is kept only if it is:
   - within 4 km of the river
   - not cropland, grass or shrub (ESA WorldCover)
   - less than 6 m above the nearest drainage (HAND), using USGS 3DEP lidar in the US and FABDEM or GLO-30 elsewhere
3. **Each scene sets its own cut-off.** Otsu's method finds the split that best separates the valley-floor pixels into two groups by maximizing the between-class variance.
   t\* = argmax<sub>t</sub> ω₀(t) · ω₁(t) · [ μ₀(t) − μ₁(t) ]²
   A floor of τ = max(t\*, 0.5 dB) keeps the cut-off out of the noise, and any pixel with Δ > τ is flagged as flooded.
4. **Abstain when the flood is long gone.** GLOWfm doesn't map ground where the nearest gauge shows the river is far past its crest.
5. **The trust light.** If the water really is flooding under trees, low forest should brighten more than the forest above it.
   gap = median( Δ | forest, HAND < 2 m ) − median( Δ | forest, 4 m < HAND < 8 m )
   - **Green** if the gap is over 0.5 dB and no heavy rain fell (at least 5 mm in 24 hours or 25 mm in 72 hours)
   - **Amber** if rain wasn't checked
   - **Red** otherwise

   We fixed this rule before its first test, and so far it has been right on 3 of 4 new passes.

### 6. How we know it works

**The reference.** For US rivers, we interpolate USGS gauge levels along the valley and compare them with 3DEP lidar ground height, counting a pixel as flooded if water stands over 0.5 m above it and connects to the river.

**The score.** Each map is scored with the critical success index, where TP, FN and FP are hits, misses and false alarms.

CSI = TP / (TP + FN + FP)

Every score comes with a 95% interval from a block bootstrap (2 km blocks along the river and 2,000 resamples).

**Results:**
- **Frozen, one-time tests:** We ran 21 tests on 13 rivers, and 14 of them (on 11 rivers) had enough flooding to judge.
- **Latest test:** CSI ranged from 0.43 to 0.73 on the four judgeable passes, with Satilla on Oct 15 at 0.73 (95% interval 0.66 to 0.84).
- **Failures:** An earlier test of the same method failed on three rivers (CSI 0.05 to 0.10), and we show it beside the successes.
- **Against lidar alone:** A lidar-only map averaged 0.61 against NISAR's 0.62, so radar's real advantage is timing, because NISAR shows where the water is on the day.
- **The reference is a model:** Since it agrees with itself at only 0.72 when a gauge is hidden, scores near 0.72 are about as good as it can measure.
- **Without lidar (seven passes):** NISAR scored 0.35 with FABDEM, compared with 0.38 with lidar and 0.25 with treetop heights, so bare-earth global data closes most of the gap.

### 7. Impact

- **Reveals what the standard map leaves blank:** Where a blank on the standard flood map can be mistaken for an all-clear, GLOWfm shows the flooding and how reliable each map is.
- **Runs wherever NISAR passes:** GLOWfm only needs NISAR and open global data. Of the 132 floods reported worldwide in the last 60 days, NISAR captured 79 while they were still being reported, and 43 of those in scenes GLOWfm can read.
- **Open to non-specialists:** Anyone can watch a flood progress, compare it with river gauges and try what-if scenarios, while the story explains the physics.
- **Results that can be verified:** Every test was frozen and run once, failures are published with confidence intervals, the data is downloadable and the trust light itself is on trial.

---

## Use of Artificial Intelligence (AI)

- **The method itself uses no AI or machine learning.** Each step is a fixed rule (Otsu's threshold, height and land-cover limits, a contrast check), written and hashed before testing.
- **Much of the code was written with AI assistance (Claude, by Anthropic)**, under the team's design and direction:
  - the Python pipeline
  - the JavaScript site
  - the browser port of the method
- **Every result was checked against the data:**
  - 139 automated tests
  - a check that the browser method matches the Python method on all 69 cases
  - figures rebuilt from the saved outputs
- **No AI-generated images or NASA branding** are used.

## NASA Data

- **NISAR L2 GCOV** (NASA/ISRO), the radar behind every flood map, via the [Alaska Satellite Facility DAAC](https://asf.alaska.edu/data-sets/sar-data-sets/nisar/) and [NASA Earthdata](https://www.earthdata.nasa.gov/)
- **NASA CMR**, the catalog used to find NISAR passes over each flood: [cmr.earthdata.nasa.gov](https://cmr.earthdata.nasa.gov/search)
- **NASA GPM IMERG** rainfall, for the rain check and each flood's likely cause: [gpm.nasa.gov](https://gpm.nasa.gov/data/imerg)
- **OPERA DSWx-S1** (NASA JPL), a second open-water map checked in the audit of what today's maps miss: [OPERA](https://www.jpl.nasa.gov/go/opera/)

## Space Agency Partner & Other Data

- **ISRO:** NISAR partner agency
- **ESA / Copernicus:**
  - Copernicus Global Flood Monitoring ([GFM](https://global-flood.emergency.copernicus.eu/))
  - Sentinel-1 RTC (via [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc))
  - Sentinel-2 imagery
  - [ESA WorldCover 2021](https://esa-worldcover.org/)
  - Copernicus DEM GLO-30
  - Copernicus CEMS GloFAS 100-year flood-hazard maps
- **USGS:** [3DEP lidar](https://www.usgs.gov/3d-elevation-program), river gauges ([USGS Water Data](https://waterdata.usgs.gov/)) and NLDI river networks
- **NOAA:** flood stages from the [National Water Prediction Service](https://water.noaa.gov/), and VDatum
- **Elsewhere:**
  - [FABDEM](https://data.bris.ac.uk/data/dataset/s5hqmjcdj8yo2ibzi9b4ew3sn) (University of Bristol)
  - [GDACS](https://www.gdacs.org/) flood alerts
  - [OpenStreetMap](https://www.openstreetmap.org/) roads
  - GeoNames towns
  - Esri World Imagery

## Tools

- **Python:** NumPy, SciPy, rasterio, pyproj, h5py and Pillow, plus pytest with 139 tests
- **JavaScript:** MapLibre GL, Canvas and SVG for the maps and figures, and the Web Audio API for sound, with no framework

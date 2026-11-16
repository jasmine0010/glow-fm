# GLOWfm: Space Apps 2026 submission draft

---

## Summary (192 words, 1,177 characters)

GLOWfm (Gauge-checked L-band Observation of Woodland flood maps) is an interactive dashboard and pipeline that maps floods hidden under forest canopies using the L-band radar on NASA and ISRO’s new NISAR satellite, whose 24 cm waves reveal flooded forest by passing through leaves and reflecting off water and tree trunks. These are areas that today’s flood map, Copernicus GFM, cannot observe. On October 24, 2026, it showed 0 hectares flooded along Georgia’s Satilla River, whereas gauges and lidar estimated 1,149. From a single NISAR pass near the crest, GLOWfm found 79% of the inundated area the gauges indicated, with 92% precision, using a method fixed in advance. Each map includes a built-in trust light, and users can follow a flood using both NISAR passes and river gauges. Of the 132 floods reported worldwide in the last 60 days, NISAR imaged 43 that GLOWfm could read. Through a live dashboard, an in-browser pipeline, and a one-page brief for emergency operators and aid groups, GLOWfm aims to give communities a view of floods today’s maps miss. Worldwide, 2.4 million km^2 of floodplain lies under trees, beside towns inhabited by more than 80 million people.

---

## Project details

### 1. What is GLOWfm?

GLOWfm is an open-source interactive dashboard and data pipeline that maps floods hidden under forest canopies, using the L-band radar on NASA and ISRO's NISAR satellite. Anyone can explore it in a web browser.

It is built on open data:
- NISAR L2 GCOV;
- USGS 3DEP lidar and river gauges;
- FABDEM and Copernicus GLO-30 elevation;
- ESA WorldCover;
- NASA GPM IMERG rainfall;
- OpenStreetMap.

It is made for emergency managers, aid groups and insurers, and for anyone who wants to know whether the flood map near them can see under trees.

How it maps a flood:
- Compares NISAR's flood pass with the median of up to six earlier passes, pixel by pixel. Flooded forest shows up as a jump in brightness
- Keeps low ground near the river (within 6 m of its height) and lets each scene set its own cut-off (Otsu's method, never below 0.5 dB)
- Grades every map with a trust light, and scores US maps against river gauges and lidar. On Georgia's Satilla River, it found 79% of the flooded area with 92% precision, where the official map's first scene showed none

### 2. What gap does it fill?

The global standard flood map, Copernicus Global Flood Monitoring (GFM), uses C-band radar (5.6 cm). Its waves scatter in leaves before reaching the water, so GFM excludes forest by design. We measured what it misses:
- **Satilla River, GA:** on GFM's first scene of the flooded stretch (Oct 24, 2026), GFM mapped 0 ha, where gauges and lidar estimate 1,149 ha. 96% of the flooding lay inside GFM's mask, covering 8.2 km of road
- **Three more Gulf Coast rivers (six passes):** GFM mapped at most 0.75 ha, where gauges and lidar estimated 832–17,972 ha
- **Worldwide:** our blind-spot atlas (Copernicus GloFAS 100-year flood-hazard maps crossed with ESA WorldCover) finds 2.4 million km² of river floodplain under trees, beside 1,355 towns home to about 81.6 million people

GLOWfm's contribution is a flood map for exactly that excluded ground, using NISAR's L-band radar, whose waves reach the water under the canopy. The method was tested on US rivers against gauges and lidar, frozen before each river's data was opened, and every map reports how far it can be trusted.

### 3. Exploring a flood: the interactive tools

**Live dashboard**
- **The map:** NISAR's flood map in magenta over satellite imagery, with every flood reported worldwide in the past 60 days and the NISAR passes over each
- **Two modes:**
  - *Live now* reads USGS gauges every 5 minutes;
  - *Past flood* replays a flood hour by hour, with a time strip marking each NISAR pass.
- **The view switch:** NISAR's map, an independent gauge-and-lidar estimate computed in the browser, or both overlaid
- **"What if the river rose?":** a slider that redraws the flood for a rise of up to 5 m
- **Layers and river cards:** roads under water, gauges, reported floods and the blind-spot map, plus a card per river with its trust light, gauge trends, next NISAR pass and a "Likely cause" line from NASA GPM IMERG rainfall

**Interactive story.** A journey from orbit to a single flooded tree, with an X-ray lens that reveals NISAR's map through the official map's blank one, a Sentinel-1 versus NISAR divider, to-scale radar waves, a flood replayed pass by pass, a game and a town search.

**Run it yourself.**
- **What it runs:** GLOWfm's frozen method, ported to JavaScript and checked against the Python original on every case, runs in the browser on 41 of this season's floods.
- **Explained and shareable:** users can change settings, see figures explaining each run (the cut-off, the trust-light check, and for gauged floods a map of hits, misses and false alarms), and download a one-page brief, the map and the run's data.

**Results.** The full method and validation, with 12 downloadable figures.

### 4. The science: why L-band sees through trees

NISAR (launched 2025) is the first mission to image nearly all of Earth's land with L-band radar every 12 days. Its 24 cm waves, 4.3× longer than Sentinel-1's 5.6 cm C-band, pass between leaves and branches.

Over flooded forest, the water and the trunks form a corner reflector. The wave reflects off the water, hits a trunk and returns to the satellite (the double bounce), so flooded forest turns brighter in HH polarization.

- **Pearl River forest, July 2026:** flooded forest brightened +0.2 dB for Sentinel-1 but +1.1 dB for NISAR.
- **Satilla:** the median flooded-forest pixel brightened +3.0 dB, against +0.4 dB for dry forest.

### 5. How GLOWfm maps a flood

GLOWfm reads NISAR's L2 GCOV backscatter (γ⁰) at 50 m. Every step is a fixed rule, written and hashed before the test data was opened.

1. **Change since before the flood.** Each pixel is compared with the median of up to six earlier passes on the same track, from the 60 days before the flood:
   Δ = 10·log₁₀ γ⁰<sub>HH, flood</sub> − median<sub>k</sub> ( 10·log₁₀ γ⁰<sub>HH, k</sub> )
   If higher ground also brightened by more than 0.5 dB (a sign of rain-soaked soil, not flooding), GLOWfm uses Δ<sub>HH</sub> − Δ<sub>HV</sub> instead. Cross-polarized HV comes mainly from canopy volume scattering, so subtracting it removes scene-wide wetting and keeps most of the flood signal.
2. **Where a flood is possible.** A pixel is kept only if it is:
   - within 4 km of the river;
   - not cropland, grass or shrub (ESA WorldCover);
   - less than 6 m above the nearest drainage (HAND), from USGS 3DEP lidar in the US and FABDEM or GLO-30 elsewhere.
3. **Each scene sets its own cut-off.** Otsu's method picks the split that maximizes the between-class variance on the valley floor:
   t\* = argmax<sub>t</sub> ω₀(t) · ω₁(t) · [ μ₀(t) − μ₁(t) ]²
   A floor, τ = max(t\*, 0.5 dB), keeps the cut-off out of noise. A pixel is flagged flooded if Δ > τ.
4. **Abstain when the flood is long gone.** Where the nearest gauge shows the river far past its crest, GLOWfm doesn't map that ground.
5. **The trust light.** If this is flooding under trees, low forest should brighten more than higher forest:
   gap = median( Δ | forest, HAND < 2 m ) − median( Δ | forest, 4 m < HAND < 8 m )
   - **Green** if the gap is over 0.5 dB and no heavy rain fell (heavy means ≥ 5 mm in 24 h or ≥ 25 mm in 72 h);
   - **Amber** where rain wasn't checked;
   - **Red** otherwise.

   Fixed before its first test, it has been right on 3 of 4 new passes so far.

### 6. How we know it works

**The reference.** For US rivers, USGS gauge water levels are interpolated along the valley and compared with 3DEP lidar ground height. A pixel counts as flooded if the water stands more than 0.5 m above the ground and connects to the river.

**The score.** Maps are scored with the critical success index:

CSI = TP / (TP + FN + FP)

Here TP, FN and FP are hits, misses and false alarms. Each score has a 95% interval from a 2 km block bootstrap (2,000 resamples).

**Results:**
- **Frozen, one-time tests:** 21 tests on 13 rivers, 14 of them (on 11 rivers) with enough flooding to judge
- **Latest test:** CSI 0.43–0.73 on the four judgeable passes. Satilla Oct 15 scored 0.73 (95% 0.66–0.84), with 79% recall and 92% precision
- **Failures, published:** an earlier test of the same method failed on three rivers (CSI 0.05–0.10)
- **Against lidar alone:** a lidar-only map averaged 0.61, against NISAR's 0.62. Radar's clear extra is the date: a lidar map looks the same every day
- **The reference is a model:** it agrees with itself at 0.72 when one gauge is hidden, so scores near 0.72 are about as close as it can judge
- **Without lidar** (seven passes): NISAR scored 0.35 with FABDEM, against 0.38 with lidar and 0.25 with treetop heights. Bare-earth global data closes most of the gap


### 7. Impact

- **Reveals what the standard map leaves blank.** In forested floodplains, where a blank on the standard flood map can read as an all-clear, GLOWfm reveals the flooding and indicates how reliable each map is.
- **Runs wherever NISAR passes.** It needs only NISAR and open global data. Of the 132 floods reported worldwide in the last 60 days, NISAR captured 79 while they were still reported, 43 of them in scenes GLOWfm can read.
- **Open to non-specialists.** Anyone can watch a flood progress, compare it with river gauges and test what-if scenarios, while the story explains the physics.
- **Results that can be verified:** frozen protocols and one-time tests, published failures with confidence intervals, downloadable data, and a trust light that is itself on trial.

---

## Use of Artificial Intelligence (AI)

- **The method itself uses no AI or machine learning.** Each step is a fixed rule (Otsu's threshold, height and land-cover limits, a contrast check), written and hashed before testing.
- **Much of the code was written with AI assistance (Claude, by Anthropic)**, under the team's design and direction:
  - the Python pipeline;
  - the JavaScript site;
  - the browser port of the method.
- **Every result was checked against the data:**
  - 138 automated tests;
  - a check that the browser method matches the Python method on all 41 cases;
  - figures rebuilt from the saved outputs.
- **No AI-generated images or NASA branding** are used. The site's footer states the AI assistance.

## NASA Data

- **NISAR L2 GCOV** (NASA/ISRO), the radar behind every flood map, via the [Alaska Satellite Facility DAAC](https://asf.alaska.edu/data-sets/sar-data-sets/nisar/) and [NASA Earthdata](https://www.earthdata.nasa.gov/).
- **NASA CMR**, the catalog used to find NISAR passes over each flood: [cmr.earthdata.nasa.gov](https://cmr.earthdata.nasa.gov/search).
- **NASA GPM IMERG** rainfall, for the rain check and each flood's likely cause: [gpm.nasa.gov](https://gpm.nasa.gov/data/imerg).
- **OPERA DSWx-S1** (NASA JPL), a second open-water map checked in the audit of what today's maps miss: [OPERA](https://www.jpl.nasa.gov/go/opera/).

## Space Agency Partner & Other Data

- **ISRO:** NISAR partner agency.
- **ESA / Copernicus:**
  - Copernicus Global Flood Monitoring ([GFM](https://global-flood.emergency.copernicus.eu/));
  - Sentinel-1 RTC (via [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc));
  - Sentinel-2 imagery;
  - [ESA WorldCover 2021](https://esa-worldcover.org/);
  - Copernicus DEM GLO-30;
  - Copernicus CEMS GloFAS 100-year flood-hazard maps.
- **USGS:** [3DEP lidar](https://www.usgs.gov/3d-elevation-program), river gauges ([USGS Water Data](https://waterdata.usgs.gov/)) and NLDI river networks.
- **NOAA:** flood stages from the [National Water Prediction Service](https://water.noaa.gov/), and VDatum.
- **Elsewhere:**
  - [FABDEM](https://data.bris.ac.uk/data/dataset/s5hqmjcdj8yo2ibzi9b4ew3sn) (University of Bristol);
  - [GDACS](https://www.gdacs.org/) flood alerts;
  - [OpenStreetMap](https://www.openstreetmap.org/) roads;
  - GeoNames towns;
  - Esri World Imagery.

## Tools

- **Python:** NumPy, SciPy, rasterio, pyproj, h5py and Pillow; pytest, with 138 tests.
- **JavaScript:** no framework. MapLibre GL, Canvas and SVG for the maps and figures, and the Web Audio API for sound.

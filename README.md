# Summary

GLOWfm (Gauge-checked L-band Observation of Woodland flood maps) is an interactive dashboard and pipeline that finds floods hidden under forest canopy. It uses the L-band radar on NASA and ISRO’s new NISAR satellite, whose 24 cm waves pass through leaves and bounce off the water and tree trunks below to reveal flooded forests. Today’s main global flood map, Copernicus GFM, cannot identify these areas at all. On October 24, 2026, it showed 0 hectares flooded along Georgia’s Satilla River, while gauges and lidar put the flooded area at 1,149 hectares. From a single NISAR pass near the crest, GLOWfm found 79% of the flooding the gauges pointed to with 92% precision, using a method that was fixed in advance. Every map comes with a built-in trust light, and users can follow a flood as it rises and falls through both NISAR passes and river gauges. Of the 132 floods reported worldwide in the last 60 days, NISAR imaged 43 that GLOWfm could read. Through a live dashboard, a pipeline that runs in the browser and a one-page brief for emergency operators and aid groups, GLOWfm aims to show communities the floods that today’s maps miss. That gap is large, since 2.4 million km² of the world’s floodplain lies under trees, beside towns that are home to more than 80 million people.

# Project Demonstration

https://drive.google.com/file/d/1Q--R_ChN_bnBYuBd7m4-IwxWRQtXvDPk/view?usp=sharing

# Project

https://glowfm.earth

# Project Details

## 1. What is GLOWfm?

GLOWfm is an open-source interactive dashboard and data pipeline that maps floods hidden under forest canopies, using the L-band radar on NASA and ISRO's NISAR satellite. Anyone can explore it in a web browser. It is built on open data, including:

* NISAR L2 GCOV
* USGS 3DEP lidar and river gauges
* FABDEM and Copernicus GLO-30 elevation
* ESA WorldCover
* NASA GPM IMERG rainfall
* OpenStreetMap

We made it for emergency managers, aid groups and anyone curious about whether their local flood map can see under trees. Here is how it maps a flood:

* It compares each pixel of NISAR's flood pass with the median of up to six earlier passes, and flooded forest shows up as a jump in brightness.
* It keeps only low ground near the river (within 6 m of its height) and lets each scene set its own cut-off with Otsu's method, which never drops below 0.5 dB.
* It grades every map with a trust light, and US maps are also scored against river gauges and lidar. On Georgia's Satilla River, GLOWfm found 79% of the flooded area with 92% precision where the official map's first scene showed none.

## 2. What gap does it fill?

The global standard flood map, Copernicus Global Flood Monitoring (GFM), relies on C-band radar with a 5.6 cm wavelength. These short waves scatter in the leaves before they ever reach the water, so GFM leaves forest out by design. We measured how much it misses:

* Satilla River, GA: On GFM's first scene of the flooded stretch (Oct 24, 2026), it mapped 0 ha, whereas gauges and lidar estimated 1,149 ha. 96% of the flooding sat inside GFM's own mask, and the missed water covered 8.2 km of road.
* Three more Gulf Coast rivers (six passes): GFM mapped at most 0.75 ha where gauges and lidar estimated anywhere from 832 to 17,972 ha.
* Worldwide: Our blind-spot atlas finds 2.4 million km² of river floodplain under trees, beside 1,355 towns home to about 81.6 million people.

GLOWfm maps that excluded ground, since NISAR's longer waves reach the water under the canopy. We tested it on US rivers against gauges and lidar after freezing the method, and every map reports how far it can be trusted.

## 3. Exploring a flood: the interactive tools

### Live dashboard

* Map: NISAR's flood map in magenta over satellite imagery, alongside every flood reported worldwide in the past 60 days.
* Following a flood: The dashboard tracks floods hour by hour from USGS gauges, with both live and past floods.
* View switch: You can look at NISAR's map, an independent gauge-and-lidar estimate computed in the browser, or both overlaid.
* "What if the river rose?": A slider plays out a hypothetical rise of up to 5 m at every gauge and shows where the water would spread.
* Layers and river cards: Layers show roads under water and the blind-spot map, and each river's card gives its trust light, gauge trends, next NISAR pass and a "Likely cause" from NASA GPM IMERG rainfall.

### Interactive story

* The story zooms from orbit down to a single flood, with an X-ray lens illustrating NISAR’s flood map beneath the official map’s blank one, a slider comparing Sentinel-1 with NISAR, and radar waves showing why only L-band reaches the water. You can also replay a flood and search for your own town.

### Run it yourself

* GLOWfm's frozen method runs in the browser on 32 of this season's floods.
* Users can change the settings, see figures that explain each run (including a map of hits, misses and false alarms for gauged floods) and download a one-page brief, the map and the run's data.

### Results

* This page holds the full method and validation, with downloadable figures.

## 4. The science: why L-band sees through trees

NISAR, launched in 2025, is the first mission to image nearly all of Earth's land with L-band radar every 12 days. Its 24 cm waves are 4.3 times longer than Sentinel-1's 5.6 cm C-band waves, which lets them pass between leaves and branches.

When the forest floor floods, the water and trunks form a corner reflector, so the wave bounces off the water, hits a trunk and heads straight back to the satellite. This double bounce makes flooded forest appear brighter in HH polarization.

* Pearl River forest: Flooded forest brightened by only 0.2 dB for Sentinel-1 but by 1.1 dB for NISAR.
* Satilla: The median flooded-forest pixel brightened by 3.0 dB, compared with 0.4 dB for dry forest.

## 5. How GLOWfm maps a flood

GLOWfm reads NISAR's L2 GCOV backscatter (γ⁰) at 50 m resolution. Every step is a fixed rule that was written and hashed before validation data was opened.

1. **Change since before the flood:** Each pixel is compared with the median of the earlier passes on the same track from the 60 days before the flood.
   1. Δ = 10·log₁₀ γ⁰(HH, flood) − medianₖ [10·log₁₀ γ⁰(HH, k)]
2. If higher ground also brightened by more than 0.5 dB, which points to rain-soaked soil rather than flooding, GLOWfm switches to ΔHH − ΔHV. Cross-polarized HV comes mainly from volume scattering in the canopy, so subtracting it removes the scene-wide wetting while keeping most of the flood signal.
3. **Where a flood is possible:** A pixel is kept only if it is:
   * Within 4 km of the river
   * Not cropland, grass or shrub (ESA WorldCover)
   * Less than 6 m above the nearest drainage (HAND), using USGS 3DEP lidar in the US and FABDEM or GLO-30 elsewhere
4. **Each scene sets its own cut-off:** Otsu's method finds the split t* that best separates the valley-floor pixels into two groups by maximizing the between-class variance. A floor of τ = max(t*, 0.5 dB) keeps the cut-off out of the noise, and any pixel with Δ > τ is flagged as flooded.
   1. t* = argmaxₜ ω₀(t) · ω₁(t) · [μ₀(t) − μ₁(t)]²
5. **Skip floods that have already drained:** GLOWfm doesn't map ground where the nearest gauge shows the river is far past its crest.
6. **The trust light:** If the water really is flooding under trees, low forest should brighten more than the forest above it. gap = median(Δ | forest, HAND < 2 m) − median(Δ | forest, 4 m < HAND < 8 m)
   1. Green if the gap is over 0.5 dB and no heavy rain fell (at least 5 mm in 24 hours or 25 mm in 72 hours)
   2. Amber if rain wasn't checked
   3. Red otherwise

## 6. How we know it works

For US rivers, we interpolate USGS gauge levels along the valley and compare them with 3DEP lidar ground height, counting a pixel as flooded if water stands over 0.5 m above it and connects to the river.

Score: Each map is scored with the critical success index, where TP, FN and FP are hits, misses and false alarms, respectively.

CSI = TP / (TP + FN + FP)

Results:

* Frozen, one-time tests: We ran 21 tests on 13 rivers, and 14 of them (on 11 rivers) had enough flooding to judge.
* Latest test: CSI ranged from 0.43 to 0.73 on the four judgeable passes, with Satilla on Oct 15 at 0.73 (95% interval 0.66 to 0.84).
* Against lidar alone: GLOWfm narrowly outscored a lidar-only map on three of the four judgeable passes (an average CSI of 0.62 against 0.61), even though the reference is built from that same lidar and favors the lidar map. Only the radar, not the lidar, shows where the water actually is on the day, as it arrives and drains.
* The reference is a model: Since it agrees with itself at only 0.72 when a gauge is hidden, scores near 0.72 are about as good as it can measure.
* Without lidar (seven passes): NISAR scored 0.35 with FABDEM, compared with 0.38 with lidar and 0.25 with treetop heights, so bare-earth global data closes most of the gap.

## 7. Impact

* In regions where a blank on the standard flood map can be mistaken for an all-clear, GLOWfm shows the flooding and how reliable each map is.
* Anyone can watch a flood progress, compare it with river gauges and try what-if scenarios, while the story explains the physics.
* GLOWfm only needs NISAR and open global data. Of the 132 floods reported worldwide in the last 60 days, NISAR captured 79 while they were still being reported, and 43 of those in scenes GLOWfm can read.
* Every test was fixed in advance and run once, failures included, with confidence intervals and downloadable data.

# NASA Data

* [NASA Earthdata (NISAR, OPERA DSWx-S1, GPM IMERG)](https://www.earthdata.nasa.gov/)
* [NISAR mission (NASA JPL and ISRO)](https://nisar.jpl.nasa.gov/)
* [NASA POWER](https://power.larc.nasa.gov/)

# Space Agency Partner & Other Data

* [Copernicus Sentinel-1 and Sentinel-2](https://dataspace.copernicus.eu/)
* [Copernicus GFM and GloFAS](https://global-flood.emergency.copernicus.eu/)
* [ESA WorldCover 2021](https://esa-worldcover.org/)
* [Copernicus DEM GLO-30](https://registry.opendata.aws/copernicus-dem/)
* [FABDEM V1-2](https://doi.org/10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn)
* [USGS Water Data](https://waterdata.usgs.gov/)
* [USGS 3DEP lidar](https://www.usgs.gov/3d-elevation-program)
* [NOAA water and imagery data](https://www.noaa.gov/)
* [GDACS](https://www.gdacs.org/)
* [OpenStreetMap](https://www.openstreetmap.org/copyright)
* [Esri World Imagery](https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9)
* [GeoNames and Natural Earth](https://www.geonames.org/)

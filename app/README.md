# Hidden Floods web app

A static site with no server. MapLibre GL 4.7.1 loads from a CDN (and Plotly 2.35.2, for the dashboard's graphs only), and all data is in `data/`. Every map and figure below the first screen loads only as it nears the screen.

```bash
# rebuild data (after any analysis change)
C:/Users/Jasmi/.venvs/hidden-floods/Scripts/python.exe scripts/build_app.py
# preview locally
C:/Users/Jasmi/.venvs/hidden-floods/Scripts/python.exe scripts/serve_app.py   # tells browsers to check for newer files
```

## Design

One world for every page: the night side of the Earth with NISAR (`body.night` in `style.css`). The color tokens at the top of `style.css` give each color one meaning, and `shared.js` reads them into `PALETTE` for maps and charts: cyan is water (the river's answer), green-teal is floodplain forest, magenta is NISAR, blue is the official flood map (Copernicus GFM), gray is where the official map can't look, amber is people and "you", and gold is only for buttons that act. Forest is always points, water is always filled areas, and a miss is hatched, so no meaning rests on color alone. Numbers use one quiet style (`.qn`: Space Grotesk, tabular figures), each section opens with an instrument readout computed from its data (`setReadout`, `pow10` in `shared.js`), and maps feather into the night instead of sitting in boxes. `shared.js` also holds the one basemap (`BASEMAP`), the chart font and legend, the gauge marker, the scale bar, `countUp`, `countWhenSeen` and `visibleLoop`, which runs an animation only while it's on screen. Keep text at 12px or larger and targets at 24px or larger.

Shared pieces: `globe.js` (the night globe; `makeGlobe()` gives each section its own, sharing one load of the points, towns and coastlines), `strip.js` (the pass strip: river levels with every satellite look and a playhead, also a slider), `orbit.js` (the orbit rail) and `sound.js` (opt-in sound).

## Story page (`index.html`, `story.js`)

Written for readers with no background, as one night with NISAR. Each part shows a claim, one line and a visual; its caveats sit in a collapsed "The fine print" panel beside it (`<details class="fine">`). Every number, date and count is computed from the data files; only outside facts (NISAR's orbit and swath, its 12-day repeat, Greenland's area) are typed.

**One stage behind the whole page** (`stage.js`): a fixed night canvas, so the same points of light carry from the opening to the end instead of each part starting from scratch. The Satilla's flood pixels (`acts.js`, from `data/story/thread.json`) move between layouts as you scroll, and the globe hands over to the journey's own canvas, and back, in exactly the same place. Each part keeps one or two things on screen: the stage, and a short heading or one window. The stage redraws only after a scroll or while a globe on screen is turning, drifts a few pixels with the mouse, and shows each part's end state with reduced motion.

1. **The finding:** an X-ray lens on the held-out Satilla pass over a Sentinel-2 photo, the official GFM map or the river's answer, with the globe rising under it.
2. **Act 1, what the map misses:** the flood's pixels bloom out of Georgia into their real shape, and the official map's own mask passes over them, with a key, a 10 km scale bar and the river's name; one number. Then one line on who acts on a blank map, as the pixels fold back into the globe.
3. **The journey** (`lantern.js`, `globe.js`): the scroll-driven flight from orbit to one flooded tree, unchanged; its canvas shows only while it's pinned.
4. **Act 2, how NISAR sees it:** the tree's water line sorts itself into two dot histograms of the change in radar brightness, flooded pixels above and dry below, each dot one 2.5 ha pixel, with both medians labeled; one number.
5. **Why NISAR:** the histogram fades where it stands as the C-band / L-band map opens.
6. **Watch it move:** the Yellow River night log; its maps now crossfade from pass to pass.
7. **Beat the satellite** (`game.js`): the game, opened the same way as a window.
8. **Act 3, your turn, and your town** (`where.js`): one light appears where the town globe will be, and the globe grows from it, which takes over once it lands (or as soon as someone searches).
9. **The tools:** the globe unrolls into the equal-area world map, and this season's reported floods light up where NISAR passed with a scene GLOWfm can read; two links.
10. **The proof:** every judged test as a dot at its score, one lane per method, with the Satilla's own test ringed; one number. Then Go deeper, and the footer zooms back out to orbit.

The orbit rail down the right edge (`orbit.js`) is the page's navigation: one station per part, the journey's seven parts as smaller stations, and a satellite that follows the scroll. On phones it's a line under the top bar plus a Sections menu. Parts fade in as they arrive (skipped under reduced motion). The sound switch in the top bar is off by default.

**Trust light.** Every NISAR map on the site carries one (`trustLight` in `shared.js`). It is the trust signal fixed in `research/OVERBANK_PROTOCOL.md` section 4: green if the map's own contrast check passed and there was no heavy rain (`research/RAINFALL.md`), red otherwise, gray when the method declines to map, and amber on the Run it yourself floods, where rain isn't checked. It was right on 3 of 4 fresh passes, which the protocol calls too few for a verdict, and the site says so.

## Dashboard tour (`dashtour.js`)

A short popup beside each key control of the dashboard, one at a time, with Back and Next: what the map shows, choosing a flood, NISAR's answer, the what-if slider, live or past, map layers and More. It opens by itself on a first visit (remembered in that browser only), from More, and from `dashboard.html?tour=1` (the story page links there). Steps whose control is off screen, such as the side panels on a phone, are skipped. The older full-screen tour (`tour.html`, `tour.js`) is no longer linked.

## Results page (`evidence.html`, `evidence.js`, `figures.js`, `figkit.js`)

Written for readers who want to check the work, as a short paper: an abstract whose numbers are computed from the data, the four limits to know first, then Fig. 1–9 and Tables 1–3 in the order of the argument: the gap, the signal, the tests, then the checks. It opens with a three-sentence summary and four key numbers, and each figure shows one takeaway sentence with its full caption folded under it; the supporting figures and Methods are folded too, and printing opens everything. Figures and tables are numbered in page order by `evidence.js`, and every reference to one, on this page or another, names it by id (`#fig-accuracy`, `#no-lidar`). Repeats were cut: every test's score is in the every-frozen-test figure, the GFM masks are in the blind-spot figure, and the imagery checks, the ROC curves and agreement by depth, height and land cover are in Methods or the figure data. The file keeps its old name so existing links work.

- **Figures** (`figures.js`): study design, the radar signature (ridgeline), separability and ROC, maps of three frozen results, every frozen test with its interval, where it works, a flood through time, the official map's blind spot, the worldwide extent, the reference check, NISAR's coverage and the exploratory interferograms. Their data is built by `scripts/build_figures.py`, which checks it against the frozen records before writing (`tests/test_figures.py`). Captions are computed in `evidence.js`.
- **Post-hoc figure data** (descriptive; no frozen number changes; each script first checks it gives back the frozen CSI): `scripts/posthoc_result_maps.py` draws the results maps (hits, misses and false alarms on a strong, a typical and a failed pass) from the saved layers; `scripts/posthoc_reference_checks.py` scores each judged version-4 pass with the reference's water surface moved by −1 to +1 m (the reference figure's panel c), recomputes the intervals with 5 and 10 km blocks, and gives per-pass numbers under trees; `scripts/posthoc_swamp_fringes.py` draws the water-level-under-the-canopy figure. Methods summarizes the independent imagery checks in `research/INDEPENDENT_*`.
- **figkit.js** is a small SVG plotting kit in journal style (boxed axes, outward ticks, framed legends, capped error bars). Every figure downloads as SVG, PNG (2x) or the plotted data (CSV), and "Print colors" switches them to a white background for slides and print.
- Four of the figures also appear, in compact form, on the story page, each linking to its full version.

Fuller records stay in `research/`.

## Dashboard page (`dashboard.html`, `dashboard.js`, `estimator.js`)

A tool for using the data directly, live by default. The whole page is one map, with the controls floating around it, and every flood event stays on that map:

- **Moving between events:** choosing an event or its pin flies the camera there. Dragging the map onto a river, or clicking inside one, selects it too. Each river keeps its own NISAR and estimate layers while another is selected.
- **Live now:** current river levels from USGS (`waterservices.usgs.gov`), fetched by the browser every 5 minutes, and the newest scene dates from NASA's catalog (`cmr.earthdata.nasa.gov`). Neither needs a login.
- **Past flood:** Play, the Pass buttons and the arrow keys step from one NISAR pass to the next, so the map and the estimate show the same moment; dragging the time bar moves by the hour. A score shows only when the two match, and a warning appears when they're over a day apart. Rivers that aren't selected show their headline pass.
- **The map shows one thing at a time,** picked with the switch on the map: NISAR's flood map, the gauge-and-lidar estimate, or Both (the estimate in see-through cyan over NISAR's magenta: blue where they agree, magenta where only NISAR mapped flooding, cyan where only the estimate did). One map, so panning never changes what a pixel shows; `&show=nisar` or `&show=estimate` in a link.
- **Left panel:** flood events and five layer switches (roads, gauges, reported floods, the blind-spot map, and what today's flood map leaves out). The card holds the what-if rise; More holds the link, the CSV and the tour. River levels refresh every 5 minutes.
- **Right panel:** a plain summary sentence, then two big numbers (NISAR's mapped area with its trust light, and the gauge estimate), the what-if slider, and a label-and-value list in three groups: the river now (gauges above flood level, the closest gauge, the 6-hour trend, the 8-day peak, road under water, depth), NISAR (the pass shown, its orbit, a newer scene and the next pass from NASA's catalog, the lidar-only map) and the valley (length and area, share under trees and inside the official map's mask, counted from its pixels, the official map's record and the fair test). Rows appear only when there's data. Then buttons for the gauge table and graphs, and Details with a click-a-spot card and the caveat.
- **Bottom:** time slider, play and jump to a pass, and the map's scale and legend. The gauge table, graphs and About open in a drawer, and About is in the top bar.
- **Map instruments:** a thin strip with the coordinates, scale and color key, plus a labeled coordinate grid.
- **Phones and small windows:** the panels become sheets opened from the bottom row.
- **Accessibility:** status uses shapes and words as well as color, every control works from the keyboard, sliders report their values, moving to a flood is announced to screen readers, and the event list stands in for the map pins. `scripts/` has no automated check for this, so rerun an axe audit after layout changes.
- **Deep links:** `dashboard.html?river=yellow&mode=history&t=2026-10-16T00:36`, with `&show=` for the map's view.

**The estimate runs in the browser.** `estimator.js` follows `hydraulic_truth` in `src/hidden_floods/truth.py`, using per-river packs in `data/dashboard/`. At the end of each build, `scripts/check_estimator.cjs` compares it with the Python result on every recorded pass, and the build stops if any differs by more than 0.5%. This needs Node.

**What likely caused each flood.** The challenge asks for the physical drivers behind what the radar shows. `scripts/build_flood_rain.py` takes each dashboard river's crest from its recorded gauge levels, the catchment draining to its lowest gauge from USGS NLDI, and NASA GPM IMERG Late Run daily rainfall over that catchment for the 14 days to the crest, with the wettest 3-day spell (`data/dashboard/rain.json`). The dashboard card shows it as "Likely cause", and the Story's flood timeline as one line. Under 50 mm the site says the river was likely already high from earlier rain instead of naming rain (St. Johns, 31 mm). It is a hypothesis about the driver, not a measurement of it.

**Roads under water.** `scripts/build_roads.py` (run by the dashboard build) cuts the drivable OpenStreetMap roads saved for each river's blind-spot audit into short pieces, one per estimate pixel crossed, using the frozen audit's rules: footpaths and bridges left out. The dashboard loads them for the river on screen, draws each road with any flooded stretch whole in white and its flooded stretches in orange, (the "Road under water" layer), and the river card adds up their length and how much of it lies inside Copernicus GFM's exclusion mask. On the Satilla's Oct 15 pass it matches the audit's own count to within 0.4% (16.3 km against 16.2 km). Run it yourself does the same with NISAR's own flood map: `scripts/build_live_roads.py` saves each prepared flood's roads from OpenStreetMap (a custom run asks OpenStreetMap from the browser), and `live.js` lays them on the case's 50 m grid; the placement matches an exact projection to the kilometer on all five floods.

Replay uses hourly gauge levels, while research results use 15-minute readings, so a replayed pass can differ slightly from the recorded area (Satilla Oct 19 shows 2,269 ha against 2,266 ha).

**What is and isn't live:** river levels are live. Radar maps are fixed at build time, so they don't update with new NISAR scenes. If USGS can't be reached, the page falls back to a recorded flood and says so.

**Its rivers.** Every US river the project has gauges and lidar for:
- the ten held-out rivers, each built from its one-time frozen run in `outputs/<river>/<pass>/` (kept out of git; copy it over from the project folder that ran the tests), with the score, trust light and rain flag that run recorded;
- the four rivers the method was developed on;
- the St. Johns River, FL, the sealed test's river (`scripts/setup_st_johns.py`): no test yet, and its one NISAR map is Run it yourself's 24 km box around Astor, so the card doesn't compare that area with the river's estimate;
- rivers added by `scripts/auto_rivers.py`, below.

A river's data loads only once it's on screen.

**Adding rivers automatically.** `python scripts/auto_rivers.py` looks at every NOAA gauge in flood and adds the river when every check passes: at least two gauges on the main stem with a height above NAVD88 (a published datum, or one derived from their own readings), at least 8 km of river between them, at least 20% of the floodplain under trees, and a NISAR pass during the flood. It fetches the river's stage records, NWS flood stage, lidar and land cover, runs the frozen method on the radar box around the flooding gauge (with this computer's Earthdata login), lists the river in `sites/auto_rivers.json` and rebuilds the dashboard data; if the build's checks fail, the new rivers are taken out again. `--dry-run` only reports what it would do. Each decision goes to `<data root>/auto_rivers/log.jsonl`. These rivers are labeled "added automatically, not tested": dams and levees aren't checked, and nothing about them is scored.

Build the dashboard data alone with `python scripts/build_dashboard.py`, once `build_app.py` has run.

## Run it anywhere (local only)

```
python scripts/custom_server.py     # http://127.0.0.1:8767/live.html
```

Serves the site plus a local box reader, and the Run it yourself page gains "Or choose any place": draw a box on the map (5–50 km a side; a click drops a 24 km box, or type a latitude and longitude), pick dates, list the NISAR passes whose scene covers the whole box, and choose one. With no box, the panel lists the floods GDACS reported that had a pass of the kind the method reads (from the coverage figure's data), and choosing one searches a 24 km box on its reported point over its reported dates. A browser can't read NISAR's data files itself (NASA's data server refuses cross-site reads, and the files need an Earthdata sign-in), so the server reads just that box with this computer's sign-in (`~/.netrc`, with `hidden_floods.live_v2`'s readers, aligned to the scene's pixel edges), writes the pack to `outputs/custom/`, and the method runs in the browser as on every live case. Custom runs use the global inputs everywhere (FABDEM heights, nearest mapped water), have no gauges and no score, and are uses of the frozen method, not tests. The first run in a new region takes a few minutes (FABDEM tiles); later runs there take seconds. It listens on 127.0.0.1 only and publishes nothing. The page offers the panel only when this server marks it, so a static copy of the site never asks for the reader.

## Live runs (`live.html`, `live.js`, `livemethod.js`)

The frozen method v4 run on floods happening now, kept apart from the tested results. Cases are prepared on your computer
under `research/LIVE_PROTOCOL.md`:

```
python scripts/build_world_floods.py   # the worldwide flood list (GDACS)
python scripts/live_cases.py --dev     # development: inputs and the method only, into outputs/live_dev, never scored
python scripts/live_cases.py           # the frozen run: US cases scored once, published to app/data/live
python scripts/prepare_all_floods.py   # every other dashboard flood that can run (see below)
python scripts/build_live_roads.py     # roads for each new case
node scripts/check_live_method.cjs     # the browser's method against Python's, on every published case
```

**Every dashboard flood.** The protocol picks up to 6 US and 4 world floods per run. `scripts/prepare_all_floods.py`
runs the same frozen job, with protocol v2's inputs and receipts, on every flood the dashboard lists that has a usable
NISAR pass, with no cap. `--check` asks NASA's catalog only and lists which floods can run and why the rest can't. Cases
it adds are marked `"selection": "coverage"` (not picked by the protocol), its attempts go to
`research/coverage_attempts.log`, and why each other flood couldn't run goes to `index.json`'s `coverage.skipped`, which the
dashboard's flood card shows in place of a button. Its packs are stored gzipped (`pack.bin.gz`, about half the size), and
`live.js` unpacks them in the browser. A US flood gauge whose NOAA record names no USGS gauge gets the nearest USGS gauge on
the same river within 2 km; GDACS floods inside the US run map-only, like the world floods.

**Scope.** GLOWfm reads flooding under trees, so a flood is offered to run only when at least half of its valley floor
(land up to 6 m above the nearest water and within 4 km of the river) is forest or wetland in ESA WorldCover; cropland,
grass and shrub count against it, built-up ground and open water on neither side. `livescope.js` holds the rule, and
`node scripts/scope_cases.cjs` (run at the end of `prepare_all_floods.py`) writes each case's share into `index.json`.
Cases outside it stay published but aren't listed; a direct link says why, the page's footnote lists them with their
shares, and the dashboard's flood card gives the reason. The rule was added on Nov 15, 2026, after the list grew to
prairie and farmland rivers that scored near zero, and it reads only land cover and terrain, never a score.

**In flood at the pass.** A US flood is picked because its gauge reached NOAA's minor flood stage on some day, but a
tidal gauge tops it for an hour a day and a flash flood can be gone by the pass. `scripts/pass_stage.py` (also run at the
end of `prepare_all_floods.py`) reads USGS's 15-minute gage height nearest each US pass and writes it, with NOAA's flood
stage, into `index.json` as `pass_stage`; a flood below its flood stage at the pass isn't offered, for the same reasons
and in the same footnote as the scope rule. No reading within 45 minutes, or a NOAA gauge naming another USGS site, gives
no verdict, and the flood stays listed. Readings are cached in `outputs/pass_stage`. One exception, `EXEMPT` in the script:
St. Marys River near Macclenny read 11.8 ft against its 12 ft flood stage but 4 to 9 ft above its earlier passes, and is
offered anyway. It was chosen by hand after seeing its score, and the page says so.

- **US:** NOAA gauges at flood stage, with 3DEP lidar, USGS river lines and gauges. Scored once against the
  gauge-and-lidar estimate with the tested rivers' rules.
- **Elsewhere:** GDACS floods, with Copernicus GLO-30 heights. Published unscored.
- The job reads only a 24 km box from each NISAR scene with your Earthdata sign-in (curl and `~/.netrc`); the sign-in never
  reaches the site. Each case's `pack.bin` holds the radar, heights, land cover, gauge timing, permanent water and, for
  scored US cases, the estimate, so `livemethod.js` can rerun the method in the browser with other settings.
- A published case is never rerun or overwritten. Only the frozen run's score counts; the page says that settings chosen
  after seeing a score are tuning.
- **What a run shows** (`live.js`, `livefigs.js`), in the order a reader checks it:
  - the cut-off chart under the map, with Otsu's separability, so a one-humped histogram is called out;
  - whether low forest brightened more than high forest;
  - whether the flood pass clears the cut-off more often than the last pass before the flood (where it doesn't, the cut-off
    alone can't tell flood from ordinary change);
  - the trust light's own check;
  - for scored US cases, the score by cut-off with the published 95% range and a no-radar line (every forest pixel within
    the height limit), and a hit, miss and false-alarm map against the estimate;
  - the area with the method rerun at height limits from 2 to 10 m.

## Which numbers are which

- **First screen:** frozen v4 on a river it had never seen, built from the one-time run's saved layers (`build_hero` in `scripts/build_app.py`). The build stops if those layers don't reproduce the frozen CSI.
- **Yellow River section and explorer:** these rivers helped build v4, so their scores are development numbers, and the page says so. The build stops if v3 doesn't reproduce its frozen Yellow River CSI, or if v4 differs from its development scores.
- **GFM on the first screen:** Oct 24 is the first GFM scene that covers the stretch, nine days after the NISAR pass (`research/SATILLA_AUDIT.md`). The page labels both dates.

The Satilla GFM layers come from `scripts/audit_satilla.py`, which keeps them in their own `ops_audit` folder. Run it before `build_app.py` on a fresh machine.

**Chart colors** are in `CHART` in `shared.js`. They were checked with a color-blind palette validator on the dark background, and the cyan sits slightly outside its lightness band to keep it distinct from NISAR's magenta.

**Data encoding:** see the `scripts/build_app.py` docstring. Overlays are Web Mercator PNGs placed with MapLibre image sources. Click info is read from two opaque data PNGs through a canvas.

**Hosting:** the site is `app/` as it stands (about 100 MB with `data/`), and works from a subfolder, as GitHub Pages serves a project site. `.github/workflows/pages.yml` publishes it, but only when started by hand from the Actions tab; it never runs on a push. It also writes the full address of the link-preview card (`og-card.jpg`) into each page. `404.html` and `.nojekyll` are included. Basemap imagery is © Esri, so keep the attribution line in the footer.

**Releasing a change:** bump the `?v=` number on the script and stylesheet tags in every page, so visitors' browsers fetch the new files instead of mixing them with cached old ones.

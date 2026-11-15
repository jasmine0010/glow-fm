# Hidden Floods web app

A static site with no server. MapLibre GL 4.7.1 loads from a CDN (and Plotly 2.35.2, for the dashboard's graphs only), and all data is in `data/`. Every map and figure below the first screen loads only as it nears the screen.

```bash
# rebuild data (after any analysis change)
C:/Users/Jasmi/.venvs/hidden-floods/Scripts/python.exe scripts/build_app.py
# preview locally
C:/Users/Jasmi/.venvs/hidden-floods/Scripts/python.exe scripts/serve_app.py   # tells browsers to check for newer files
```

## Design

One world for every page: the night side of the Earth with NISAR (`body.night` in `style.css`). The colour tokens at the top of `style.css` give each colour one meaning, and `shared.js` reads them into `PALETTE` for maps and charts: cyan is water (the river's answer), green-teal is floodplain forest, magenta is NISAR, blue is the official flood map (Copernicus GFM), grey is where the official map can't look, amber is people and "you", and gold is only for buttons that act. Forest is always points, water is always filled areas, and a miss is hatched, so no meaning rests on colour alone. Numbers use one quiet style (`.qn`: Space Grotesk, tabular figures), each section opens with an instrument readout computed from its data (`setReadout`, `pow10` in `shared.js`), and maps feather into the night instead of sitting in boxes. `shared.js` also holds the one basemap (`BASEMAP`), the chart font and legend, the gauge marker, the scale bar, `countUp`, `countWhenSeen` and `visibleLoop`, which runs an animation only while it's on screen. Keep text at 12px or larger and targets at 24px or larger.

Shared pieces: `globe.js` (the night globe; `makeGlobe()` gives each section its own, sharing one load of the points, towns and coastlines), `strip.js` (the pass strip: river levels with every satellite look and a playhead, also a slider), `orbit.js` (the orbit rail) and `sound.js` (opt-in sound).

## Story page (`index.html`, `story.js`)

Written for readers with no background, as one night with NISAR. Each part shows a claim, one line and a visual; its caveats sit in a collapsed "The fine print" panel beside it (`<details class="fine">`). Every number, date and count is computed from the data files; only outside facts (NISAR's orbit and swath, its 12-day repeat, Greenland's area) are typed.

1. **The finding:** an X-ray lens on the held-out Satilla pass over a Sentinel-2 photo, the official GFM map (nine days later, so not scored against NISAR) or the river's answer. Two quiet numbers, the trust light, the tour and game buttons, and a town check.
2. **The journey** (`lantern.js`, `globe.js`): "NISAR's night shift", a full-screen, scroll-driven flight on the night side of the Earth. The planet is drawn only from its floodplain forests as points of light (`data/story/lantern_points.bin`), NISAR's 240 km swath sweeps across, the area pours into a Greenland silhouette on an equal-area projection, town lights count up the people beside it (`lantern_people.json`), a veil covers 92 of 100 motes, then the Satilla floods hour by hour from its gauges (`estimator.js`) while NISAR and the official map's satellite pass overhead on the pass strip, down to one pixel (with an echo at the measured power ratio) and one tree whose meter is the measured curve. Data from `scripts/build_lantern.py`, which checks its totals against the atlas.
3. **Beat the satellite** (`game.js`): the reader paints the flood (amber) on the photo; grading plays NISAR's pass as a beam sweeping up the map with the result drawn in behind it, then the river's answer grades them beside NISAR and the official map, on the frozen test's scored ground. The answer key is `data/satilla/047A_oct15/game.png` from `scripts/build_story_charts.py`.
4. **Run it yourself:** the mission console, a doorway to `live.html`: the ready floods on a night world map and a departure board (`data/live/index.json`), the method's steps (`RUN_STEPS`) lighting up in turn, and the floods that aren't ready, with why.
5. **Why NISAR:** one map of the flooded Pearl River forest with a line you drag: Sentinel-1's C-band change on one side, NISAR's L-band on the other, the two waves drawn to scale along the line, and the measured contrasts beside it. "Hear the difference" plays each radar's dry and flooded echoes at those power ratios. Data from `scripts/c_band_check.py`, by the rules in `research/C_BAND_PROTOCOL.md`. The measured Satilla curve and its caveat sit in the fine print. Below it, the ridgeline from Results Fig. 2: the spread of radar brightening at each depth of water.
6. **Watch it move:** the night log, a large Yellow River time-lapse that plays once in view, with the date, trust light and three quiet numbers, and a pass strip under the map (river rise at each gauge since the lowest pass, NISAR's passes, the official map's scenes we compared) that scrubs through the passes. The area chart and river levels sit in its fine print.
7. **Your town** (`where.js`): back to orbit. Three quiet numbers, then a second night globe with the towns as amber lights; search or click a town and the globe turns and closes in, with the 25 km the check covers drawn to scale, and the verdict beside it. And who acts on a blank map. Under the globe, two compact figures: the official map against the gauges on every audited flood (Fig. 8a) and the forested floodplain by latitude (Fig. 9a).
8. **Go deeper:** opens with every frozen test and its 95% interval (Fig. 5a), then the logbook, collapsed: every fair test and what 0.73 means, why GFM had no picture during the crest, the flood-map gap on three Gulf rivers, and what's next.

The orbit rail down the right edge (`orbit.js`) is the page's navigation: one station per part, the journey's seven parts as smaller stations, and a satellite that follows the scroll. On phones it's a line under the top bar plus a Sections menu. Parts fade in as they arrive (skipped under reduced motion). The sound switch in the top bar is off by default.

**Trust light.** Every NISAR map on the site carries one (`trustLight` in `shared.js`). It is the trust signal fixed in `research/OVERBANK_PROTOCOL.md` section 4: green if the map's own contrast check passed and there was no heavy rain (`research/RAINFALL.md`), red otherwise, grey when the method declines to map, and amber on the Run it yourself floods, where rain isn't checked. It was right on 3 of 4 fresh passes, which the protocol calls too few for a verdict, and the site says so.

## Dashboard tour (`dashtour.js`)

A short popup beside each key control of the dashboard, one at a time, with Back and Next: what the map shows, choosing a flood, NISAR's answer, the what-if slider, live or past, map layers and More. It opens by itself on a first visit (remembered in that browser only), from More, and from `dashboard.html?tour=1` (the story page links there). Steps whose control is off screen, such as the side panels on a phone, are skipped. The older full-screen tour (`tour.html`, `tour.js`) is no longer linked.

## Results page (`evidence.html`, `evidence.js`, `figures.js`, `figkit.js`)

Written for readers who want to check the work, as a short paper: an abstract whose numbers are computed from the data, the four limits to know first, Fig. 1–9 and Tables 1–3. The file keeps its old name so existing links work.

- **Figures** (`figures.js`): study design, the radar signature (ridgeline), separability and ROC, maps of three frozen results, every frozen test with its interval, where it works, a flood through time, the official map's blind spot, the worldwide extent, the reference check, NISAR's coverage and the exploratory interferograms. Their data is built by `scripts/build_figures.py`, which checks it against the frozen records before writing (`tests/test_figures.py`). Captions are computed in `evidence.js`.
- **Post-hoc figure data** (descriptive; no frozen number changes; each script first checks it gives back the frozen CSI): `scripts/posthoc_result_maps.py` draws Fig. 4's maps (hits, misses and false alarms on a strong, a typical and a failed pass) from the saved layers; `scripts/posthoc_reference_checks.py` scores each judged version-4 pass with the reference's water surface moved by −1 to +1 m (Fig. 10c), recomputes the intervals with 5 and 10 km blocks, and gives per-pass numbers under trees; `scripts/posthoc_swamp_fringes.py` draws Fig. 12. Table 6 summarises the independent imagery checks in `research/INDEPENDENT_*`.
- **figkit.js** is a small SVG plotting kit in journal style (boxed axes, outward ticks, framed legends, capped error bars). Every figure downloads as SVG, PNG (2x) or the plotted data (CSV), and "Print colours" switches them to a white background for slides and print.
- Four of the figures also appear, in compact form, on the story page, each linking to its full version.

Fuller records stay in `research/`.

## Dashboard page (`dashboard.html`, `dashboard.js`, `estimator.js`)

A tool for using the data directly, live by default. The whole page is one map, with the controls floating around it, and every flood event stays on that map:

- **Moving between events:** choosing an event or its pin flies the camera there. Dragging the map onto a river, or clicking inside one, selects it too. Each river keeps its own NISAR and estimate layers while another is selected.
- **Live now:** current river levels from USGS (`waterservices.usgs.gov`), fetched by the browser every 5 minutes, and the newest scene dates from NASA's catalog (`cmr.earthdata.nasa.gov`). Neither needs a login.
- **Past flood:** Play, the Pass buttons and the arrow keys step from one NISAR pass to the next, so the map and the estimate show the same moment; dragging the time bar moves by the hour. A score shows only when the two match, and a warning appears when they're over a day apart. Rivers that aren't selected show their headline pass.
- **The map shows one thing at a time,** picked with the switch on the map: NISAR's flood map, the gauge-and-lidar estimate, or Both (the estimate in see-through cyan over NISAR's magenta: blue where they agree, magenta where only NISAR mapped flooding, cyan where only the estimate did). One map, so panning never changes what a pixel shows; `&show=nisar` or `&show=estimate` in a link.
- **Left panel:** flood events and five layer switches (roads, gauges, reported floods, the blind-spot map, and what today's flood map leaves out). The card holds the what-if rise; More holds the link, the CSV and the tour. River levels refresh every 5 minutes.
- **Right panel:** a plain summary sentence, dated key numbers, buttons for the gauge table and graphs, a click-a-spot card, the river's record and collapsible detail.
- **Bottom:** time slider, play and jump to a pass, and the map's scale and legend. The gauge table, graphs and About open in a drawer, and About is in the top bar.
- **Map instruments:** a thin strip with the coordinates, scale and color key, plus a labelled coordinate grid.
- **Phones and small windows:** the panels become sheets opened from the bottom row.
- **Accessibility:** status uses shapes and words as well as color, every control works from the keyboard, sliders report their values, moving to a flood is announced to screen readers, and the event list stands in for the map pins. `scripts/` has no automated check for this, so rerun an axe audit after layout changes.
- **Deep links:** `dashboard.html?river=yellow&mode=history&t=2026-10-16T00:36`, with `&show=` for the map's view.

**The estimate runs in the browser.** `estimator.js` follows `hydraulic_truth` in `src/hidden_floods/truth.py`, using per-river packs in `data/dashboard/`. At the end of each build, `scripts/check_estimator.cjs` compares it with the Python result on every recorded pass, and the build stops if any differs by more than 0.5%. This needs Node.

**Roads under water.** `scripts/build_roads.py` (run by the dashboard build) cuts the drivable OpenStreetMap roads saved for each river's blind-spot audit into short pieces, one per estimate pixel crossed, using the frozen audit's rules: footpaths and bridges left out. The dashboard loads them for the river on screen, draws each road with any flooded stretch whole in white and its flooded stretches in orange, (the "Road under water" layer), and the river card adds up their length and how much of it lies inside Copernicus GFM's exclusion mask. On the Satilla's Oct 15 pass it matches the audit's own count to within 0.4% (16.3 km against 16.2 km). Run it yourself does the same with NISAR's own flood map: `scripts/build_live_roads.py` saves each prepared flood's roads from OpenStreetMap (a custom run asks OpenStreetMap from the browser), and `live.js` lays them on the case's 50 m grid; the placement matches an exact projection to the kilometre on all five floods.

Replay uses hourly gauge levels, while research results use 15-minute readings, so a replayed pass can differ slightly from the recorded area (Satilla Oct 19 shows 2,269 ha against 2,266 ha).

**What is and isn't live:** river levels are live. Radar maps are fixed at build time, so they don't update with new NISAR scenes. If USGS can't be reached, the page falls back to a recorded flood and says so.

**Its rivers.** Every US river the project has gauges and lidar for:
- the ten held-out rivers, each built from its one-time frozen run in `outputs/<river>/<pass>/` (kept out of git; copy it over from the project folder that ran the tests), with the score, trust light and rain flag that run recorded;
- the four rivers the method was developed on;
- the St. Johns River, FL, the sealed test's river (`scripts/setup_st_johns.py`): no test yet, and its one NISAR map is Run it yourself's 24 km box around Astor, so the card doesn't compare that area with the river's estimate;
- rivers added by `scripts/auto_rivers.py`, below.

A river's data loads only once it's on screen.

**Adding rivers automatically.** `python scripts/auto_rivers.py` looks at every NOAA gauge in flood and adds the river when every check passes: at least two gauges on the main stem with a height above NAVD88 (a published datum, or one derived from their own readings), at least 8 km of river between them, at least 20% of the floodplain under trees, and a NISAR pass during the flood. It fetches the river's stage records, NWS flood stage, lidar and land cover, runs the frozen method on the radar box around the flooding gauge (with this computer's Earthdata login), lists the river in `sites/auto_rivers.json` and rebuilds the dashboard data; if the build's checks fail, the new rivers are taken out again. `--dry-run` only reports what it would do. Each decision goes to `<data root>/auto_rivers/log.jsonl`. These rivers are labelled "added automatically, not tested": dams and levees aren't checked, and nothing about them is scored.

Build the dashboard data alone with `python scripts/build_dashboard.py`, once `build_app.py` has run.

## Run it anywhere (local only)

```
python scripts/custom_server.py     # http://127.0.0.1:8767/live.html
```

Serves the site plus a local box reader, and the Run it yourself page gains "Or choose any place": draw a box on the map (5–50 km a side; a click drops a 24 km box, or type a latitude and longitude), pick dates, list the NISAR passes whose scene covers the whole box, and choose one. With no box, the panel lists the floods GDACS reported that had a pass of the kind the method reads (from Fig. 11's data), and choosing one searches a 24 km box on its reported point over its reported dates. A browser can't read NISAR's data files itself (NASA's data server refuses cross-site reads, and the files need an Earthdata sign-in), so the server reads just that box with this computer's sign-in (`~/.netrc`, with `hidden_floods.live_v2`'s readers, aligned to the scene's pixel edges), writes the pack to `outputs/custom/`, and the method runs in the browser as on every live case. Custom runs use the global inputs everywhere (FABDEM heights, nearest mapped water), have no gauges and no score, and are uses of the frozen method, not tests. The first run in a new region takes a few minutes (FABDEM tiles); later runs there take seconds. It listens on 127.0.0.1 only and publishes nothing. The page offers the panel only when this server marks it, so a static copy of the site never asks for the reader.

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

- **US:** NOAA gauges at flood stage, with 3DEP lidar, USGS river lines and gauges. Scored once against the
  gauge-and-lidar estimate with the tested rivers' rules.
- **Elsewhere:** GDACS floods, with Copernicus GLO-30 heights. Published unscored.
- The job reads only a 24 km box from each NISAR scene with your Earthdata sign-in (curl and `~/.netrc`); the sign-in never
  reaches the site. Each case's `pack.bin` holds the radar, heights, land cover, gauge timing, permanent water and, for
  scored US cases, the estimate, so `livemethod.js` can rerun the method in the browser with other settings.
- A published case is never rerun or overwritten. Only the frozen run's score counts; the page says that settings chosen
  after seeing a score are tuning.

## Which numbers are which

- **First screen:** frozen v4 on a river it had never seen, built from the one-time run's saved layers (`build_hero` in `scripts/build_app.py`). The build stops if those layers don't reproduce the frozen CSI.
- **Yellow River section and explorer:** these rivers helped build v4, so their scores are development numbers, and the page says so. The build stops if v3 doesn't reproduce its frozen Yellow River CSI, or if v4 differs from its development scores.
- **GFM on the first screen:** Oct 24 is the first GFM scene that covers the stretch, nine days after the NISAR pass (`research/SATILLA_AUDIT.md`). The page labels both dates.

The Satilla GFM layers come from `scripts/audit_satilla.py`, which keeps them in their own `ops_audit` folder. Run it before `build_app.py` on a fresh machine.

**Chart colours** are in `CHART` in `shared.js`. They were checked with a colour-blind palette validator on the dark background, and the cyan sits slightly outside its lightness band to keep it distinct from NISAR's magenta.

**Data encoding:** see the `scripts/build_app.py` docstring. Overlays are Web Mercator PNGs placed with MapLibre image sources. Click info is read from two opaque data PNGs through a canvas.

**Hosting:** the site is `app/` as it stands (about 100 MB with `data/`), and works from a subfolder, as GitHub Pages serves a project site. `.github/workflows/pages.yml` publishes it, but only when started by hand from the Actions tab; it never runs on a push. It also writes the full address of the link-preview card (`og-card.jpg`) into each page. `404.html` and `.nojekyll` are included. Basemap imagery is © Esri, so keep the attribution line in the footer.

**Releasing a change:** bump the `?v=` number on the script and stylesheet tags in every page, so visitors' browsers fetch the new files instead of mixing them with cached old ones.

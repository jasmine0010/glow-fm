# Live cases: protocol v2

**What changes from v1:** one input. Where a box has no lidar, ground height comes from **FABDEM V1-2**, a global elevation model with trees and buildings removed, instead of Copernicus GLO-30, which measures the treetops. Everything else in `LIVE_PROTOCOL.md` stays as written: which floods, which scenes, the box, the method (v4, unchanged), the US inputs and score, and running each case once.

**Receipt:** `research/freeze_receipt_live_v2.json`, with SHA-256 hashes of this file, `src/hidden_floods/live_v2.py`, `scripts/live_cases_v2.py`, the v1 receipt and every file v1 hashed. `scripts/live_cases_v2.py` refuses a frozen run if any of them has changed, or if the v1 receipt no longer verifies. The freeze commit is the dated record.

## Why

The frozen bare-earth test (`BARE_EARTH_RESULTS.md`) ran method v4 unchanged on seven US passes with no lidar in the map. With FABDEM heights its mean CSI was 0.35, against 0.25 with Copernicus GLO-30 and 0.38 with lidar. FABDEM won clearly on four passes and lost on one by 0.01. The cause was the one predicted: Copernicus puts flooded forest a median 4.9 m above the river on the Satilla, so v4's 6 m limit throws much of it out, and FABDEM puts it at 0.4 m. Nothing in that test favoured Copernicus anywhere. Since v4 is unchanged, this is a better input, not a new method.

## Inputs

| Input | US | Elsewhere |
|---|---|---|
| Heights | 3DEP lidar, bare earth (as v1) | **FABDEM V1-2, bare earth** (v1: Copernicus GLO-30) |
| Height above river | As v1 | Height above the nearest mapped water (as v1) |
| Everything else | As v1 | As v1 |

FABDEM tiles are read from the University of Bristol archives (https://doi.org/10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn) by byte ranges, checked against the CRC-32 in each archive's directory, and averaged onto the 50 m grid the same way v1 read Copernicus. Each case records its tiles' SHA-256 hashes, sizes, CRC-32s and archives, and a tile that no longer matches its record stops the run.

## The four v1 world floods

v1 published four floods outside the US (Mexico, India, Thailand, Vietnam), with Copernicus heights. **They stay published exactly as they ran.** Under v2 each gets a twin, `<id>_v2`, built from what v1 published:
- The radar, land cover, water, distance to water and grid are v1's own published arrays, byte for byte. Only the height layer is replaced, by FABDEM heights above the nearest mapped water.
- **Replay check, run before the freeze:** the same code, given v1's heights (Copernicus, rebuilt on the rebuilt grid), must give back each v1 run exactly: the same height on every pixel as stored, the same flagged pixels, cut-off, signal choice and confidence label. It did, on all four (`scripts/live_cases_v2.py --check`). So a twin can differ from v1 only through the height source.
- The site shows the v2 twin by default and keeps v1 one click away, labelled with its heights.
- No FABDEM data over these boxes is decoded before the freeze. The rebuild runs once, logs each attempt in `research/live_v2_attempts.log` before reading FABDEM, and refuses if a twin already exists.

## New floods

New cases run the v1 job (`scripts/live_cases.py`, unchanged) with `hidden_floods.live_v2` in place of `hidden_floods.live`, so they get FABDEM heights outside the US and are marked protocol 2. A flood v1 already published isn't run again.

## Licence

FABDEM is CC BY-NC-SA 4.0. A v2 world pack contains a height layer made from it, so that layer is shared under CC BY-NC-SA 4.0, for non-commercial use, with the citation and attribution below; each case records this. The project's code stays MIT. This replaces, for the live cases only, the bare-earth test's choice not to publish FABDEM-derived layers (`BARE_EARTH_PROTOCOL.md` §2, unchanged as frozen).

Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C. & Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed. *Environmental Research Letters* 17, 024016.

> FABDEM is produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.

## What it isn't

- **Still unvalidated outside the US.** There are no gauges to score these maps, and the bare-earth test covered only US rivers. FABDEM's tree correction is least certain under tall tropical forest, though treetop heights are further off there too.
- **The trust light can change.** It compares low and higher valley forest, and both are defined by height above the water, so better heights can turn it green or red. The v2 result is reported as it comes out.
- A twin isn't evidence that v2 is right on that flood. It shows what the better-tested input changes.

"""Run the bare-earth test once: ``python scripts/run_frozen_bare_earth.py``. Rules are in research/BARE_EARTH_PROTOCOL.md."""

import json

from hidden_floods.frozen_bare_earth import run

result = run()
print(json.dumps(result["readings"], indent=1, default=float), flush=True)
print("BARE EARTH RUN DONE", flush=True)

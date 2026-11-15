"""Run the no-lidar test once: ``python scripts/run_frozen_no_lidar.py``. Rules are in research/NO_LIDAR_PROTOCOL.md."""

from hidden_floods.frozen_no_lidar import run

run()
print("NO LIDAR RUN DONE", flush=True)

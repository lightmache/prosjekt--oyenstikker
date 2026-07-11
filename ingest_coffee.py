import os
import time
import numpy as np
import requests

API_URL = "http://localhost:8000/ingest"
API_KEY = os.getenv("API_KEY", "")

np.random.seed(42)
n_rows = 30
start_ts = int(time.time())
sample_interval_sec = 60

count = 0
for i in range(n_rows):
    ts = start_ts + i * sample_interval_sec
    water_temp_c = round(float(np.random.normal(93.0, 1.2)), 1)
    pressure_bar = round(float(np.random.normal(9.0, 0.4)), 2)
    power_w = round(float(np.random.normal(1400, 60)), 0)
    water_level_pct = round(float(max(0, min(100, 95 - i * 1.8 + np.random.normal(0, 2)))), 1)

    content = (
        f"Coffee machine telemetry reading: brew temperature {water_temp_c}C, "
        f"pump pressure {pressure_bar} bar, power draw {power_w}W, "
        f"water reservoir at {water_level_pct}%, recorded at timestamp {ts}."
    )

    metadata = {
        "type": "coffee_telemetry",
        "source": "google_sheets:coffee_machine",
        "timestamp": ts,
        "water_temp_c": water_temp_c,
        "pressure_bar": pressure_bar,
        "power_w": power_w,
        "water_level_pct": water_level_pct
    }

    r = requests.post(
        API_URL,
        json={"content": content, "metadata": metadata},
        headers={"X-API-Key": API_KEY}
    )
    count += 1
    if count % 10 == 0:
        print(f"ingested {count}/{n_rows}")

print(f"done — {count} records ingested")

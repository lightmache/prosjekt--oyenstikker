import pandas as pd
import requests

API_URL = "http://localhost:8000/ingest"

df = pd.read_csv('/mnt/d/Projects/memory-system/vinton_sample_2024-01-01.csv')

count = 0
for _, row in df.iterrows():
    content = (
        f"Vinton EPA {row['pollutant']} measurement: "
        f"{row['Sample Measurement']} {row['Units of Measure']} "
        f"at {row['site_name']} on {row['Date Local']} {row['Time Local']}. "
        f"Site {row['site_id']} lat {row['latitude']} lon {row['longitude']}."
    )
    metadata = {
        "type": "epa_measurement",
        "pollutant": row['pollutant'],
        "date": row['Date Local'],
        "time": row['Time Local'],
        "value": float(row['Sample Measurement']),
        "unit": row['Units of Measure'],
        "site": row['site_name'],
        "site_id": row['site_id'],
        "source": row['source'],
        "source_url": row['source_url'],
        "license": row['license']
    }
    r = requests.post(API_URL, json={"content": content, "metadata": metadata})
    count += 1
    if count % 10 == 0:
        print(f"ingested {count}/{len(df)}")

print(f"done — {count} records ingested")
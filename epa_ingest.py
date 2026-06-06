import requests
import pandas as pd
import io
import zipfile
import json

TARGET_COUNTIES = [770, 161, 775, 750, 121]
PARAMS = ['88101', 'TEMP', 'WIND', 'RH_DP', 'PRESS']
YEARS = [2024, 2025]
API_URL = "http://localhost:8000/ingest"

for param in PARAMS:
    for year in YEARS:
        print(f"downloading {param} {year}...")
        try:
            url = f"https://aqs.epa.gov/aqsweb/airdata/hourly_{param}_{year}.zip"
            r = requests.get(url, stream=True)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            csv_name = z.namelist()[0]
            df = pd.read_csv(z.open(csv_name), low_memory=False)
            
            # Filter to target counties
            local = df[
                (df['State Code'] == 51) & 
                (df['County Code'].isin(TARGET_COUNTIES))
            ].copy()
            
            if len(local) == 0:
                print(f"  no data in target counties")
                continue
            
            print(f"  {len(local)} rows — ingesting...")
            
            # Ingest each row as a memory
            count = 0
            for _, row in local.iterrows():
                content = (
                    f"{row.get('Parameter Name','unknown')} reading: "
                    f"{row.get('Sample Measurement','?')} "
                    f"{row.get('Units of Measure','?')} "
                    f"at {row.get('County Name','?')} "
                    f"on {row.get('Date Local','?')} "
                    f"{row.get('Time Local','?')}"
                )
                metadata = {
                    "source": "EPA_AQS",
                    "parameter": param,
                    "year": year,
                    "county": str(row.get('County Code','')),
                    "site": str(row.get('Site Num','')),
                    "date": str(row.get('Date Local','')),
                    "time": str(row.get('Time Local','')),
                    "value": str(row.get('Sample Measurement',''))
                }
                requests.post(API_URL, json={
                    "content": content,
                    "metadata": metadata
                })
                count += 1
                if count % 100 == 0:
                    print(f"  ingested {count}/{len(local)}")
            
            print(f"  done — {count} records ingested")
            
        except Exception as e:
            print(f"  failed: {e}")
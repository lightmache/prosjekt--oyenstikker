import pandas as pd
import os
import requests

metadata_dir = "OSD-412_metadata_OSD-412-ISA"
assay_file = os.path.join(metadata_dir, "a_OSD-412_amplicon-sequencing_16s_illumina.txt")

def run_ingestion():
    df = pd.read_csv(assay_file, sep='\t')
    df.columns = [c.replace('Parameter Value[', '').replace(']', '').replace(' ', '_') for c in df.columns]
    
    for _, row in df.iterrows():
        raw_files = str(row.get('Raw_Data_File', '')).split(',')
        payload = {
            "sample_name": row['Sample_Name'],
            "read_depth": int(row.get('Read_Depth')) if pd.notnull(row.get('Read_Depth')) else 0,
            "sequencing_instrument": row.get('Sequencing_Instrument', 'N/A'),
            "raw_files": raw_files,
            "metadata": {
                "primer_info": row.get('Primer_Info', 'N/A'),
                "library_strategy": row.get('library_strategy', 'N/A'),
                "read_length": row.get('Read_Length', 'N/A')
            }
        }
        
        response = requests.post("http://localhost:8000/ingest", json=payload)
        print(f"Ingested: {payload['sample_name']} - Status: {response.status_code}")

if __name__ == "__main__":
    run_ingestion()

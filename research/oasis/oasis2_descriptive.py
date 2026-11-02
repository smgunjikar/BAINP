"""Exploratory aggregate ONLY for an authorized OASIS-2 demographics CSV.
No diagnosis training, no output of individual identifiers.
Usage: python research/oasis/oasis2_descriptive.py --input data/raw/oasis2/oasis_longitudinal_demographics.csv
Dependencies: pandas (research extras).
"""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);args=p.parse_args()
if not args.input.is_file():raise SystemExit('Input CSV not found')
import pandas as pd
df=pd.read_csv(args.input)
report={'source':'authorized local OASIS-2 CSV; aggregated only', 'rows':int(len(df)),'columns':df.columns.tolist()}
if 'Subject ID' in df.columns:report['unique_subjects']=int(df['Subject ID'].nunique())
for col in ['Age','MMSE','eTIV','nWBV','ASF']:
 if col in df:
  v=pd.to_numeric(df[col],errors='coerce')
  report[col]={'n_available':int(v.notna().sum()),'mean':round(float(v.mean()),4) if v.notna().any() else None,
               'sd':round(float(v.std()),4) if v.notna().sum()>1 else None}
# No individual-level information printed or saved.
print(json.dumps(report,indent=2))

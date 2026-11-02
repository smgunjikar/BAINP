# ADNI research integration: Phase 1 (local only)

## Step 1: Obtain approved tables yourself through LONI IDA

Choose ADNI in the IDA study selector. Go to Search & Download -> Study Files (sometimes Download -> Study Data). Obtain the variable dictionary, enrollment and visit tables, diagnosis summary, demographic tables, cognitive scores, and MRI QC / numeric summaries. Table names/availability vary by ADNI phase and date. Do not send passwords or raw human-subject data to ChatGPT.

See `../../docs/ADNI_ACQUISITION_AND_QC.md` for acquisition priorities and scientific safeguards.

## Step 2: Place files locally

Create `data/raw/adni/clinical/` beneath the repository and store your downloaded tabular files or ZIP archives there. The entire `/data/` subtree is ignored by Git other than template folders.

## Step 3: Run aggregate-only inventory

```powershell
python research/adni/inventory.py --source data/raw/adni/clinical
python research/adni/inventory.py --source data/raw/adni/clinical --output data/derived/adni/inventory.json
python -m pytest research/adni/tests -q
```

The inventory reports filenames, recognized linkage-column names, aggregate scan counts and aggregate distinct RID/PTID counts. It never prints or saves raw participant identifiers, dates or measurement values. Inspect its output before sharing even aggregate figures externally; the data-use agreement controls disclosure.

## Step 4: Proceed to scientific joins only after reviewing actual tables and dictionary

Do not equate a visit label with a date, do not merge research cohorts by name, do not use outcome-defining fields as predictors, and split on the person identifier across all ADNI phases. Keep post-baseline outcomes out of baseline feature sets.

## Limitations

- This is **not** an automatic ADNI downloader or a clinical analytics pipeline.
- Large tabular downloads can be slow to scan. Use `--max-rows 10000` for a partial inventory; it labels partial results.
- ZIP handling only reads tabular `.csv`/`.tsv` members; imaging remains untouched.

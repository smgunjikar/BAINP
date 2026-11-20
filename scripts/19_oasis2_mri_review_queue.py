"""Build an outcome-blind MRI review queue; never change the source QC tracker.

Standard library only. Queue files are snapshots, not new authoritative trackers.
"""
import argparse,csv,hashlib,io,json
from collections import Counter,defaultdict
from pathlib import Path

def require(ok,msg):
    if not ok: raise ValueError(msg)

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f); fields=r.fieldnames; rows=list(r)
    require(bool(rows),'Empty input: '+str(path))
    return fields,rows

def encode(fields,rows):
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    return s.getvalue().encode('utf-8-sig')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=Path.home()/'BAINP_DATA')
    ap.add_argument('--cohort-dir',type=Path);ap.add_argument('--qc-tracker',type=Path);ap.add_argument('--output-dir',type=Path)
    a=ap.parse_args();root=a.data_root.resolve();base=root/'derived/oasis2'
    cohort=a.cohort_dir or base/'clinical_cohort_v1';tracker=a.qc_tracker or base/'header_audit/acquisition_qc_tracking.csv'
    out=a.output_dir or base/'mri_review_queue_v1'
    require(not out.exists(),'Output already exists. Use a new --output-dir for a refreshed snapshot.')
    plan=json.loads((cohort/'analysis_plan.json').read_text(encoding='utf-8-sig'))
    # Only provenance, IDs and timing are read. No prediction errors or outcomes determine priority.
    metadata=cohort/'pair_metadata.csv'
    require(hashlib.sha256(metadata.read_bytes()).hexdigest()==plan['output_sha256']['pair_metadata.csv'],'Pair metadata checksum mismatch')
    _,pairs=read(metadata);fields,qc=read(tracker)
    require(len(pairs)==plan['primary_participants'],'Cohort size differs')
    require(len({r['subject'] for r in pairs})==len(pairs),'Duplicate participant')
    require(len({r['relative_path'].replace('\\','/') for r in qc})==len(qc),'Duplicate acquisition path')
    for f in ['session','filename','relative_path','visual_qc_status','orientation_status']:
        require(f in fields,'Missing tracker field: '+f)
    by_session=defaultdict(list)
    for row in qc:by_session[row['session']].append(row)
    sessions=[];acquisitions=[]
    for order,pair in enumerate(sorted(pairs,key=lambda r:r['earlier_session']),1):
        sid=pair['earlier_session'];subject=pair['subject']
        require(sid.rsplit('_',1)[0]==subject,'Participant/session mismatch')
        rows=sorted(by_session.get(sid,[]),key=lambda r:r['relative_path'])
        sheet_rel=f'derived/oasis2/visual_review/all_v2/{sid}_review.png'
        sessions.append({'review_order':order,'subject':subject,'session':sid,'acquisitions_in_tracker':len(rows),
            'visual_status_counts':json.dumps(dict(Counter(r['visual_qc_status'] for r in rows)),sort_keys=True),
            'orientation_status_counts':json.dumps(dict(Counter(r['orientation_status'] for r in rows)),sort_keys=True),
            'preliminary_notes':' | '.join(sorted({r.get('preliminary_montage_note','') for r in rows if r.get('preliminary_montage_note','')})),
            'review_sheet_relative_path':sheet_rel,'review_sheet_exists_locally':(root/sheet_rel).is_file(),
            'queue_status':'REVIEW_REQUIRED' if rows else 'MISSING_FROM_TRACKER'})
        for row in rows:
            rel=row['relative_path'].replace('\\','/'); path=(root/rel).resolve()
            require(path.is_relative_to(root),'Tracker path escapes data root')
            acquisitions.append({'review_order':order,'subject':subject,**row})
    require(len({s['session'] for s in sessions})==len(sessions),'Repeated earlier session')
    flags={sid:{'in_primary_earlier_visit_queue':any(s['session']==sid for s in sessions),'acquisitions_in_tracker':len(by_session.get(sid,[]))} for sid in ['OAS2_0099_MR1','OAS2_0061_MR3']}
    summary={'status':'REVIEW_QUEUE_ONLY_NO_MRI_APPROVAL','participants':len(pairs),'earlier_sessions':len(sessions),
      'acquisitions_in_queue':len(acquisitions),'sessions_missing_from_tracker':[s['session'] for s in sessions if not s['acquisitions_in_tracker']],
      'review_sheets_found_locally':sum(s['review_sheet_exists_locally'] for s in sessions),
      'visual_status_counts':dict(Counter(r['visual_qc_status'] for r in acquisitions)),
      'orientation_status_counts':dict(Counter(r['orientation_status'] for r in acquisitions)),
      'previously_flagged_sessions':flags,'ordering':'Earlier-session ID, independent of clinical outcomes and model errors.',
      'tracker_sha256':hashlib.sha256(tracker.read_bytes()).hexdigest(),'pair_metadata_sha256':hashlib.sha256(metadata.read_bytes()).hexdigest(),
      'source_tracker_modified':False,'images_approved':False,'registration_performed':False,
      'notes':['Queue preserves source status text verbatim; it does not decide eligibility.','Use the original acquisition_qc_tracking.csv for documented review decisions.','Inspect full volumes when montages are inconclusive. Anatomical orientation needs independent verification.','Previously flagged sessions remain unresolved unless documented review establishes otherwise.','Follow-up MRI is not included as a baseline predictor.','Any later MRI exclusions require reporting and matched clinical comparisons on the retained cohort.']}
    readme='''MRI review queue — Step 19

1. Review sessions in session_review_queue.csv order. This order uses IDs, not prediction errors.
2. Open each existing all_v2 montage using its relative path under BAINP_DATA.
3. Inspect individual full volumes when the montage is ambiguous. Record uncertainty rather than approval when unsure.
4. Document motion/ghosting, blurring, intensity variation, coverage and other visible artifacts per acquisition. These observations alone are not diagnoses or proof of anatomical orientation.
5. Record reviewer, date, observations and decisions in the ORIGINAL header_audit/acquisition_qc_tracking.csv. The queue is a snapshot only; do not edit it as a replacement tracker.
6. Keep orientation unverified until an appropriate independent check is documented. Header labels alone are insufficient.
7. No automatic scan selection, rejection, averaging, registration or MRI feature extraction is performed here.

Start with the first five listed sessions; return their review notes and any ambiguous full-volume views. A qualified imaging reviewer should resolve uncertain quality/orientation decisions before MRI modeling. Do not select scans based on clinical labels or model prediction errors.
'''
    out.mkdir(parents=True)
    (out/'session_review_queue.csv').write_bytes(encode(list(sessions[0]),sessions))
    (out/'acquisition_review_queue.csv').write_bytes(encode(['review_order','subject']+fields,acquisitions))
    (out/'mri_queue_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (out/'REVIEW_INSTRUCTIONS.txt').write_text(readme,encoding='utf-8')
    print('MRI REVIEW QUEUE SUMMARY');print(json.dumps(summary,indent=2));print('Output:',out)
if __name__=='__main__':main()

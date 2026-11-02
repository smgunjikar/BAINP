"""Research-only participant-held-out baseline for prepared PADS-like feature tables.

Expected CSV columns: participant_id, recorded_group, numerical feature columns.
Run only on feature tables prepared according to the original dataset's legal terms.
The code never claims presymptomatic diagnosis or patient-level risk prediction.

Example: python scripts/motor_grouped_baseline.py my_features.csv
Requires: pandas, scikit-learn, numpy (optional research dependencies).
"""
import sys
import json

def main():
    if len(sys.argv)!=2:
        print(__doc__); return 2
    import pandas as pd
    import numpy as np
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.metrics import balanced_accuracy_score,classification_report,confusion_matrix
    df=pd.read_csv(sys.argv[1]); required={'participant_id','recorded_group'}
    if not required.issubset(df.columns):
        raise ValueError('Missing required columns: '+str(required-set(df.columns)))
    if df['participant_id'].isna().any() or df['recorded_group'].isna().any():
        raise ValueError('Participant or group labels missing')
    nlabels=df.groupby('participant_id')['recorded_group'].nunique()
    if (nlabels>1).any():
        raise ValueError('Contradictory groups within participant: check data linkage')
    numeric=list(df.drop(columns=['participant_id','recorded_group']).select_dtypes(include='number').columns)
    if not numeric:raise ValueError('No numeric feature columns to train on')
    splitter=GroupShuffleSplit(n_splits=1,test_size=.2,random_state=2026)
    train_idx,test_idx=next(splitter.split(df[numeric],df['recorded_group'],groups=df['participant_id']))
    tr,te=df.iloc[train_idx],df.iloc[test_idx]
    if set(tr.participant_id)&set(te.participant_id):
        raise RuntimeError('Leakage: participant in both train and test')
    if len(set(tr.recorded_group))<2:raise ValueError('Train split has only one class; adjust cohorts')
    model=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(max_iter=2000,class_weight='balanced'))
    model.fit(tr[numeric],tr.recorded_group)
    pred=model.predict(te[numeric])
    print(json.dumps({'research_only':True,'train_participants':tr.participant_id.nunique(),
       'test_participants':te.participant_id.nunique(), 'train_rows':len(tr),'test_rows':len(te),
       'features':numeric,'balanced_accuracy_in_this_heldout_sample':round(float(balanced_accuracy_score(te.recorded_group,pred)),4),
       'warning':'This is recorded-group discrimination in an observational dataset. NOT prodromal neurological screening or a deployed clinical classifier.'},indent=2))
    print(classification_report(te.recorded_group,pred,zero_division=0))
    print('Confusion matrix (rows=actual, cols=predicted):')
    print(confusion_matrix(te.recorded_group,pred,labels=model.classes_))
    return 0
if __name__=='__main__':raise SystemExit(main())

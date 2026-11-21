"""Audit frozen predictions and produce descriptive error analysis; no retraining."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

def require(ok,msg):
    if not ok: raise ValueError(msg)

def metrics(d,p):
    e=d[p]-d.later_mmse
    return {'n':len(d),'MAE':float(e.abs().mean()),'RMSE':float(np.sqrt((e**2).mean())),'mean_prediction_minus_observed':float(e.mean())}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=Path.home()/'BAINP_DATA')
    ap.add_argument('--benchmark-dir',type=Path); ap.add_argument('--cohort-dir',type=Path); ap.add_argument('--output-dir',type=Path)
    a=ap.parse_args(); base=a.data_root/'derived/oasis2'
    b=a.benchmark_dir or base/'clinical_benchmark_v1'; c=a.cohort_dir or base/'clinical_cohort_v1'; o=a.output_dir or base/'clinical_error_analysis_v1'
    require(not o.exists(),'Output exists; choose a new --output-dir.')
    summary=json.loads((b/'benchmark_summary.json').read_text()); plan=json.loads((c/'analysis_plan.json').read_text())
    require(hashlib.sha256((c/'analysis_plan.json').read_bytes()).hexdigest()==summary['analysis_plan_sha256'],'Analysis-plan hash mismatch')
    for n,h in plan['output_sha256'].items():
        require(Path(n).name==n,'Invalid filename')
        require(hashlib.sha256((c/n).read_bytes()).hexdigest()==h,'Cohort hash mismatch: '+n)
    d=pd.read_csv(b/'out_of_fold_predictions.csv').set_index('subject').sort_index()
    require(d.index.is_unique and not d.index.hasnans and len(d)==summary['participants'],'Invalid OOF IDs')
    tables={n:pd.read_csv(c/(n+'.csv')).set_index('subject') for n in ['clinical_features','clinical_targets','participant_folds','pair_metadata']}
    for t in tables.values(): require(t.index.is_unique and set(t.index)==set(d.index),'Cohort IDs differ')
    require(np.isfinite(d.to_numpy(float)).all(),'Nonfinite OOF values')
    require(np.array_equal(d.outer_fold,tables['participant_folds'].loc[d.index,'outer_fold']),'Fold mismatch')
    require(np.array_equal(d.later_mmse,tables['clinical_targets'].loc[d.index,'later_mmse']),'Outcome mismatch')
    require(np.array_equal(d.persistence_prediction,tables['clinical_features'].loc[d.index,'earlier_mmse']),'Persistence mismatch')
    for name in ['ridge','persistence']:
        m=metrics(d,name+'_prediction')
        for k in ['MAE','RMSE']: require(np.isclose(m[k],summary[name][k],atol=1e-10,rtol=0),'Metric mismatch')
    audit=json.loads((b/'inner_fold_audit.json').read_text()); require(len(audit)==25,'Expected 25 inner folds')
    keys=set()
    for row in audit:
        k,j=row['outer_fold'],row['inner_fold']; require((k,j) not in keys,'Duplicate inner fold'); keys.add((k,j))
        tr=set(row['train_subjects']); va=set(row['validation_subjects']); outer=set(d.index[d.outer_fold!=k])
        require(len(tr)==len(row['train_subjects']) and len(va)==len(row['validation_subjects']),'Duplicate inner IDs')
        require(not tr&va and tr|va==outer,'Inner leakage or incomplete split')
    require(keys=={(k,j) for k in range(1,6) for j in range(1,6)},'Incorrect inner fold keys')
    for k in range(1,6):
        ids=[s for r in audit if r['outer_fold']==k for s in r['validation_subjects']]
        require(len(ids)==len(set(ids))==sum(d.outer_fold!=k),'Inner validation coverage error')
    d=d.join(tables['clinical_features']).join(tables['pair_metadata'])
    d['observed_change']=d.later_mmse-d.earlier_mmse
    d['ridge_absolute_error']=(d.ridge_prediction-d.later_mmse).abs()
    d['persistence_absolute_error']=(d.persistence_prediction-d.later_mmse).abs()
    d['ridge_minus_persistence_absolute_error']=d.ridge_absolute_error-d.persistence_absolute_error
    d['ridge_clipped_sensitivity']=d.ridge_prediction.clip(0,30)
    d['observed_change_group']=np.where(d.observed_change<0,'decreased',np.where(d.observed_change>0,'increased','unchanged'))
    d['earlier_mmse_group']=np.where(d.earlier_mmse<24,'below_24',np.where(d.earlier_mmse<28,'24_to_27','28_to_30'))
    d['interval_group']=np.where(d.interval_days<730.5,'under_24_months','24_months_or_more')
    grouped=[]
    for col in ['outer_fold','earlier_cdr','earlier_mmse_group','observed_change_group','interval_group']:
        for label,part in d.groupby(col):
            for model in ['ridge','persistence']:
                grouped.append({'grouping':col,'group':str(label),'model':model,**metrics(part,model+'_prediction')})
    diff=d.ridge_minus_persistence_absolute_error
    outside=d[(d.ridge_prediction<0)|(d.ridge_prediction>30)]
    require(len(outside)==summary['ridge_predictions_outside_0_30'],'Out-of-range count mismatch')
    result={'status':'POST_HOC_DESCRIPTIVE_ONLY','participants':len(d),'all_integrity_checks_passed':True,
        'ridge_better_absolute_error':int((diff < -1e-10).sum()),'ridge_worse_absolute_error':int((diff>1e-10).sum()),'ties':int((diff.abs()<=1e-10).sum()),
        'ridge':metrics(d,'ridge_prediction'),'persistence':metrics(d,'persistence_prediction'),
        'clipped_ridge_sensitivity':metrics(d,'ridge_clipped_sensitivity'),
        'outside_range_n':len(outside),'prediction_min':float(d.ridge_prediction.min()),'prediction_max':float(d.ridge_prediction.max()),
        'notes':['Subgroup boundaries were chosen after viewing aggregate performance; no confirmatory inference.','Observed-change groups use outcomes and are descriptive, never baseline predictors.','Clipping is a post-hoc sensitivity analysis, not a replacement primary result.','Do not remove high-error participants solely to improve metrics.','No retraining; MRI QC remains unresolved.'],
        'input_sha256':{n:hashlib.sha256((b/n).read_bytes()).hexdigest() for n in ['benchmark_summary.json','inner_fold_audit.json','out_of_fold_predictions.csv']}}
    o.mkdir(parents=True)
    d.to_csv(o/'participant_errors.csv'); outside.to_csv(o/'out_of_range_predictions.csv')
    d.sort_values('ridge_absolute_error',ascending=False).head(10).to_csv(o/'largest_ridge_errors.csv')
    pd.DataFrame(grouped).to_csv(o/'descriptive_subgroup_metrics.csv',index=False)
    (o/'error_analysis_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('ERROR ANALYSIS SUMMARY'); print(json.dumps(result,indent=2)); print('Output:',o)
if __name__=='__main__': main()

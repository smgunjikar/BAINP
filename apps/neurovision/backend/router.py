"""Authenticated NeuroVision package API. No arbitrary filesystem path input.
Research cohorts are not linked to live participants by name or URL parameters.
"""
import hashlib,json,os,re
from pathlib import Path
from datetime import date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from nv_queue import storage_root
_DEMO_ASSETS=Path(__file__).resolve().parents[1]/'demo_assets'

def make_router(authenticated):
 r=APIRouter(prefix='/api/neurovision',dependencies=[Depends(authenticated)])
 def catalog(mode,principal):
  p=storage_root(principal,mode)/'catalog.json'
  entries=json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
  filtered=[x for x in entries if bool(x.get('synthetic'))==(mode=='demo')]
  # A bundled read-only phantom makes demo usable without importing a real MRI.
  if mode=='demo' and not filtered:
   filtered=json.loads((_DEMO_ASSETS/'catalog.json').read_text(encoding='utf-8'))
  return filtered
 def package(identifier,mode,principal):
  if not re.fullmatch('[0-9a-f]{24}',identifier):raise HTTPException(404,'scan_not_found')
  entry=next((x for x in catalog(mode,principal) if x['id']==identifier),None)
  if entry is None:raise HTTPException(404,'scan_not_found')
  p=storage_root(principal,mode)/(identifier+'.json')
  if mode=='demo' and not p.is_file() and any(x['id']==identifier for x in json.loads((_DEMO_ASSETS/'catalog.json').read_text(encoding='utf-8'))):
   p=_DEMO_ASSETS/(identifier+'.json')
  if not p.is_file():raise HTTPException(409,'prepared_package_missing')
  data=p.read_bytes()
  if hashlib.sha256(data).hexdigest()!=entry['package_sha256']:raise HTTPException(409,'prepared_package_hash_mismatch')
  return json.loads(data)
 @r.get('/scans')
 def scans(mode:Literal['active','demo'],principal=Depends(authenticated)):return {'items':catalog(mode,principal),'boundary':'Account-isolated imaging in active mode; synthetic-only research demonstration in demo mode. Never inferred as the selected participant MRI.'}
 @r.get('/scans/{identifier}')
 def get(identifier:str,mode:Literal['active','demo'],principal=Depends(authenticated)):return package(identifier,mode,principal)
 @r.get('/compare')
 def compare(baseline:str,followup:str,mode:Literal['active','demo'],principal=Depends(authenticated)):
  a=package(baseline,mode,principal)['metadata'];b=package(followup,mode,principal)['metadata'];reasons=[]
  if baseline==followup:reasons.append('SAME_ACQUISITION')
  for k in ['cohort','subject','protocol','pipeline']:
   if a.get(k)!=b.get(k):reasons.append(k.upper()+'_DIFFERS')
  if a.get('visit')==b.get('visit'):reasons.append('REPEATED_ACQUISITION_NOT_LONGITUDINAL_VISIT')
  days=None
  try:
   days=(date.fromisoformat(b['date'])-date.fromisoformat(a['date'])).days
   if days<=0:reasons.append('VISIT_DATES_NOT_ORDERED')
  except (KeyError,TypeError,ValueError):reasons.append('VERIFIED_VISIT_DATES_MISSING')
  if mode=='active':
   if any(x.get('review')!='APPROVED' for x in [a,b]):reasons.append('REVIEW_NOT_APPROVED')
   if any(x.get('longitudinal_comparable') is not True for x in [a,b]):reasons.append('ACQUISITION_COMPARABILITY_NOT_ESTABLISHED')
   if any(x.get('quality_flags') for x in [a,b]):reasons.append('QUALITY_FLAGS_REQUIRE_REVIEW')
  changes=[]
  if not reasons:
   prior={m['id']:m for m in a['measurements']}
   for m in b['measurements']:
    old=prior.get(m['id'])
    if old and old['name']==m['name'] and old['volume_ml']>0:changes.append({'name':m['name'],'baseline_ml':old['volume_ml'],'followup_ml':m['volume_ml'],'difference_ml':m['volume_ml']-old['volume_ml'],'percent_difference':100*(m['volume_ml']/old['volume_ml']-1)})
  return {'state':'INSUFFICIENT_OR_INCOMPARABLE' if reasons else ('SYNTHETIC_DEMONSTRATION' if mode=='demo' else 'DESCRIPTIVE_DIFFERENCE_ONLY'),'reasons':reasons,'interval_days':days,'changes':changes,'interpretation':'No atrophy diagnosis, reliable-change threshold or disease forecast is established.'}
 return r

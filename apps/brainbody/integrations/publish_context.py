"""Publish explicitly authorized same-person BBC-BE records. No identity inference.
JSON: [{"id":"UUID","payload":{...BBC-BE Record contract...}},...].
The backend still checks scopes, units, assays, identity links and source revisions.
"""
import argparse,getpass,json
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import Request,build_opener,HTTPCookieProcessor
from urllib.error import HTTPError
from uuid import UUID

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--participant',type=UUID,required=True);p.add_argument('--mode',choices=['active','demo'],required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--same-person-verified',action='store_true');a=p.parse_args()
    if not a.same_person_verified:raise ValueError('Independently verify source identity before publishing')
    items=json.loads(a.input.read_text(encoding='utf-8-sig'))
    if not isinstance(items,list) or not 1<=len(items)<=1000:raise ValueError('A bounded JSON list of 1–1000 records is required')
    ids=[str(UUID(r['id'])) for r in items]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate record IDs in request')
    client=build_opener(HTTPCookieProcessor(CookieJar()));base='http://127.0.0.1:3000/api'
    def call(path,method,body=None):
        req=Request(base+path,data=json.dumps(body,allow_nan=False).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json','X-NeuroAccess-Request':'1'})
        try:
            with client.open(req,timeout=30) as response:return json.load(response)
        except HTTPError as e:raise RuntimeError('API rejected request ('+str(e.code)+'): '+e.read().decode()) from None
    call('/login','POST',{'password':getpass.getpass('Local operator login code: ')})
    consent=call('/brainbody/participants/'+str(a.participant)+'/consent?mode='+a.mode,'GET')
    if not consent['scopes']:raise ValueError('Record scope authorization in the BBC-BE interface first; this script does not grant it')
    saved=0
    for rid,item in zip(ids,items):
        payload=item['payload'];payload['identity_verified']=True
        call('/brainbody/participants/'+str(a.participant)+'/records/'+rid+'?mode='+a.mode,'PUT',payload);saved+=1
        print('Accepted',saved,'of',len(items),'records')
    print('Done. Identical retries with the same IDs/revisions are idempotent; source data were not altered.')
if __name__=='__main__':main()

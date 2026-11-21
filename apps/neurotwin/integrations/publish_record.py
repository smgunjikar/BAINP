"""Publish an authorized source record using the existing local operator session.
Not a live EEG/device collector. Run only after verifying identity and consent.
"""
import argparse,getpass,json
from http.cookiejar import CookieJar
from urllib.request import build_opener,HTTPCookieProcessor,Request
from pathlib import Path
from uuid import UUID

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--participant',type=UUID,required=True);p.add_argument('--mode',choices=['active','demo'],required=True)
    p.add_argument('--record',type=Path,required=True);p.add_argument('--type',choices=['neural','clinical','anatomy'],required=True)
    p.add_argument('--identity-and-consent-verified',action='store_true');a=p.parse_args()
    if not a.identity_and_consent_verified:raise ValueError('Verify same-person identity and authorization before publishing')
    payload=json.loads(a.record.read_text(encoding='utf-8-sig'));payload['identity_verified']=True;payload['consent_confirmed']=True
    client=build_opener(HTTPCookieProcessor(CookieJar()));base='http://127.0.0.1:3000/api'
    def put(path,body,method):
        r=Request(base+path,data=json.dumps(body,allow_nan=False).encode(),headers={'Content-Type':'application/json','X-NeuroAccess-Request':'1'},method=method)
        with client.open(r,timeout=30) as response:return json.load(response)
    put('/login',{'password':getpass.getpass('Local operator code: ')},'POST')
    result=put('/neurotwin/participants/'+str(a.participant)+({'neural':'/neural-records','clinical':'/source-records','anatomy':'/anatomical-records'}[a.type])+'?mode='+a.mode,payload,'PUT')
    print(result)
if __name__=='__main__':main()

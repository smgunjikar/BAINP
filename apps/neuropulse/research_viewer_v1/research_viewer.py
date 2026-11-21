"""Local, read-only research viewer for BAINP NeuroPulse Main V1.1 outputs.

No clinical interpretation, no patient identity linkage, no raw EEG serving.
Requires Python 3.11+, standard library only.
"""
import argparse
import csv
import json
import math
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

EXPECTED = {'subject','status','windows_total','windows_retained','windows_excluded','sha256','clinical_qc_approved','delta_uv2','theta_uv2','alpha_uv2','beta_uv2','error'}
ALLOWED_STATES = {'DESCRIPTIVE_AVAILABLE','INSUFFICIENT_WINDOWS','FAILED'}

def load_results(run_dir):
    path = Path(run_dir).resolve()
    summary_path, csv_path = path/'run_summary.json', path/'features.csv'
    if not summary_path.is_file() or not csv_path.is_file():
        raise ValueError('Required run_summary.json and features.csv not found')
    summary = json.loads(summary_path.read_text(encoding='utf-8-sig'))
    if summary.get('clinical_qc_approved') is not False or summary.get('research_only') is not True:
        raise ValueError('Research-only and unapproved indicators are required')
    records = summary.get('results')
    if not isinstance(records, list):
        raise ValueError('Missing results list')
    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not EXPECTED.issubset(set(reader.fieldnames or [])):
            raise ValueError('Feature matrix schema mismatch')
        rows = list(reader)
    if len(rows) != len(records) or len(rows) != int(summary.get('selected', -1)):
        raise ValueError('Summary-feature matrix cardinality mismatch')
    known = {r.get('subject'):r for r in records}
    if len(known) != len(records):
        raise ValueError('Duplicate or absent subject identifiers in summary')
    out = []
    for row in rows:
        subject = row['subject']
        if subject not in known or not subject.startswith('sub-') or not subject[4:].isdigit():
            raise ValueError('Unexpected subject identifier')
        status = row['status']
        if status != known[subject].get('status') or status not in ALLOWED_STATES:
            raise ValueError('Status mismatch')
        if row.get('clinical_qc_approved','').lower() != 'false':
            raise ValueError('Unexpected clinical QC approval')
        clean = {key:row.get(key,'') for key in EXPECTED}
        for col in ('windows_total','windows_retained','windows_excluded'):
            clean[col] = int(clean[col])
        if clean['windows_total'] != clean['windows_retained']+clean['windows_excluded']:
            raise ValueError('Window counts mismatch')
        for col in ('delta_uv2','theta_uv2','alpha_uv2','beta_uv2'):
            if clean[col] == '':
                clean[col] = None
            else:
                val = float(clean[col])
                if not math.isfinite(val) or val < 0:
                    raise ValueError('Invalid spectral value')
                clean[col] = val
        clean['clinical_qc_approved'] = False
        clean['sha256'] = clean['sha256'][:64]
        out.append(clean)
    return {'schema':'neuropulse_research_viewer_v1','research_only':True,'clinical_qc_approved':False,
            'source_run':path.name,'selected':len(out),'results':out}

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BAINP · NeuroPulse Research</title><style>
:root{color-scheme:dark;font-family:system-ui,Segoe UI,Arial,sans-serif;background:#0b1220;color:#e7eef8}body{margin:0}header{padding:23px 5%;border-bottom:1px solid #29364b;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}h1{font-size:25px;margin:0}main{max-width:1200px;margin:20px auto;padding:0 20px}.muted{color:#aebed1}.warn{border:1px solid #896d36;background:#2a261c;padding:14px;border-radius:10px;margin-bottom:18px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}.card,.panel{background:#141f30;border:1px solid #2c3b52;border-radius:12px;padding:17px}.value{font-size:28px;font-weight:700}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}input,select{background:#1b2a40;color:white;border:1px solid #405371;border-radius:8px;padding:10px;font-size:14px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:11px 8px;border-bottom:1px solid #2c3b52;text-align:left}th{color:#aebed1}tr:hover{background:#203148}button{background:#315f9d;color:white;border:0;border-radius:7px;padding:7px 10px;cursor:pointer}.scroll{overflow-x:auto}.badge{font-size:12px;padding:4px 7px;border-radius:5px;background:#35475d}.small{font-size:13px}#detail{margin:15px 0}a{color:#87bafa}
</style></head><body><header><div><h1>NeuroPulse X · Research Workspace</h1><div class="muted small">BAINP 3.0 · Versioned descriptive EEG features</div></div><div class="muted small" id="run">Local-only · Read-only</div></header><main>
<div class="warn"><b>Research only · No clinical clearance</b><div class="small">Features are not disease biomarkers or diagnoses. The processing threshold and retained windows have not been clinically qualified. Dataset participants are not linked to BAINP patient identities.</div></div>
<div class="cards" id="cards"></div><div class="toolbar"><input id="search" placeholder="Find subject (e.g. sub-001)" aria-label="Search subjects"><select id="status" aria-label="Filter status"><option value="">All statuses</option><option>DESCRIPTIVE_AVAILABLE</option><option>INSUFFICIENT_WINDOWS</option><option>FAILED</option></select></div>
<div class="panel"><div class="scroll"><table><thead><tr><th>Subject</th><th>Status</th><th>Retained / total</th><th>Delta µV²</th><th>Theta µV²</th><th>Alpha µV²</th><th>Beta µV²</th><th>Details</th></tr></thead><tbody id="rows"></tbody></table></div></div><section id="detail" class="panel" hidden></section>
<p class="muted small">These bands are descriptive and depend on channel reference, preprocessing, units and retained windows. Missing features stay missing; no clinical interpretation is provided.</p></main><script>
'use strict';let dataset=null;
const el=id=>document.getElementById(id);const make=(tag,txt)=>{const e=document.createElement(tag);e.textContent=String(txt);return e};
const fmt=x=>x===null||x===undefined?'—':Number(x).toFixed(2);
function card(label,value){let c=document.createElement('div');c.className='card';let n=make('div',value);n.className='value';c.append(n,make('div',label));el('cards').append(c)}
function render(){const q=el('search').value.trim().toLowerCase(),st=el('status').value;const body=el('rows');body.replaceChildren();for(const r of dataset.results.filter(r=>r.subject.toLowerCase().includes(q)&&(!st||r.status===st))){const tr=document.createElement('tr');for(const txt of [r.subject,r.status,r.windows_retained+' / '+r.windows_total,fmt(r.delta_uv2),fmt(r.theta_uv2),fmt(r.alpha_uv2),fmt(r.beta_uv2)])tr.append(make('td',txt));const td=document.createElement('td'),b=make('button','View');b.onclick=()=>detail(r);td.append(b);tr.append(td);body.append(tr)}}
function detail(r){const d=el('detail');d.replaceChildren();d.hidden=false;d.append(make('h2',r.subject),make('p','Status: '+r.status),make('p','Retained '+r.windows_retained+' of '+r.windows_total+' windows; excluded '+r.windows_excluded),make('p','SHA-256 (recorded provenance): '+r.sha256),make('p','Clinical QC approved: No'),make('p','Processing error: '+(r.error||'None reported')));d.scrollIntoView({behavior:'smooth',block:'nearest'})}
fetch('/api/results',{cache:'no-store'}).then(x=>{if(!x.ok)throw Error('Unable to read results');return x.json()}).then(data=>{dataset=data;el('run').textContent='Source run: '+data.source_run;card('Recordings',data.selected);for(const s of ['DESCRIPTIVE_AVAILABLE','INSUFFICIENT_WINDOWS','FAILED'])card(s.replaceAll('_',' ').toLowerCase(),data.results.filter(r=>r.status===s).length);render()}).catch(err=>{el('run').textContent='Error: '+err.message});el('search').oninput=()=>dataset&&render();el('status').onchange=()=>dataset&&render();
</script></body></html>'''

class Handler(BaseHTTPRequestHandler):
    payload = None
    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/':
            body,ctype=HTML.encode('utf-8'),'text/html; charset=utf-8'
        elif url.path == '/api/results':
            body,ctype=json.dumps(self.payload,allow_nan=False).encode('utf-8'),'application/json; charset=utf-8'
        else:
            self.send_error(404);return
        self.send_response(200)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.send_header('Referrer-Policy','no-referrer')
        self.end_headers();self.wfile.write(body)
    def do_POST(self):
        self.send_error(405,'Read-only research workspace')
    def log_message(self,*args):
        pass

def main():
    parser=argparse.ArgumentParser(description='Read-only BAINP NeuroPulse research dashboard')
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8766)
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('port must be 1024..65535')
    Handler.payload=load_results(args.run_dir)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'NeuroPulse local research viewer: http://127.0.0.1:{args.port}/',flush=True)
    print(f'Recordings: {Handler.payload["selected"]}. Ctrl+C to stop.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__':main()

"""Serve the static accessible UI on loopback:3000 and proxy /api to loopback:8000.

Using one browser origin avoids CORS and keeps the operator cookie HttpOnly.
Only the three application assets are exposed; there is no directory listing.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]/'web'
API_PORT=8000
ASSETS={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/i18n.js':('i18n.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/cognition':('cognition.html','text/html; charset=utf-8'),'/cognition.js':('cognition.js','text/javascript; charset=utf-8'),'/cognition-results':('cognition.html','text/html; charset=utf-8'),'/results.js':('results.js','text/javascript; charset=utf-8'),'/extended.js':('extended.js','text/javascript; charset=utf-8'),'/cognition-dashboard':('cognition.html','text/html; charset=utf-8'),'/battery.css':('battery.css','text/css; charset=utf-8')}
ASSETS['/account-ui.js']=('account-ui.js','text/javascript; charset=utf-8')
ASSETS.update({'/neurosense':('neurosense.html','text/html; charset=utf-8'),'/neurosense.js':('neurosense.js','text/javascript; charset=utf-8')})
ASSETS.update({'/sense-monitor':('sense-monitor.html','text/html; charset=utf-8'),'/sense-monitor.js':('sense-monitor.js','text/javascript; charset=utf-8')})
ASSETS.update({'/sense-monitor':('../../neurosense/frontend/dashboard.html','text/html; charset=utf-8'),'/sense-monitor.js':('../../neurosense/frontend/dashboard.js','text/javascript; charset=utf-8'),'/sense-dashboard.css':('../../neurosense/frontend/dashboard.css','text/css; charset=utf-8')})
ASSETS.update({'/neurovision':('../../neurovision/frontend/index.html','text/html; charset=utf-8'),'/neurovision.js':('../../neurovision/frontend/app.js','text/javascript; charset=utf-8'),'/neurovision.css':('../../neurovision/frontend/style.css','text/css; charset=utf-8')})
ASSETS.update({'/neurovision':('../../neurovision/frontend/index.html','text/html; charset=utf-8'),'/neurovision.js':('../../neurovision/frontend/app.js','text/javascript; charset=utf-8'),'/neurovision.css':('../../neurovision/frontend/style.css','text/css; charset=utf-8'),'/neurovision-volume.js':('../../neurovision/frontend/volume.js','text/javascript; charset=utf-8')})
ASSETS.update({'/neurovision-analysis.js':('../../neurovision/frontend/analysis-ui.js','text/javascript; charset=utf-8')})
ASSETS.update({'/neurovision-phase2b.js':('../../neurovision/frontend/phase2b-ui.js','text/javascript; charset=utf-8')})
ASSETS.update({'/neurovision-phase2c.js':('../../neurovision/frontend/phase2c-ui.js','text/javascript; charset=utf-8'),'/neurotwin-phase2c.js':('../../neurotwin/frontend/phase2c-twin.js','text/javascript; charset=utf-8')})
ASSETS.update({'/neurotwin-research-preview.js':('../../neurotwin/frontend/research-preview.js','text/javascript; charset=utf-8')})
ASSETS.update({'/neurotwin':('../../neurotwin/frontend/index.html','text/html; charset=utf-8'),'/neurotwin.js':('../../neurotwin/frontend/app.js','text/javascript; charset=utf-8'),'/neurotwin.css':('../../neurotwin/frontend/style.css','text/css; charset=utf-8')})
ASSETS.update({'/neurotwin':('../../neurotwin/frontend/index.html','text/html; charset=utf-8'),'/neurotwin.js':('../../neurotwin/frontend/app.js','text/javascript; charset=utf-8'),'/neurotwin.css':('../../neurotwin/frontend/style.css','text/css; charset=utf-8'),'/neurotwin-brain.js':('../../neurotwin/frontend/brain.js','text/javascript; charset=utf-8'),'/neurotwin-volume.js':('../../neurotwin/frontend/volume.js','text/javascript; charset=utf-8')})
ASSETS.update({'/brain-body':('../../brainbody/frontend/index.html','text/html; charset=utf-8'),'/brainbody.js':('../../brainbody/frontend/app.js','text/javascript; charset=utf-8'),'/brainbody.css':('../../brainbody/frontend/style.css','text/css; charset=utf-8')})
ASSETS.update({'/brainbody-return.js':('../../brainbody/frontend/return.js','text/javascript; charset=utf-8')})
ASSETS.update({
    '/neurograph': ('../../neurograph/frontend/index.html', 'text/html; charset=utf-8'),
    '/neuroguard': ('../../neurograph/frontend/index.html', 'text/html; charset=utf-8'),
    '/neuro-evidence.js': ('../../neurograph/frontend/app.js', 'text/javascript; charset=utf-8'),
    '/neuro-evidence.css': ('../../neurograph/frontend/style.css', 'text/css; charset=utf-8'),
})
ASSETS.update({
    '/neurosim': ('../../neurosim/frontend/index.html', 'text/html; charset=utf-8'),
    '/careloop': ('../../careloop/frontend/index.html', 'text/html; charset=utf-8'),
    '/careloop-v2.js': ('../../careloop/frontend/app.js', 'text/javascript; charset=utf-8'),
    '/careloop-v2.css': ('../../careloop/frontend/style.css', 'text/css; charset=utf-8'),
    '/prevention.js': ('../../neurosim/frontend/app.js', 'text/javascript; charset=utf-8'),
    '/prevention.css': ('../../neurosim/frontend/style.css', 'text/css; charset=utf-8'),
})
ASSETS.update({
    '/arena': ('../../neurosignal-arena/frontend/index.html', 'text/html; charset=utf-8'),
    '/platform-core': ('../../neurosignal-arena/frontend/index.html', 'text/html; charset=utf-8'),
    '/arena-platform.js': ('../../neurosignal-arena/frontend/app.js', 'text/javascript; charset=utf-8'),
    '/arena-platform.css': ('../../neurosignal-arena/frontend/style.css', 'text/css; charset=utf-8'),
})
ASSETS.update({
    '/neuropulse': ('../../neuropulse/frontend/index.html', 'text/html; charset=utf-8'),
    '/neuropulse.js': ('../../neuropulse/frontend/app.js', 'text/javascript; charset=utf-8'),
    '/neuropulse.css': ('../../neuropulse/frontend/style.css', 'text/css; charset=utf-8'),
    '/neuropulse-demo.json': ('../../neuropulse/frontend/demo.json', 'application/json'),
    '/neuropulse-research-example.json': ('../../neuropulse/frontend/research-example.json', 'application/json'),
    '/neuropulse-benchmark.json': ('../../neuropulse/frontend/benchmark.json', 'application/json'),
})
# neurocontinuum_native_assets_v1
ASSETS.update({
    '/neurocontinuum': ('../../neurocontinuum/frontend/index.html', 'text/html; charset=utf-8'),
    '/neurocontinuum.js': ('../../neurocontinuum/frontend/app.js', 'text/javascript; charset=utf-8'),
    '/neurocontinuum.css': ('../../neurocontinuum/frontend/style.css', 'text/css; charset=utf-8'),
})
# neuroquest_native_assets_v1
ASSETS.update({
 '/neuroquest': ('../../neuroquest/frontend/index.html','text/html; charset=utf-8'),
 '/neuroquest.js': ('../../neuroquest/frontend/app.js','text/javascript; charset=utf-8'),
 '/neuroquest.css': ('../../neuroquest/frontend/style.css','text/css; charset=utf-8'),
})
# neuroshadow_native_assets_v1
ASSETS.update({
 '/neuroshadow': ('../../neuroshadow/frontend/index.html','text/html; charset=utf-8'),
 '/neuroshadow.js': ('../../neuroshadow/frontend/app.js','text/javascript; charset=utf-8'),
 '/neuroshadow-collector.js': ('../../neuroshadow/frontend/collector.js','text/javascript; charset=utf-8'),
 '/neuroshadow.css': ('../../neuroshadow/frontend/style.css','text/css; charset=utf-8'),
})
# mimic_proof_native_v1
ASSETS.update({'/neuromimic': ('../../neuromimic/frontend/index.html', 'text/html; charset=utf-8'), '/neuromimic.js': ('../../neuromimic/frontend/app.js', 'text/javascript; charset=utf-8'), '/neuromimic.css': ('../../neuromimic/frontend/style.css', 'text/css; charset=utf-8')})
ASSETS.update({'/neuroproof': ('../../neuroproof/frontend/index.html', 'text/html; charset=utf-8'), '/neuroproof.js': ('../../neuroproof/frontend/app.js', 'text/javascript; charset=utf-8'), '/neuroproof.css': ('../../neuroproof/frontend/style.css', 'text/css; charset=utf-8')})

ASSETS['/neuropulse-research.js']=('../../neuropulse/frontend/research-integration.js','text/javascript; charset=utf-8')

ASSETS.update({'/shared-navigation.js':('shared-navigation.js','text/javascript; charset=utf-8'),'/shared-workspace.css':('shared-workspace.css','text/css; charset=utf-8')})

ASSETS.update({'/neurocognition':('../../neurocognition/frontend/workspace.html','text/html; charset=utf-8'),'/nc-workspace.js':('../../neurocognition/frontend/workspace.js','text/javascript; charset=utf-8')})
# NeuroCognition-owned assets; existing URLs remain compatible.
for _route, _asset, _type in [
 ('/cognition','cognition.html','text/html; charset=utf-8'),
 ('/cognition-results','cognition.html','text/html; charset=utf-8'),
 ('/cognition-dashboard','cognition.html','text/html; charset=utf-8'),
 ('/cognition.js','cognition.js','text/javascript; charset=utf-8'),
 ('/extended.js','extended.js','text/javascript; charset=utf-8'),
 ('/results.js','results.js','text/javascript; charset=utf-8'),
 ('/battery.css','battery.css','text/css; charset=utf-8')]:
 ASSETS[_route]=('../../neurocognition/frontend/'+_asset,_type)

ASSETS.update({
 '/nc-camera.js':('../../neurocognition/frontend/camera.js','text/javascript; charset=utf-8'),
 '/nc-connected.css':('../../neurocognition/frontend/connected.css','text/css; charset=utf-8'),
})
for _asset,_type in [('vision_bundle.mjs','text/javascript; charset=utf-8'),('vision_wasm_internal.js','text/javascript; charset=utf-8'),('vision_wasm_internal.wasm','application/wasm'),('vision_wasm_nosimd_internal.js','text/javascript; charset=utf-8'),('vision_wasm_nosimd_internal.wasm','application/wasm'),('face_landmarker.task','application/octet-stream')]:
 ASSETS['/nc-vendor/'+_asset]=('../../neurocognition/frontend/vendor/'+_asset,_type)

ASSETS.update({'/bainp-research':('../../bainp_research_expansion/frontend/index.html','text/html; charset=utf-8'),'/bainp-research.js':('../../bainp_research_expansion/frontend/app.js','text/javascript; charset=utf-8'),'/bainp-research.css':('../../bainp_research_expansion/frontend/style.css','text/css; charset=utf-8')})

ASSETS['/neuropulse-x.css']=('../../neuropulse/frontend/neuro-pulse-x.css','text/css; charset=utf-8')







# neurotwin_neuropulse_research_link_v1: protected research explorer assets only
ASSETS.update({
    '/neurotwin-pulse-link-v1.js': ('../../neurotwin/frontend/neurotwin_pulse_link_v1.js','text/javascript; charset=utf-8'),
    '/neurotwin-pulse-link-v1.css': ('../../neurotwin/frontend/neurotwin_pulse_link_v1.css','text/css; charset=utf-8'),
})

ASSETS['/bainp-dashboard-v1.css']=('bainp-dashboard-v1.css','text/css; charset=utf-8')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass  # Avoid participant IDs in routine access logs.
    def do_GET(self):self.handle_request()
    def do_POST(self):self.handle_request()
    def do_PATCH(self):self.handle_request()
    def do_PUT(self):self.handle_request()
    def do_DELETE(self):self.handle_request()
    def headers_safe(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self' 'wasm-unsafe-eval'; media-src 'self' blob:; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    def handle_request(self):
        path=urlsplit(self.path).path
        if path.startswith('/api/'):
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:self.send_error(400);return
            import re
            # User MRI, aligned mask and discrete labels have the same per-file
            # server limit. All other API requests keep the small default.
            imaging_put=(self.command=='PUT' and bool(re.fullmatch(
                r'/api/neurovision/import-jobs/[0-9a-f]{32}/(?:image|aux/(?:mask|labels))',path)))
            upload_limit=64*1024*1024 if imaging_put else 2_000_000
            if length<0 or length>upload_limit:
                # Do not interpret a rejected, unconsumed large POST/PUT body as
                # a reusable connection. Return JSON so the browser can report 413.
                data=b'{"detail":"request_exceeds_proxy_limit"}'
                self.send_response(413);self.headers_safe()
                self.send_header('Connection','close')
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
                self.close_connection=True
                return
            connection=HTTPConnection('127.0.0.1',API_PORT,timeout=180 if imaging_put else 20)
            try:
                headers={k:self.headers[k] for k in ['Cookie','Content-Type','X-NeuroAccess-Request','Origin'] if k in self.headers}
                # Research key forwarded ONLY to the protected NeuroPulse API.
                if path.startswith('/api/neuropulse/intelligence/v3/') and 'X-BAINP-Research-Key' in self.headers:
                    headers['X-BAINP-Research-Key'] = self.headers['X-BAINP-Research-Key']
                headers['Content-Length']=str(length)
                if imaging_put:
                    # Stream rather than buffering a 64-MiB image twice in RAM.
                    connection.putrequest(self.command,self.path)
                    for key,value in headers.items():connection.putheader(key,value)
                    connection.endheaders()
                    remaining=length
                    while remaining:
                        chunk=self.rfile.read(min(262144,remaining))
                        if not chunk:raise ConnectionError('client_upload_disconnected')
                        connection.send(chunk)
                        remaining-=len(chunk)
                else:
                    body=self.rfile.read(length) if length else None
                    connection.request(self.command,self.path,body=body,headers=headers)
                response=connection.getresponse();data=response.read()
                self.send_response(response.status);self.headers_safe()
                for key,value in response.getheaders():
                    if key.lower() in ('content-type','set-cookie'):self.send_header(key,value)
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (OSError,HTTPException,ConnectionError):
                # Transport failures should be explicit, not an unexplained
                # JavaScript TypeError or a half-open browser connection.
                data=b'{"detail":"imaging_proxy_transport_error; inspect local API and frontend logs"}'
                try:
                    self.send_response(503);self.headers_safe()
                    self.send_header('Content-Type','application/json')
                    self.send_header('Connection','close')
                    self.send_header('Content-Length',str(len(data)))
                    self.end_headers();self.wfile.write(data)
                except OSError:pass
                self.close_connection=True
            finally:connection.close()
            return
        if self.command=='GET' and path in ('/active','/results','/setup','/intake','/encoding','/assessment','/demo','/sessions'):
            self.send_response(303);self.headers_safe();self.send_header('Location','/?mode='+('demo' if path=='/demo' else 'active'));self.send_header('Content-Length','0');self.end_headers();return
        if self.command!='GET' or path not in ASSETS:self.send_error(404);return
        name,mime=ASSETS[path];data=(ROOT/name).read_bytes()
        if mime.startswith('text/html'):
            data=data.replace(b'</head>',b'<link rel="stylesheet" href="/shared-workspace.css"><script src="/shared-navigation.js" defer></script></head>')
        self.send_response(200);self.headers_safe();self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=3000);parser.add_argument('--api-port',type=int,default=8000);args=parser.parse_args()
    API_PORT=args.api_port
    print(f'NeuroAccess frontend: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer((__import__('os').environ.get('BAINP_FRONTEND_HOST','127.0.0.1'),args.port),Handler).serve_forever()

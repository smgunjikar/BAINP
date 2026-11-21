"""Local-only NeuroVision research demonstration server. Python 3.11+, numpy, Pillow.
No BAINP database modification, no network calls outside loopback.
"""
from __future__ import annotations
import argparse
import json
import secrets
import hmac
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from volume import synthetic_volume, load_local_mri, slice_image, meta_for

HERE=Path(__file__).resolve().parent
MIME={'/':'text/html; charset=utf-8','/ui.css':'text/css; charset=utf-8','/ui.js':'text/javascript; charset=utf-8'}
ASSET={'/':'index.html','/ui.css':'ui.css','/ui.js':'ui.js'}


def make_handler(volumes, access_token):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'NeuroVisionLocal/0.1'
        def log_message(self, fmt, *args):
            # No query strings or patient identifiers in logs.
            print('[NeuroVisionDemo] '+fmt.replace('%s','{}').format(*[str(v).split('?')[0] for v in args]))
        def respond(self,code:int,body:bytes,mime:str):
            self.send_response(code)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
        def do_POST(self):
            self.respond(405,b'{"error":"read-only demonstration"}','application/json')
        def do_GET(self):
            url=urlsplit(self.path)
            if url.path in ASSET:
                p=HERE/ASSET[url.path]
                self.respond(200,p.read_bytes(),MIME[url.path]);return
            if url.path not in ('/api/meta','/api/slice'):
                self.respond(404,b'{"error":"not found"}','application/json');return
            try:
                query=parse_qs(url.query,keep_blank_values=False)
                provided_token = self.headers.get('Authorization', '')
                if not hmac.compare_digest(provided_token, 'Bearer ' + access_token):
                    self.respond(403,b'{"error":"invalid local access token"}','application/json');return
                visit=int(query.get('visit',['1'])[0]);
                if visit not in volumes: raise ValueError('Unknown visit')
                volume=volumes[visit]
                if url.path=='/api/meta':
                    payload={'current':meta_for(volume),'visits':[{'id':int(k),'label':v.descriptor['visit']} for k,v in volumes.items()]}
                    self.respond(200,json.dumps(payload).encode(),'application/json');return
                plane=query.get('plane',['axial'])[0]
                xyz=tuple(int(query.get(n,[str(volume.intensity.shape[i]//2)])[0]) for i,n in enumerate(['x','y','z']))
                if any(not 0<=v<lim for v,lim in zip(xyz, volume.intensity.shape)):
                    raise ValueError('Crosshair out of range')
                indices={'axial':xyz[2],'coronal':xyz[1],'sagittal':xyz[0]}
                if plane not in indices:raise ValueError('Invalid plane')
                opacity=float(query.get('opacity',['0.43'])[0]);label=int(query.get('label',['0'])[0])
                if not (0<=opacity<=1 and 0<=label<=65535):raise ValueError('Invalid overlay params')
                img=slice_image(volume,plane,indices[plane],xyz,opacity,label)
                self.respond(200,img,'image/png')
            except (ValueError,KeyError,TypeError) as e:
                self.respond(400,json.dumps({'error':str(e)}).encode(),'application/json')
            except Exception:
                # Do not disclose filesystem paths to browser.
                self.respond(500,b'{"error":"local processing error"}','application/json')
    return Handler


def main(argv=None):
    ap=argparse.ArgumentParser(description='Local research MRI viewer. No participant record writes.')
    ap.add_argument('--image',help='Optional local authorized NIfTI/.img/MGZ; requires nibabel')
    ap.add_argument('--segmentation',help='Optional local label image on exactly same MRI grid')
    ap.add_argument('--port',type=int,default=8765)
    args=ap.parse_args(argv)
    if args.segmentation and not args.image:ap.error('--segmentation requires --image')
    if not 1024<=args.port<=65535: ap.error('Port out of range')
    volumes={1:load_local_mri(args.image,args.segmentation)} if args.image else {1:synthetic_volume(1),2:synthetic_volume(2)}
    token=secrets.token_urlsafe(24)
    site=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(volumes,token))
    print('NeuroVision local RESEARCH DEMO (not clinical; no participant database writes)')
    print(f'Open only this private local link: http://127.0.0.1:{args.port}/#token={token}')
    try:site.serve_forever()
    except KeyboardInterrupt:pass
    finally:site.server_close()

if __name__=='__main__':main()

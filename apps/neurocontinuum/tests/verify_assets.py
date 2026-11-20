"""Exercise the real host allowlist and injected asset URLs over loopback HTTP."""
from pathlib import Path
import sys, threading, re
from urllib.request import urlopen
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'neuroaccess/backend'))
import serve_frontend
server=ThreadingHTTPServer(('127.0.0.1',0),serve_frontend.Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_port)
try:
 for page in ['/neurocontinuum','/neurocontinuum?experience=participant']:
  with urlopen(base+page) as r:
   assert r.status==200;html=r.read().decode()
  assets=re.findall(r'(?:src|href)="(/[^"#]+)"',html)
  for asset in assets:
   with urlopen(base+asset) as r:
    assert r.status==200 and len(r.read())>0,asset
  print('PASS',page,'and',len(assets),'host-registered assets')
finally:
 server.shutdown();thread.join();server.server_close()

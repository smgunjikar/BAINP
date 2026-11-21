"""Local multi-account boundary. No email/SMS verification or public hosting claim."""
import argparse,contextvars,getpass,hashlib,hmac,json,os,re,secrets,sqlite3,threading,time
from pathlib import Path
from contextlib import contextmanager
from uuid import uuid4
from fastapi import HTTPException,Request,Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field

DATABASE=contextvars.ContextVar('bainp_account_database',default=None)
PRINCIPAL=contextvars.ContextVar('bainp_account_principal',default=None)
HASH_LOCK=threading.BoundedSemaphore(2)
COOKIE='bainp_session'
PUBLIC={'/api/health','/api/login','/api/auth/register','/api/auth/recover','/api/auth/status'}
DB_PREFIXES=('/api/participants','/api/checkins','/api/ncx','/api/neurosense','/api/brainbody','/api/neurocontinuum/v1','/api/neuroquest/v1','/api/neuroshadow/v1','/api/neuromimic/v1','/api/neuroproof/v1','/api/prevention','/api/neuro-evidence')

def db_path(fallback):return DATABASE.get() or fallback

def require_identity():
    p=PRINCIPAL.get()
    if not p:raise HTTPException(401,'Sign in to continue.')
    return p

def password_hash(password):
    if not 15<=len(password)<=128:raise HTTPException(422,'Use a password of 15–128 characters.')
    salt=secrets.token_bytes(16)
    with HASH_LOCK:key=hashlib.scrypt(password.encode(),salt=salt,n=131072,r=8,p=1,maxmem=268435456)
    return 'scrypt$'+salt.hex()+'$'+key.hex()

def password_ok(password,encoded):
    try:
        if len(password)>128:return False
        kind,salt,key=encoded.split('$')
        if kind!='scrypt':return False
        with HASH_LOCK:actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=131072,r=8,p=1,maxmem=268435456)
        return hmac.compare_digest(actual.hex(),key)
    except (ValueError,TypeError):return False

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def normalize(value):
    value=value.strip().lower()
    if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise HTTPException(422,'Enter an email address.')
    return value

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Login(Strict):
    email:str=Field(max_length=254)
    password:str=Field(max_length=128)
class Register(Login):
    name:str=Field(min_length=1,max_length=80)
class Change(Strict):
    current_password:str=Field(max_length=128)
    new_password:str=Field(min_length=15,max_length=128)
class Recover(Strict):
    code:str=Field(min_length=20,max_length=200)
    new_password:str=Field(min_length=15,max_length=128)
class AdminAction(Strict):
    action:str
    password:str=Field(max_length=128)
    reason:str=Field(min_length=8,max_length=300)
class Enter(Strict):
    target:str=Field(max_length=50)
    reason:str=Field(min_length=8,max_length=300)
    password:str=Field(max_length=128)

class Accounts:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'accounts.sqlite3';self.lock=threading.RLock()
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('user','admin')),status TEXT NOT NULL CHECK(status IN ('pending','active','disabled','deleted')),created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),created REAL NOT NULL,seen REAL NOT NULL,expires REAL NOT NULL,target TEXT,reason TEXT);
            CREATE TABLE IF NOT EXISTS recovery(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,start REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,stamp REAL NOT NULL,actor TEXT,action TEXT NOT NULL,target TEXT,detail TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'append_only_audit'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'append_only_audit'); END;
            ''')
        try:self.path.chmod(0o600)
        except OSError:pass
        self.dummy=password_hash(secrets.token_urlsafe(24))
        self.schema=None
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA journal_mode=WAL')
        try:yield c;c.commit()
        except Exception:c.rollback();raise
        finally:c.close()
    def audit(self,actor,action,target='',detail=''):
        with self.connect() as c:c.execute('INSERT INTO audit(stamp,actor,action,target,detail) VALUES(?,?,?,?,?)',(time.time(),actor,action,target,detail[:1000]))
    def rate(self,key,maximum=10,period=900):
        now=time.time();blocked=False
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM limits WHERE start<?',(now-86400,))
            row=c.execute('SELECT * FROM limits WHERE key=?',(key,)).fetchone()
            if not row or now-row['start']>period:c.execute('INSERT OR REPLACE INTO limits VALUES(?,?,?)',(key,1,now))
            elif row['count']>=maximum:blocked=True
            else:c.execute('UPDATE limits SET count=count+1 WHERE key=?',(key,))
        if blocked:raise HTTPException(429,'Too many attempts. Try again later.')
    def lookup(self,request):
        token=digest(request.cookies.get(COOKIE,''));now=time.time()
        with self.connect() as c:
            row=c.execute('SELECT s.*,u.email,u.name,u.role,u.status FROM sessions s JOIN users u ON s.user_id=u.id WHERE token=?',(token,)).fetchone()
            if not row or row['status']!='active' or row['expires']<=now or row['seen']<now-1800:
                c.execute('DELETE FROM sessions WHERE token=?',(token,));return None
            if row['target'] not in (None,'legacy'):
                target=c.execute('SELECT status FROM users WHERE id=?',(row['target'],)).fetchone()
                if not target or target['status']!='active':
                    c.execute('DELETE FROM sessions WHERE token=?',(token,));return None
            c.execute('UPDATE sessions SET seen=? WHERE token=?',(now,token))
            return dict(row)
    def admin(self,request,password=None):
        p=require_identity()
        if p['role']!='admin':raise HTTPException(403,'Administrator access required.')
        if password is not None:self.reauthenticate(p,password)
        return p
    def reauthenticate(self,p,password):
        self.rate('reauth:'+p['user_id'])
        with self.connect() as c:row=c.execute('SELECT password FROM users WHERE id=?',(p['user_id'],)).fetchone()
        if not row or not password_ok(password,row['password']):raise HTTPException(403,'Password confirmation failed.')
    def workspace(self,p):
        target=p['target'] or p['user_id']
        if target=='legacy':
            if p['role']!='admin':raise HTTPException(403,'Administrator access required.')
            return self.legacy
        if target!=p['user_id'] and p['role']!='admin':raise HTTPException(403,'Workspace access denied.')
        if not re.fullmatch(r'[0-9a-f-]{36}',target):raise HTTPException(403,'Invalid workspace.')
        folder=self.root/'workspaces'/target;folder.mkdir(parents=True,exist_ok=True)
        path=folder/'records.sqlite3'
        with self.lock:
            with sqlite3.connect(path) as c:
                c.executescript(self.schema)
                c.execute('PRAGMA user_version=5')
        return path
    def mount(self,app,store):
        self.legacy=store.path
        with store.connect() as c:
            rows=c.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END").fetchall()
        self.schema=';\n'.join(r[0].replace('CREATE TABLE ','CREATE TABLE IF NOT EXISTS ',1).replace('CREATE UNIQUE INDEX ','CREATE UNIQUE INDEX IF NOT EXISTS ',1).replace('CREATE INDEX ','CREATE INDEX IF NOT EXISTS ',1) for r in rows)+';'
        # The schema snapshot contains definitions only, never legacy participant rows.
        @app.middleware('http')
        async def account_boundary(request,call_next):
            pt=dt=None;p=None;response=None
            try:
                if request.url.hostname not in ('localhost','127.0.0.1','::1'):raise HTTPException(400,'Host not allowed.')
                if request.method not in ('GET','HEAD','OPTIONS'):
                    try:size=int(request.headers.get('content-length','0'))
                    except ValueError:raise HTTPException(400,'Invalid request length.')
                    if request.url.path.startswith(('/api/auth/','/api/admin/')) or request.url.path=='/api/login':
                        if size>16384:raise HTTPException(413,'Account request too large.')
                    if request.headers.get('x-neuroaccess-request')!='1':raise HTTPException(403,'Request header required.')
                    if request.headers.get('sec-fetch-site')=='cross-site':raise HTTPException(403,'Cross-site request denied.')
                path=request.url.path
                if path.startswith('/api/') and path not in PUBLIC:
                    p=self.lookup(request)
                    if not p:raise HTTPException(401,'Sign in to continue.')
                    pt=PRINCIPAL.set(p)
                    if path.startswith('/api/admin/') and p['role']!='admin':raise HTTPException(403,'Administrator access required.')
                    safe=path in ('/api/session','/api/logout','/api/owner-profile') or path.startswith(('/api/auth/','/api/admin/','/api/owner-profile/')) or any(path==prefix or path.startswith(prefix+'/') for prefix in DB_PREFIXES)
                    if not safe and not (p['role']=='admin' and p['target']=='legacy'):raise HTTPException(403,'This research tool is available only in the administrator test workspace.')
                    if p['role']!='admin' and request.query_params.get('mode','active')!='active':raise HTTPException(403,'Demo records are administrator-only.')
                    dt=DATABASE.set(self.workspace(p))
                    if p['target']:
                        self.audit(p['user_id'],'workspace_request_started',p['target'],request.method+' '+path)
                    if p['role']!='admin' and request.method=='POST' and path=='/api/participants':
                        body=await request.json()
                        if body.get('mode')!='active':raise HTTPException(403,'Only an active personal profile is allowed.')
                        with store.connect() as c:
                            rows=c.execute('SELECT id FROM participants').fetchall()
                        if rows and not any(r['id']==body.get('id') for r in rows):raise HTTPException(409,'Your account already has a profile. Edit it instead.')
                response=await call_next(request)
                if p and p['target']:self.audit(p['user_id'],'workspace_request_finished',p['target'],request.method+' '+request.url.path+' '+str(response.status_code))
                return response
            except HTTPException as e:return JSONResponse({'detail':e.detail},status_code=e.status_code,headers={'Cache-Control':'no-store'})
            finally:
                if dt is not None:DATABASE.reset(dt)
                if pt is not None:PRINCIPAL.reset(pt)
        @app.get('/api/auth/status')
        def auth_status():return {'email_verified':False,'delivery_configured':False,'registration':'admin_approval','phone_login':False}
        @app.post('/api/login')
        def login(payload:Login,request:Request,response:Response):
            host=request.client.host if request.client else 'local';email=normalize(payload.email)
            self.rate('login-ip:'+host,50);self.rate('login-email:'+digest(email),10)
            with self.connect() as c:row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            valid=password_ok(payload.password,row['password'] if row else self.dummy)
            if not row or not valid or row['status']!='active':
                self.audit(None,'login_rejected',digest(email));raise HTTPException(401,'Sign-in failed. Check your credentials and account approval.')
            token=secrets.token_urlsafe(32);now=time.time()
            with self.connect() as c:
                c.execute('DELETE FROM sessions WHERE expires<?',(now,))
                c.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)',(digest(token),row['id'],now,now,now+8*3600,None,None))
                c.execute('DELETE FROM limits WHERE key=?',('login-email:'+digest(email),))
            response.set_cookie(COOKIE,token,max_age=8*3600,httponly=True,samesite='strict',secure=False,path='/api')
            self.audit(row['id'],'login_success')
            return {'authenticated':True,'role':row['role']}
        @app.post('/api/auth/register',status_code=202)
        def register(payload:Register,request:Request):
            self.rate('register:'+(request.client.host if request.client else 'local'),5,3600)
            email=normalize(payload.email);hashed=password_hash(payload.password)
            with self.connect() as c:
                identifier=str(uuid4())
                c.execute('INSERT OR IGNORE INTO users VALUES(?,?,?,?,?,?,?)',(identifier,email,payload.name.strip(),hashed,'user','pending',time.time()))
            self.audit(None,'registration_requested',digest(email))
            return {'message':'If eligible, your request is awaiting administrator approval. Your email address has not been verified.'}
        @app.get('/api/session')
        def session():
            p=require_identity()
            return {'authenticated':True,'role':p['role'],'user_id':p['user_id'],'email':p['email'],'name':p['name'],'email_verified':False,'workspace':p['target'] or p['user_id'],'review_reason':p['reason'],'storage':'local_account_database'}
        @app.post('/api/logout')
        def logout(request:Request,response:Response):
            p=require_identity()
            with self.connect() as c:c.execute('DELETE FROM sessions WHERE token=?',(p['token'],))
            response.delete_cookie(COOKIE,path='/api');self.audit(p['user_id'],'logout')
            return {'logged_out':True}
        @app.post('/api/auth/password')
        def change_password(payload:Change):
            p=require_identity();self.reauthenticate(p,payload.current_password);hashed=password_hash(payload.new_password)
            with self.connect() as c:
                c.execute('UPDATE users SET password=? WHERE id=?',(hashed,p['user_id']))
                c.execute('DELETE FROM sessions WHERE user_id=?',(p['user_id'],))
                c.execute('DELETE FROM recovery WHERE user_id=?',(p['user_id'],))
            self.audit(p['user_id'],'password_changed');return {'message':'Password changed. Sign in again.'}
        @app.get('/api/auth/sessions')
        def sessions():
            p=require_identity()
            with self.connect() as c:rows=c.execute('SELECT created,seen,expires FROM sessions WHERE user_id=? AND expires>? ORDER BY created DESC',(p['user_id'],time.time())).fetchall()
            return {'items':[dict(r) for r in rows]}
        @app.post('/api/auth/logout-all')
        def logout_all():
            p=require_identity()
            with self.connect() as c:c.execute('DELETE FROM sessions WHERE user_id=?',(p['user_id'],))
            self.audit(p['user_id'],'all_sessions_revoked');return {'message':'All sessions signed out.'}
        @app.post('/api/auth/recover')
        def recover(payload:Recover,request:Request):
            self.rate('recover:'+(request.client.host if request.client else 'local'),10)
            hashed=password_hash(payload.new_password)
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT r.* FROM recovery r JOIN users u ON r.user_id=u.id WHERE r.token=? AND r.expires>? AND u.status="active"',(digest(payload.code),time.time())).fetchone()
                if not row:raise HTTPException(400,'Recovery code is invalid or expired.')
                c.execute('UPDATE users SET password=? WHERE id=?',(hashed,row['user_id']))
                c.execute('DELETE FROM recovery WHERE user_id=?',(row['user_id'],));c.execute('DELETE FROM sessions WHERE user_id=?',(row['user_id'],))
            self.audit(row['user_id'],'password_recovered');return {'message':'Password reset. Sign in with your new password.'}
        @app.get('/api/admin/overview')
        def overview(request:Request):
            p=self.admin(request);now=time.time()
            with self.connect() as c:
                counts={r['status']:r['n'] for r in c.execute('SELECT status,count(*) n FROM users GROUP BY status')}
                sessions=c.execute('SELECT count(*) FROM sessions s JOIN users u ON u.id=s.user_id WHERE u.status="active" AND s.expires>? AND s.seen>?',(now,now-1800)).fetchone()[0]
                recent=[dict(r) for r in c.execute("SELECT a.stamp,a.action,u.email FROM audit a LEFT JOIN users u ON a.actor=u.id WHERE a.action IN ('login_success','login_rejected','logout','registration_requested') ORDER BY a.id DESC LIMIT 50")]
                activity=[dict(r) for r in c.execute("SELECT u.id,u.email,u.name,u.status,u.created,(SELECT max(stamp) FROM audit WHERE actor=u.id AND action='login_success') last_login,(SELECT count(*) FROM sessions WHERE user_id=u.id AND expires>? AND seen>?) sessions FROM users u ORDER BY u.created DESC LIMIT 500",(now,now-1800))]
            with sqlite3.connect(self.legacy) as c:
                records=dict(c.execute('SELECT mode,count(*) FROM participants GROUP BY mode').fetchall())
            self.audit(p['user_id'],'admin_overview_read')
            return {'accounts':counts,'valid_sessions':sessions,'activity':activity,'events':recent,'legacy_records':records,'generated_at':now,'account_limit':500}
        @app.get('/api/admin/users')
        def users(request:Request):
            p=self.admin(request)
            with self.connect() as c:rows=c.execute('SELECT id,email,name,role,status,created FROM users ORDER BY created DESC LIMIT 500').fetchall()
            self.audit(p['user_id'],'account_directory_read');return {'items':[dict(r) for r in rows]}
        @app.post('/api/admin/users/{uid}')
        def user_action(uid:str,payload:AdminAction,request:Request):
            p=self.admin(request,payload.password)
            if payload.action not in ('approve','disable','enable','delete','recovery'):raise HTTPException(422,'Unsupported action.')
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
                if not row:raise HTTPException(404,'Account not found.')
                if row['role']=='admin' and payload.action in ('disable','delete'):raise HTTPException(409,'Administrator accounts cannot be disabled or deleted here.')
                if row['status']=='deleted':raise HTTPException(409,'Account is archived.')
                if payload.action=='recovery':
                    if row['status']!='active':raise HTTPException(409,'Activate the account first.')
                    code=secrets.token_urlsafe(32);c.execute('DELETE FROM recovery WHERE user_id=?',(uid,));c.execute('INSERT INTO recovery VALUES(?,?,?)',(digest(code),uid,time.time()+1800))
                else:
                    status={'approve':'active','enable':'active','disable':'disabled','delete':'deleted'}[payload.action]
                    c.execute('UPDATE users SET status=? WHERE id=?',(status,uid))
                c.execute('DELETE FROM sessions WHERE user_id=? OR target=?',(uid,uid))
            self.audit(p['user_id'],'account_'+payload.action,uid,payload.reason)
            return {'message':'Account updated. Archived account data is retained for administrator review; this is not a data purge.','recovery_code':code if payload.action=='recovery' else None}
        @app.post('/api/admin/workspace')
        def enter_workspace(payload:Enter,request:Request):
            p=self.admin(request,payload.password)
            target=None if payload.target=='self' else payload.target
            if target not in (None,'legacy'):
                with self.connect() as c:row=c.execute('SELECT status FROM users WHERE id=?',(target,)).fetchone()
                if not row or row['status']!='active':raise HTTPException(404,'Active account not found.')
            with self.connect() as c:c.execute('UPDATE sessions SET target=?,reason=? WHERE token=?',(target,payload.reason if target else None,p['token']))
            self.audit(p['user_id'],'workspace_entered',target or p['user_id'],payload.reason)
            return {'message':'Workspace selected. Return to My profile.'}
        @app.get('/api/admin/audit')
        def audit_log(request:Request,before:int=0):
            p=self.admin(request)
            with self.connect() as c:rows=c.execute('SELECT * FROM audit WHERE (?=0 OR id<?) ORDER BY id DESC LIMIT 100',(before,before)).fetchall()
            self.audit(p['user_id'],'audit_read');return {'items':[dict(r) for r in rows]}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',type=Path);parser.add_argument('--bootstrap-admin',action='store_true');parser.add_argument('--reset-admin',action='store_true');args=parser.parse_args()
    root=args.data_dir or Path(os.environ.get('NEUROACCESS_DATA_DIR',str(Path(os.environ.get('USERPROFILE',str(Path.home())))/'BAINP_DATA/local/neuroaccess_v1')))
    accounts=Accounts(root/'identity')
    if args.reset_admin:
        email=normalize(input('Existing administrator email: '))
        with accounts.connect() as c:row=c.execute('SELECT id FROM users WHERE email=? AND role="admin"',(email,)).fetchone()
        if not row:raise SystemExit('Administrator not found.')
        password=getpass.getpass('New password (15–128 characters): ')
        if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
        hashed=password_hash(password)
        with accounts.connect() as c:
            c.execute('UPDATE users SET password=?,status="active" WHERE id=?',(hashed,row['id']))
            c.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
            c.execute('DELETE FROM recovery WHERE user_id=?',(row['id'],))
        accounts.audit(row['id'],'administrator_local_recovery');print('Administrator password reset; sessions revoked.');return
    if not args.bootstrap_admin:parser.error('Use --bootstrap-admin or --reset-admin')
    with accounts.connect() as c:
        if c.execute('SELECT 1 FROM users WHERE role="admin"').fetchone():raise SystemExit('Administrator already exists. Use account recovery; bootstrap cannot overwrite it.')
    email=normalize(input('Administrator email (not automatically verified): '));name=input('Display name: ').strip()[:80]
    password=getpass.getpass('New password (15–128 characters): ')
    if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
    hashed=password_hash(password);uid=str(uuid4())
    with accounts.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM users WHERE role="admin"').fetchone():raise SystemExit('Administrator already exists.')
        c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(uid,email,name or 'Administrator',hashed,'admin','active',time.time()))
    accounts.audit(uid,'administrator_bootstrapped');print('Administrator created. No password was printed or saved as plaintext.')
if __name__=='__main__':main()

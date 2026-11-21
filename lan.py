"""Authoritative, persistent LAN sessions over certificate-pinned HTTPS."""
import copy, datetime, hashlib, hmac, http.client, inspect, json, secrets, socket, sqlite3, ssl, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from game import Game, new_game, RULESET, DURATIONS, RuleError, ASSETS
PROTOCOL='bft-lan-3'
LIMIT=262144

def tuples(v):return tuple(map(tuples,v)) if isinstance(v,list) else v

LINUX_MAGIC=b'BFTK1'

def _linux_key():
    """Per-user 256-bit key in a 0600 file. Linux counterpart to DPAPI: other local users cannot read it."""
    import os
    from platform_paths import data_dir
    path=data_dir()/'linux-protect.key'
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        try:os.chmod(path.parent,0o700)
        except OSError:pass
        fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(secrets.token_bytes(32))
    key=path.read_bytes()
    if len(key)!=32:raise OSError('Nøglefilen til forbindelsesdata er beskadiget.')
    return key

def protect_linux(data, decrypt=False):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aes=AESGCM(_linux_key())
    if not decrypt:
        nonce=secrets.token_bytes(12);return LINUX_MAGIC+nonce+aes.encrypt(nonce,data,LINUX_MAGIC)
    if not data.startswith(LINUX_MAGIC) or len(data)<len(LINUX_MAGIC)+12+16:raise OSError('Forbindelsesdata kunne ikke læses.')
    nonce=data[len(LINUX_MAGIC):len(LINUX_MAGIC)+12]
    try:return aes.decrypt(nonce,data[len(LINUX_MAGIC)+12:],LINUX_MAGIC)
    except Exception as e:raise OSError('Forbindelsesdata kunne ikke dekrypteres (anden bruger eller beskadiget).') from e

def protect(data, decrypt=False):
    import sys
    if sys.platform!='win32':return protect_linux(data,decrypt)
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):_fields_=[('n',wintypes.DWORD),('p',ctypes.POINTER(ctypes.c_char))]
    buf=ctypes.create_string_buffer(data);src=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_char)));dst=Blob()
    fn=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst)):raise OSError('Windows kunne ikke beskytte forbindelsesdata.')
    try:return ctypes.string_at(dst.p,dst.n)
    finally:ctypes.windll.kernel32.LocalFree(dst.p)

def save_credentials(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_bytes(protect(json.dumps(value).encode()));temp.replace(path)
def load_credentials(path):return json.loads(protect(Path(path).read_bytes(),True))

class Session:
    def __init__(self,path,days=31,name='BFT-aften'):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.seen={}
        self.db=sqlite3.connect(str(path),check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        row=self.db.execute('SELECT data FROM state WHERE id=1').fetchone()
        if row:self.s=json.loads(row[0])
        else:
            if days not in DURATIONS:raise ValueError('Ugyldig tidshorisont')
            self.s=dict(protocol=PROTOCOL,ruleset=RULESET,id=secrets.token_hex(16),name=name[:40],days=days,started=False,code=secrets.token_urlsafe(16),owner=secrets.token_urlsafe(32),players={},receipts={})
            self.commit()
        if self.s['protocol'] in ('bft-lan-1','bft-lan-2') and self.s['ruleset']=='bft-4':
            backup=self.path.with_suffix('.pre-v1.1.json')
            if not backup.exists():backup.write_text(json.dumps(self.s),encoding='utf-8')
            for p in self.s['players'].values():
                if p['state']:
                    g=self.game(p);g.upgrade_events();g.check();p['state']=g.s
            self.s.update(protocol=PROTOCOL,ruleset=RULESET);self.commit()
        if self.s['protocol']!=PROTOCOL or self.s['ruleset']!=RULESET:raise ValueError('Sessionen bruger en anden LAN-version.')
    def commit(self):
        with self.db:self.db.execute('INSERT OR REPLACE INTO state VALUES (1,?)',(json.dumps(self.s,ensure_ascii=False),))
    def game(self,p):
        g=Game();g.s=copy.deepcopy(p['state']);g.rng.setstate(tuples(p['rng']));return g
    def dispatch(self,m):
        with self.lock:
            if getattr(self,'closed',False):raise ValueError('Værten lukker sessionen.')
            if isinstance(m,dict) and m.get('op')=='poll':return self.handle(m)
            before=copy.deepcopy(self.s)
            try:
                result=self.handle(m)
                if self.s!=before:self.commit()
                return result
            except Exception:
                self.s=before
                raise
    def handle(self,m):
        if not isinstance(m,dict) or m.get('protocol')!=PROTOCOL:raise ValueError('Forkert LAN-version.')
        op=m.get('op')
        if op=='join':
            if not hmac.compare_digest(str(m.get('code','')),self.s['code']):raise ValueError('Forkert invitation.')
            token=m.get('token');key=hashlib.sha256(str(token).encode()).hexdigest()
            if key not in self.s['players']:
                if self.s['started']:raise ValueError('Spillet er startet. Brug Genforbind på din oprindelige pc.')
                if len(self.s['players'])>=8:raise ValueError('Lobbyen er fuld.')
                name=''.join(c for c in str(m.get('name','')) if c.isprintable()).strip()[:24]
                if not name or any(p['name'].casefold()==name.casefold() for p in self.s['players'].values()):raise ValueError('Vælg et andet spillernavn.')
                if not isinstance(token,str) or len(token)!=64:raise ValueError('Ugyldig spilleridentitet.')
                owner=hmac.compare_digest(str(m.get('owner','')),self.s['owner'])
                self.s['players'][key]=dict(id=secrets.token_hex(8),name=name,owner=owner,ready=False,revision=0,state=None,rng=None)
            self.seen[key]=time.monotonic()
            return self.view(key)
        key=hashlib.sha256(str(m.get('token','')).encode()).hexdigest()
        if key not in self.s['players']:raise ValueError('Forbind igen med din gemte invitation.')
        p=self.s['players'][key];self.seen[key]=time.monotonic()
        if op=='poll':return self.view(key)
        rid=m.get('request_id')
        if not isinstance(rid,str) or len(rid)!=32:raise ValueError('Ugyldigt request-id.')
        receipt_key=key+':'+rid;payload=hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()
        if receipt_key in self.s['receipts']:
            if self.s['receipts'][receipt_key]!=payload:raise ValueError('Genbrugt request-id med andet indhold.')
            return self.view(key)
        if op=='ready':
            if self.s['started']:raise ValueError('Spillet er startet.')
            p['ready']=not p['ready']
        elif op=='start':
            if not p['owner'] or self.s['started']:raise ValueError('Kun værten kan starte én gang.')
            if len(self.s['players'])<2 or not all(x['ready'] and time.monotonic()-self.seen.get(k,-100)<15 for k,x in self.s['players'].items()):raise ValueError('Mindst to spillere; alle skal være klar og online.')
            for x in self.s['players'].values():
                g=new_game(x['name'],days=self.s['days'],seed=secrets.randbits(256));x.update(state=g.s,rng=g.rng.getstate())
            self.s['started']=True
        elif op=='retire':
            if not p['owner']:raise ValueError('Kun værten kan fjerne en spiller.')
            target=next((x for x in self.s['players'].values() if x['id']==m.get('target')),None)
            if target is None or target['id']==p['id']:raise ValueError('Ugyldig deltager.')
            if not self.s['started']:
                target_key=next(k for k,x in self.s['players'].items() if x is target)
                del self.s['players'][target_key]
            else:
                if target['state']['finished']:raise ValueError('Spilleren er allerede afsluttet.')
                g=self.game(target);g.finish('Værten markerede spilleren som opgivet (DNF).')
                target.update(state=g.s,rng=g.rng.getstate(),revision=target['revision']+1,dnf=True)
        elif op=='leave':
            if self.s['started']:raise ValueError('Brug Afslut for at afslutte spillet.')
            if p['owner']:raise ValueError('Værten skal lukke lobbyen.')
            del self.s['players'][key]
            return {'left':True}
        elif op=='command':
            if not self.s['started']:raise ValueError('Spillet er ikke startet.')
            if type(m.get('revision')) is not int or m.get('revision')!=p['revision']:raise ValueError('Spillet blev opdateret. Kontrollér den aktuelle pris og prøv igen.')
            action=m.get('action');args=m.get('args')
            allowed={'buy','sell','travel','wait','bag','weapon','bank','hire','dispatch','dismiss','asset','fund','sell_asset','heal','police','finish','wash'}
            if action not in allowed or not isinstance(args,dict):raise ValueError('Ugyldig handling.')
            g=self.game(p)
            inspect.signature(getattr(g,'do_'+action)).bind(**args)
            for k,v in args.items():
                if k in ('amount','qty','tier','district'):
                    if type(v) is not int or abs(v)>10**12:raise ValueError('Ugyldigt tal.')
                elif type(v) is not str or len(v)>100:raise ValueError('Ugyldigt argument.')
            g.execute(action,**args)
            p.update(state=g.s,rng=g.rng.getstate(),revision=p['revision']+1)
        else:raise ValueError('Ukendt netværkshandling.')
        self.s['receipts'][receipt_key]=payload
        return self.view(key)
    def view(self,key):
        public=[]
        for k,p in self.s['players'].items():
            online=time.monotonic()-self.seen.get(k,-100)<15
            v=dict(id=p['id'],name=p['name'],owner=p['owner'],ready=p['ready'],online=online,dnf=p.get('dnf',False))
            if p['state']:
                st=p['state'];assets=sum(ASSETS[a['tier']][1]*60//100 for a in st['assets']);v.update(day=st['day'],bank=st['clean'],assets=assets,debt=st['debt'],score=st['clean']+assets-st['debt'],finished=st['finished'])
            public.append(v)
        p=self.s['players'][key];original=p['state'];state=copy.deepcopy({k:v for k,v in original.items() if k not in ('markets','log','history')}) if original else None
        if state:
            market=copy.deepcopy(original['markets'][state['city']][state['district']])
            state['markets']={state['city']:[{} for _ in range(6)]};state['markets'][state['city']][state['district']]=market
            for order in state['washing']:order.pop('ready',None)
            state['log']=original['log'][:30];state['history']=[]
        return dict(session=self.s['id'],name=self.s['name'],days=self.s['days'],started=self.s['started'],players=public,me=p['id'],revision=p['revision'],state=state,complete=self.s['started'] and all(x['state']['finished'] for x in self.s['players'].values()))

class Server:
    def __init__(self,directory,days=31,name='BFT-aften',port=47652,bind='0.0.0.0'):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        self.session=Session(directory/'session.sqlite',days,name)
        pem=directory/'certificate.pem';private=directory/'key.dpapi'
        if not pem.exists() or not private.exists():
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'BFT LAN')]);now=datetime.datetime.now(datetime.timezone.utc)
            cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=3650)).sign(key,hashes.SHA256())
            pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            private.write_bytes(protect(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())))
        self.fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem.read_text())).hexdigest()
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                self.connection.settimeout(5)
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=LIMIT:raise ValueError('Beskeden er for stor.')
                    m=json.loads(self.rfile.read(n));result=owner.session.dispatch(m);response={'ok':True,'view':result}
                except (ValueError,TypeError,KeyError,AssertionError) as e:response={'ok':False,'error':str(e)[:200]}
                except Exception:response={'ok':False,'error':'Værten kunne ikke gemme handlingen. Prøv igen.'}
                data=json.dumps(response,ensure_ascii=False).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:self.wfile.write(data)
                except OSError:pass
        class HTTP(ThreadingHTTPServer):
            daemon_threads=True
            slots=threading.BoundedSemaphore(24)
            def process_request(self,request,address):
                if not self.slots.acquire(False):request.close();return
                try:super().process_request(request,address)
                except Exception:self.slots.release();raise
            def process_request_thread(self,request,address):
                try:
                    request.settimeout(5)
                    wrapped=context.wrap_socket(request,server_side=True)
                    super().process_request_thread(wrapped,address)
                except (OSError,ssl.SSLError):request.close()
                finally:self.slots.release()
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
        temp=directory/'key-loading.pem'
        try:
            import os
            temp.unlink(missing_ok=True)
            fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)  # never world-readable, even briefly
            with os.fdopen(fd,'wb') as f:f.write(protect(private.read_bytes(),True))
            context.load_cert_chain(str(pem),str(temp))
        finally:temp.unlink(missing_ok=True)
        try:self.http=HTTP((bind,port),Handler)
        except Exception:self.session.db.close();raise
        self.port=self.http.server_address[1];self.closed=False
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        from lan_discovery import Advertiser
        self.discovery=None
        try:self.discovery=Advertiser(self)
        except OSError:pass  # Direct invitation remains available if UDP is unavailable.
    def invite(self,host):return '|'.join([host,str(self.port),self.fingerprint,self.session.s['code']])
    def close(self):
        if self.closed:return
        self.closed=True
        if self.discovery:self.discovery.close()
        self.http.shutdown();self.http.server_close()
        with self.session.lock:
            self.session.closed=True;self.session.db.close()

def rpc(invite,message):
    host,port,fingerprint,code=invite.strip().split('|')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    conn=http.client.HTTPSConnection(host,int(port),timeout=5,context=context)
    try:
        conn.connect()
        actual=hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
        if not hmac.compare_digest(actual,fingerprint):raise ValueError('Værtens certifikat matcher ikke invitationen.')
        body=dict(message,protocol=PROTOCOL)
        if body.get('op')=='join':body['code']=code
        conn.request('POST','/session',json.dumps(body).encode(),{'Content-Type':'application/json'})
        response=conn.getresponse();data=response.read(LIMIT+1)
        if len(data)>LIMIT:raise ValueError('For stort serversvar.')
        return json.loads(data)
    finally:conn.close()

def addresses():
    values={'127.0.0.1'}
    try:values.update(x[4][0] for x in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET))
    except OSError:pass
    try:  # Linux often resolves the hostname to 127.0.1.1 only; a UDP connect reveals the real LAN address (sends nothing).
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.connect(('192.0.2.1',9));values.add(s.getsockname()[0])
    except OSError:pass
    return sorted(values,key=lambda x:x.startswith('127.'))

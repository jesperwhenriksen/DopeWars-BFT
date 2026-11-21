"""Small IPv4 LAN discovery. Open lobbies are joinable on the trusted local network."""
import json,secrets,socket,threading,time
from lan import PROTOCOL
PORT=47653
MAGIC='BFT-DISCOVERY-1'
class Advertiser:
 def __init__(self,server,port=PORT):
  self.server=server;self.closed=False
  self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
  try:
   self.sock.bind(('',port));self.sock.settimeout(.3)
  except Exception:self.sock.close();raise
  self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
 def run(self):
  while not self.closed:
   try:
    raw,addr=self.sock.recvfrom(8192);m=json.loads(raw)
    if m.get('magic')!=MAGIC or m.get('protocol')!=PROTOCOL or not isinstance(m.get('nonce'),str) or len(m['nonce'])!=32:continue
    with self.server.session.lock:
     s=self.server.session.s
     # LAN-1.1 / NFR-5: running games advertise identity, never the join code.
     reply=dict(magic=MAGIC,protocol=PROTOCOL,nonce=m['nonce'],session=s['id'],name=s['name'],days=s['days'],players=len(s['players']),port=self.server.port,fingerprint=self.server.fingerprint,started=s['started'],options=s.get('options',{}))
     if not s['started']:reply['code']=s['code']
    self.sock.sendto(json.dumps(reply).encode(),addr)
   except (OSError,ValueError,AttributeError):continue
 def close(self):
  self.closed=True;self.sock.close();self.thread.join(timeout=1)

def targets():
 result={'255.255.255.255','127.0.0.1'}
 try:
  from PySide6.QtNetwork import QNetworkInterface
  for interface in QNetworkInterface.allInterfaces():
   for address in interface.addressEntries():
    b=address.broadcast().toString()
    if b and ':' not in b:result.add(b)
 except Exception:pass
 return result

def scan(timeout=1.2,hosts=None,port=PORT):
 nonce=secrets.token_hex(16);found={}
 packet=json.dumps(dict(magic=MAGIC,protocol=PROTOCOL,nonce=nonce)).encode()
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);sock.bind(('',0));sock.settimeout(.15)
  for host in hosts or targets():
   try:sock.sendto(packet,(host,port))
   except OSError:pass
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   try:
    raw,addr=sock.recvfrom(8192);m=json.loads(raw)
    if m.get('magic')!=MAGIC or m.get('protocol')!=PROTOCOL or m.get('nonce')!=nonce:continue
    if not isinstance(m.get('session'),str) or len(m['session'])!=32:continue
    if not isinstance(m.get('name'),str) or len(m['name'])>40:continue
    if type(m.get('port')) is not int or not 1<=m['port']<=65535:continue
    if type(m.get('players')) is not int or not 0<=m['players']<=8:continue
    if m.get('days') not in (31,90,180,365):continue
    if not isinstance(m.get('fingerprint'),str) or len(m['fingerprint'])!=64 or any(c not in '0123456789abcdef' for c in m['fingerprint']):continue
    if type(m.get('started')) is not bool:continue
    if not isinstance(m.get('options'),dict) or any(type(m['options'].get(k)) is not bool for k in ('allow_tips','shared_market')):continue
    if m['started']:
     if 'code' in m:continue
    elif not isinstance(m.get('code'),str) or not 1<=len(m['code'])<=80:continue
    m={k:m[k] for k in ('session','name','days','players','port','fingerprint','started','options')+(() if m['started'] else ('code',))}
    m['host']=addr[0]
    if not m['started']:m['invite']='|'.join([addr[0],str(m['port']),m['fingerprint'],m['code']])
    # Prefer an actual LAN address over the local loopback reply.
    if m['session'] not in found or not addr[0].startswith('127.'):found[m['session']]=m
   except (OSError,ValueError,AttributeError):continue
 return sorted(found.values(),key=lambda x:x['name'].casefold())


def reconnect_invite(credentials, offers):
 """LAN-1.2--1.4: discovery is a hint, authenticated by the original pin."""
 import hmac
 old=credentials['invite'].split('|')
 if len(old)!=4 or not credentials.get('session'):return None
 for offer in offers:
  if offer.get('session')!=credentials['session']:continue
  fingerprint=offer.get('fingerprint')
  if not isinstance(fingerprint,str) or not hmac.compare_digest(fingerprint,old[2]):continue
  host=offer.get('host');port=offer.get('port')
  if not isinstance(host,str) or '|' in host or type(port) is not int or not 1<=port<=65535:continue
  return '|'.join([host,str(port),old[2],old[3]])
 return None

import copy,json,secrets,tempfile,unittest,uuid
from pathlib import Path
from lan import Server,rpc,load_credentials,save_credentials
class LanTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.directory=Path(self.tmp.name);self.server=Server(self.directory,port=0,bind='127.0.0.1');self.addCleanup(lambda:self.server.close());self.invite=self.server.invite('127.0.0.1');self.a=secrets.token_hex(32);self.b=secrets.token_hex(32)
  self.call(self.a,'join',name='A',owner=self.server.session.s['owner']);self.call(self.b,'join',name='B')
 def tearDown(self):self.server.close()
 def call(self,token,op,**args):return rpc(self.invite,dict(token=token,op=op,request_id=uuid.uuid4().hex,**args))
 def start(self):
  self.call(self.a,'ready');self.call(self.b,'ready');r=self.call(self.a,'start');self.assertTrue(r['ok']);return r['view']
 def test_lobby_and_host_authority(self):
  self.assertFalse(self.call(self.b,'start')['ok']);self.assertFalse(self.call(self.a,'start')['ok']);v=self.start();self.assertEqual(v['state']['city'],'Høje på Fyn');self.assertFalse(self.call(secrets.token_hex(32),'join',name='late')['ok'])
 def test_independent_days_and_privacy(self):
  self.start();before=self.call(self.b,'poll')['view']['state'];v=self.call(self.a,'command',revision=0,action='wait',args={})['view'];self.assertEqual(v['state']['day'],2);self.assertEqual(self.call(self.b,'poll')['view']['state'],before)
  self.assertNotIn('rng',v);self.assertNotIn('black',v['players'][0]);self.assertNotIn('inventory',v['players'][1]);self.assertEqual(len(v['state']['markets']),1)
 def test_duplicate_command_and_payload_reuse(self):
  self.start();m=dict(op='command',token=self.a,request_id=uuid.uuid4().hex,revision=0,action='buy',args=dict(drug='hash',qty=1))
  r=rpc(self.invite,m);self.assertTrue(r['ok']);r2=rpc(self.invite,m);self.assertEqual(r['view']['state'],r2['view']['state']);m['args']['qty']=2;self.assertFalse(rpc(self.invite,m)['ok'])
 def test_validation_and_stale_revision(self):
  self.start()
  for action,args in [('buy',dict(drug='hash',qty=True)),('buy',dict(drug='hash',qty=-1)),('set_money',{}),('buy',dict(drug='hash',qty=1,player_id='B'))]:self.assertFalse(self.call(self.a,'command',revision=0,action=action,args=args)['ok'])
  self.call(self.a,'command',revision=0,action='wait',args={});self.assertFalse(self.call(self.a,'command',revision=0,action='wait',args={})['ok'])
 def test_certificate_pin_and_auth(self):
  bad=self.invite.split('|');bad[2]='0'*64
  with self.assertRaises(ValueError):rpc('|'.join(bad),dict(op='poll',token=self.a))
  self.assertFalse(self.call('invalid','poll')['ok'])
 def test_restart_and_exactly_once(self):
  self.start();m=dict(op='command',token=self.a,request_id=uuid.uuid4().hex,revision=0,action='wait',args={});r=rpc(self.invite,m)
  self.server.close();self.server.session.db.close();self.server=Server(self.directory,port=0,bind='127.0.0.1');self.invite=self.server.invite('127.0.0.1')
  self.assertEqual(rpc(self.invite,m)['view']['state'],r['view']['state'])
 def test_finish_does_not_stop_other_player(self):
  self.start();self.call(self.a,'command',revision=0,action='finish',args={});v=self.call(self.b,'command',revision=0,action='wait',args={})['view'];self.assertFalse(v['complete']);v=self.call(self.b,'command',revision=1,action='finish',args={})['view'];self.assertTrue(v['complete'])
 def test_credentials_protected(self):
  p=self.directory/'client';v=dict(token=self.a,invite=self.invite);save_credentials(p,v);self.assertNotIn(self.a.encode(),p.read_bytes());self.assertEqual(load_credentials(p),v)
 def test_linux_protection_key_is_private_and_tamper_detected(self):
  import os,stat,sys
  if sys.platform=='win32':self.skipTest('Windows uses DPAPI')
  from lan import protect
  from platform_paths import data_dir
  blob=protect(b'hemmelig');self.assertNotIn(b'hemmelig',blob);self.assertEqual(protect(blob,True),b'hemmelig')
  self.assertEqual(stat.S_IMODE(os.stat(data_dir()/'linux-protect.key').st_mode),0o600)
  bad=bytearray(blob);bad[-1]^=1
  with self.assertRaises(OSError):protect(bytes(bad),True)
 def test_save_failure_rolls_back(self):
  from unittest.mock import patch
  self.start();before=self.call(self.a,'poll')['view']['state']
  with patch.object(self.server.session,'commit',side_effect=OSError('disk')):self.assertFalse(self.call(self.a,'command',revision=0,action='wait',args={})['ok'])
  self.assertEqual(self.call(self.a,'poll')['view']['state'],before)
 def test_eight_clients(self):
  for i in range(6):self.assertTrue(self.call(secrets.token_hex(32),'join',name=str(i))['ok'])
  self.assertFalse(self.call(secrets.token_hex(32),'join',name='extra')['ok'])
 def test_guest_can_leave_lobby_and_slot_is_released(self):
  self.assertTrue(self.call(self.b,'leave')['ok'])
  self.assertEqual(len(self.call(self.a,'poll')['view']['players']),1)
  self.assertFalse(self.call(self.a,'leave')['ok'])
  self.assertTrue(self.call(secrets.token_hex(32),'join',name='B')['ok'])
 def test_retire_visible_dnf_and_guest_denied(self):
  v=self.start();target=next(p['id'] for p in v['players'] if p['name']=='B')
  self.assertFalse(self.call(self.b,'retire',target=target)['ok'])
  v=self.call(self.a,'retire',target=target)['view'];p=next(p for p in v['players'] if p['id']==target)
  self.assertTrue(p['dnf']);self.assertTrue(p['finished'])
 def test_concurrent_commands_and_private_wash(self):
  from concurrent.futures import ThreadPoolExecutor
  self.start()
  with ThreadPoolExecutor(max_workers=2) as ex:
   futures=[ex.submit(self.call,self.a,'command',revision=0,action='buy',args=dict(drug='hash',qty=1)) for _ in range(2)]
   self.assertEqual(sum(f.result()['ok'] for f in futures),1)
  v=self.call(self.a,'command',revision=1,action='wash',args=dict(amount=100,tier=0))['view']
  self.assertNotIn('ready',v['state']['washing'][0]);self.assertNotIn('washing',v['players'][0])
 def test_LAN_1_1_discovery_join_and_hide_started_code(self):
  from lan_discovery import scan
  found=scan(timeout=.25,hosts=['127.0.0.1'])
  entry=next(g for g in found if g['session']==self.server.session.s['id'])
  self.assertEqual(entry['players'],2);self.assertNotIn('owner',entry);self.assertNotIn('state',entry)
  c=secrets.token_hex(32)
  self.assertTrue(rpc(entry['invite'],dict(op='join',token=c,name='Found'))['ok'])
  self.call(c,'ready');self.start()
  running=next(g for g in scan(timeout=.25,hosts=['127.0.0.1']) if g['session']==entry['session'])
  self.assertTrue(running['started']);self.assertNotIn('code',running);self.assertNotIn('invite',running)
 def test_discovery_stops_with_server(self):
  from lan_discovery import scan
  self.server.discovery.close()
  self.assertFalse(any(g['session']==self.server.session.s['id'] for g in scan(timeout=.25,hosts=['127.0.0.1'])))
 def test_LAN_3_1_4_keepalive_and_recheck_pin_before_payload(self):
  import time
  from lan import RpcClient
  from unittest.mock import patch
  client=RpcClient();self.addCleanup(client.close)
  start=self.server.handshakes
  for _ in range(6):self.assertTrue(client.call(self.invite,dict(op='poll',token=self.a))['ok'])
  self.assertEqual(self.server.handshakes-start,1)
  client.close()
  self.assertTrue(client.call(self.invite,dict(op='poll',token=self.a))['ok'])
  self.assertEqual(self.server.handshakes-start,2)
  bad=self.invite.split('|');bad[2]='0'*64
  with patch.object(self.server.session,'dispatch',wraps=self.server.session.dispatch) as dispatch:
   with self.assertRaisesRegex(ValueError,'certifikat'):client.call('|'.join(bad),dict(op='poll',token=self.a))
   dispatch.assert_not_called()

 def test_LAN_1_2_3_4_5_LAN_3_3_automatic_client_relocation_under_15s(self):
  import os,time
  os.environ['QT_QPA_PLATFORM']='offscreen'
  from unittest.mock import patch
  from PySide6.QtWidgets import QApplication
  import app as ui
  from lan_ui import Connection,Lobby
  from lan_discovery import scan
  q=QApplication.instance() or QApplication([]);ui.load_fonts();q.setStyle('Fusion');q.setStyleSheet(ui.STYLE)
  view=self.start()
  creds=dict(token=self.a,name='A',invite=self.invite,session=view['session'])
  with patch.object(ui,'DATA',self.directory):
   lobby=Lobby();lobby.browsing=False;lobby.search_timer.stop()
   c=Connection(creds,self.directory/'reconnect.dpapi');lobby.controller=c;c.timer.stop()
   c.response.connect(lambda result:lobby.received(c,result));c.failure.connect(lambda error:lobby.failed(c,error))
   lobby.received(c,({'op':'poll'},dict(ok=True,view=view)))
   self.assertEqual(c.timer.interval(),1000)
   old_port=self.server.port;self.server.close()
   self.server=Server(self.directory,port=0,bind='127.0.0.1');self.invite=self.server.invite('127.0.0.1')
   self.assertNotEqual(old_port,self.server.port)
   start=time.monotonic()
   try:
    with patch('lan_ui.scan',side_effect=lambda:scan(timeout=.2,hosts=['127.0.0.1'])) as search:
     c.timer.start(1000);c.tick()
     while time.monotonic()-start<15 and c.c['invite']!=self.invite:
      q.processEvents();time.sleep(.01)
     self.assertEqual(c.c['invite'],self.invite)
     search.assert_called();self.assertGreaterEqual(search.call_count,1)
    self.assertEqual(load_credentials(c.path)['invite'],self.invite)
    self.assertIn('fundet igen',lobby.window.statusBar().currentMessage())
    self.assertTrue(c.online);self.assertEqual(c.failures,0)
   finally:
    c.stop()
    if lobby.window:
     lobby.window.hide();lobby.window.deleteLater()
    lobby.close();q.processEvents()

 def test_LAN_3_5_NFR_8_eight_clients_and_ui_heartbeat(self):
  from benchmark_lan import measure
  # Keep initial TLS handshakes in the sample, but measure long enough that
  # eight connection starts do not dominate the 95th percentile of polling.
  result=measure(seconds=5,keepalive=True,clients=8)
  self.assertEqual(result['errors'],[])
  self.assertEqual(result['commands_sent'],result['commands_committed'])
  self.assertGreater(result['commands_committed'],0)
  self.assertGreater(result['ui_heartbeats'],10)
  self.assertLess(result['poll_p95_ms'],50,result)

class SpecSessionTests(unittest.TestCase):
 def setUp(self):
  from lan import Session
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'session.sqlite'
  self.s=Session(self.path,options=dict(allow_tips=True,shared_market=True));self.addCleanup(lambda:self.s.db.close())
  self.tokens=['a'*64,'b'*64,'c'*64]
  for i,t in enumerate(self.tokens):self.call(i,'join',code=self.s.s['code'],name='Spiller '+str(i),owner=self.s.s['owner'] if i==0 else '')
  for i in range(3):self.call(i,'ready')
  self.call(0,'start')
 def message(self,i,op,**args):
  from lan import PROTOCOL
  return dict(protocol=PROTOCOL,token=self.tokens[i],op=op,request_id=uuid.uuid4().hex,**args)
 def call(self,i,op,**args):return self.s.dispatch(self.message(i,op,**args))
 def player(self,i):
  import hashlib
  return self.s.s['players'][hashlib.sha256(self.tokens[i].encode()).hexdigest()]
 def command(self,i,action,**args):return self.call(i,'command',action=action,args=args,revision=self.player(i)['revision'])
 def tip(self,i=0,target=1):return self.command(i,'tip',target=self.player(target)['id'])
 def test_TIP_1_3_7_8_10_atomic_anonymous_tip_without_rng(self):
  from game import tip_cost
  for p in self.s.s['players'].values():p['state']['black']=25001
  rng=[copy.deepcopy(self.player(i)['rng']) for i in range(3)]
  a=self.tip();b=self.call(1,'poll')
  self.assertEqual(a['state']['black'],25001-tip_cost(25001))
  self.assertEqual(b['state']['tip_until_day'],6)
  self.assertEqual(a['state']['tip_cooldown_until'],11)
  self.assertEqual(a['revision'],1);self.assertEqual(b['revision'],1)
  self.assertEqual(rng,[self.player(i)['rng'] for i in range(3)])
  self.assertEqual(a['events'],b['events'])
  self.assertEqual(a['events'][0]['data'],{})
  self.assertEqual(a['events'][0]['player_id'],b['me'])
  self.assertNotIn(a['me'],json.dumps(b['state']['day_events']))
  self.assertIn('Politiet har fået et tip',b['state']['day_events'][0]['title'])
 def test_TIP_2_rejections_leave_no_state_change(self):
  cases=[('self',lambda:self.player(0)['id']),('missing',lambda:'missing'),
         ('finished',lambda:self.player(1)['id']),('dnf',lambda:self.player(1)['id']),
         ('active',lambda:self.player(1)['id']),('cooldown',lambda:self.player(1)['id']),
         ('funds',lambda:self.player(1)['id']),('disabled',lambda:self.player(1)['id'])]
  original=copy.deepcopy(self.s.s)
  for case,target in cases:
   self.s.s=copy.deepcopy(original)
   if case=='finished':self.player(1)['state']['finished']=True
   if case=='dnf':self.player(1)['dnf']=True
   if case=='active':self.player(1)['state']['tip_until_day']=6
   if case=='cooldown':self.player(0)['state']['tip_cooldown_until']=11
   if case=='funds':self.player(0)['state']['black']=499
   if case=='disabled':self.s.s['options']['allow_tips']=False
   before=copy.deepcopy(self.s.s)
   with self.subTest(case=case),self.assertRaises(ValueError):self.command(0,'tip',target=target())
   self.assertEqual(self.s.s,before)
 def test_TIP_2_target_cannot_stack_and_cooldown_uses_tipper_days(self):
  self.tip()
  with self.assertRaises(ValueError):self.tip(2,1)
  with self.assertRaises(ValueError):self.tip(0,2)
  self.player(0)['state'].update(day=11,last_police_day=11,last_market_event_day=11)
  self.tip(0,2);self.assertEqual(self.player(2)['state']['tip_until_day'],6)
 def test_TIP_4_offline_time_uses_target_own_days(self):
  from unittest.mock import patch
  import time
  key=next(k for k,p in self.s.s['players'].items() if p is self.player(1))
  self.s.seen[key]=time.monotonic()-60
  self.tip();self.assertEqual(self.player(1)['state']['day'],1)
  for _ in range(6):self.command(0,'wait')
  self.assertEqual(self.player(1)['state']['tip_until_day'],6)
  self.assertEqual(self.player(1)['state']['day'],1)
  for _ in range(5):self.command(1,'wait')
  self.assertTrue(self.s.game(self.player(1)).tip_active)
  self.command(1,'wait');self.assertFalse(self.s.game(self.player(1)).tip_active)
 def test_TIP_9_options_defaults_preview_and_persistence(self):
  from lan import Session,PROTOCOL
  with tempfile.TemporaryDirectory() as d:
   s=Session(Path(d)/'s.sqlite')
   try:
    expected=dict(allow_tips=False,shared_market=True)
    self.assertEqual(s.s['options'],expected)
    self.assertEqual(s.dispatch(dict(protocol=PROTOCOL,op='info',code=s.s['code']))['options'],expected)
    with self.assertRaises(ValueError):s.dispatch(dict(protocol=PROTOCOL,op='info',code='wrong'))
   finally:s.db.close()
  self.s.db.close();self.s=Session(self.path)
  self.assertEqual(self.s.s['options'],dict(allow_tips=True,shared_market=True))
 def test_TIP_NFR_4_receipts_stale_revision_and_transaction_failure(self):
  from unittest.mock import patch
  m=self.message(0,'command',action='tip',args=dict(target=self.player(1)['id']),revision=0)
  a=self.s.dispatch(m);b=self.s.dispatch(m)
  self.assertEqual(a['state'],b['state']);self.assertEqual(len(b['events']),1)
  m['args']['target']=self.player(2)['id']
  with self.assertRaisesRegex(ValueError,'request-id'):self.s.dispatch(m)
  with self.assertRaisesRegex(ValueError,'opdateret'):self.call(1,'command',action='wait',args={},revision=0)
  # A second sender to a fresh target reaches commit; a disk failure rolls back
  # sender money, target effect, revisions, event and receipt together.
  before=copy.deepcopy(self.s.s)
  with patch.object(self.s,'commit',side_effect=OSError('disk')),self.assertRaises(OSError):self.tip(2,0)
  self.assertEqual(before,self.s.s)
 def test_LAN_2_1_2_3_4_public_event_types_limits_and_privacy(self):
  self.player(0)['state']['clean']=10000;self.command(0,'asset',tier=0)
  for _ in range(23):self.command(0,'wait')
  self.tip(1,2);self.command(0,'finish')
  self.call(0,'retire',target=self.player(1)['id'])
  events=self.call(2,'poll')['events']
  self.assertEqual({e['type'] for e in events},{'first_asset','milestone','tip','finished','dnf'})
  self.assertEqual([e['data']['percent'] for e in events if e['type']=='milestone'],[25,50,75])
  with self.assertRaises(ValueError):self.s.event('tip',self.player(1),black=100)
  for _ in range(70):self.s.event('tip',self.player(1))
  self.assertEqual(len(self.s.s['events']),50)
  a=self.call(0,'poll');b=self.call(2,'poll');self.assertEqual(a['events'],b['events'])
  self.assertEqual(len(a['events']),20);ids=[e['id'] for e in a['events']];self.assertEqual(ids,sorted(ids));self.assertEqual(len(set(ids)),20)
  text=json.dumps(dict(players=a['players'],events=a['events']))
  for secret in ('black','inventory','city','district','market_seed','prices','sender','tip_until_day','tip_cooldown_until'):self.assertNotIn('"'+secret+'"',text)
 def test_LAN_3_2_unchanged_small_but_other_player_change_refreshes(self):
  a=self.call(0,'poll');since={k:a[k] for k in ('revision','lobby_version')}
  small=self.call(0,'poll',since=since);self.assertEqual(small,dict(unchanged=True))
  self.assertLess(len(json.dumps(dict(ok=True,view=small)).encode()),200)
  self.command(1,'wait');changed=self.call(0,'poll',since=since)
  self.assertIn('players',changed);self.assertNotEqual(changed['lobby_version'],since['lobby_version'])
  self.assertEqual(changed['revision'],since['revision'])
 def test_LAN_3_2_presence_and_server_restart_invalidates_version(self):
  import time
  from lan import Session
  a=self.call(0,'poll');since={k:a[k] for k in ('revision','lobby_version')}
  self.s.seen[next(k for k,p in self.s.s['players'].items() if p is self.player(1))]=time.monotonic()-60
  self.assertIn('players',self.call(0,'poll',since=since))
  self.s.db.close();self.s=Session(self.path)
  self.assertIn('players',self.call(0,'poll',since=since))
 def test_BAL_5_LAN_4_shared_prices_personal_state_and_off_switch(self):
  a=self.player(0);b=self.player(1)
  self.assertEqual(a['state']['markets'],b['state']['markets'])
  self.assertNotEqual(a['rng'],b['rng'])
  for _ in range(5):self.command(0,'wait')
  for _ in range(5):self.command(1,'wait')
  self.assertEqual(a['state']['markets'],b['state']['markets'])
  v=self.call(0,'poll');self.assertNotIn('market_seed',v['state']);self.assertNotIn('seed',v)
  # A new opt-out lobby has independent markets, matching solo behavior.
  self.s.s['started']=False;self.s.s['options']['shared_market']=False
  self.call(0,'start')
  self.assertNotEqual(self.player(0)['state']['markets'],self.player(1)['state']['markets'])
 def test_BAL_6_LAN_5_NFR_2_public_history_only_day_score(self):
  for _ in range(9):self.command(0,'wait')
  for _ in range(14):self.command(1,'wait')
  a=self.player(0)['state'];b=self.player(1)['state']
  for p in (a,b):p['history'][0].update(black=123,inventory={'hash':1},city='Randers')
  public=self.call(2,'poll')['players']
  for p in public:
   for h in p['history']:self.assertEqual(set(h),{'day','score'})
  for i in (0,1):
   entry=next(p for p in public if p['id']==self.player(i)['id'])
   self.assertEqual(next(h['score'] for h in entry['history'] if h['day']==10),next(h['score'] for h in self.player(i)['state']['history'] if h['day']==10))
 def test_TIP_11_NFR_1_legacy_session_backup_and_pending_receipt(self):
  import hashlib
  from lan import Session,PROTOCOL
  m=self.message(0,'command',action='buy',args=dict(drug='hash',qty=1),revision=0)
  self.s.dispatch(m)
  receipt=hashlib.sha256(self.tokens[0].encode()).hexdigest()+':'+m['request_id']
  old=dict(m,protocol='bft-lan-3')
  self.s.s['receipts'][receipt]=hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()
  self.s.s.update(protocol='bft-lan-3',ruleset='bft-5')
  for p in self.s.s['players'].values():
   p['state']['ruleset']='bft-5'
   for field in ('tip_until_day','tip_cooldown_until','market_seed','entity_seq'):p['state'].pop(field,None)
  for field in ('options','seed','events','next_event_id'):self.s.s.pop(field,None)
  before=copy.deepcopy(self.s.s);self.s.commit();self.s.db.close();self.s=Session(self.path)
  backup=json.loads(self.path.with_suffix('.pre-v1.2.json').read_text(encoding='utf-8'))
  self.assertEqual(backup['protocol'],'bft-lan-3')
  for key,p in self.s.s['players'].items():
   for field in ('markets','black','clean','debt','inventory','history'):self.assertEqual(p['state'][field],before['players'][key]['state'][field])
   self.assertEqual(json.dumps(p['rng']),json.dumps(before['players'][key]['rng']))
   self.assertEqual(p['state']['tip_until_day'],0)
  self.assertEqual(self.s.s['options'],dict(allow_tips=False,shared_market=False))
  self.s.dispatch(m);self.assertEqual(self.player(0)['state']['inventory']['hash'],1)
  with self.assertRaisesRegex(ValueError,__import__('re').escape(__import__('game').VERSION)):self.s.dispatch(old)
  self.command(0,'wait');self.assertEqual(self.player(0)['state']['day'],2)
 def test_NFR_5_discovery_ports_and_match_require_both_identity_and_pin(self):
  from lan_discovery import PORT,reconnect_invite
  self.assertEqual(PORT,47653)
  c=dict(session='s'*32,invite='old|47652|'+'a'*64+'|saved-code')
  offer=dict(session=c['session'],fingerprint='a'*64,host='127.0.0.1',port=5555,started=True)
  for field,value in (('session','other'),('fingerprint','b'*64),('port',0),('host','evil|47652')):
   self.assertIsNone(reconnect_invite(c,[dict(offer,**{field:value})]),field)
  self.assertEqual(reconnect_invite(c,[offer]),'127.0.0.1|5555|'+'a'*64+'|saved-code')

if __name__=='__main__':unittest.main()

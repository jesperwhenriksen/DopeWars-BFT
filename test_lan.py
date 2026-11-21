import copy,json,secrets,tempfile,unittest,uuid
from pathlib import Path
from lan import Server,rpc,load_credentials,save_credentials
class LanTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.directory=Path(self.tmp.name);self.server=Server(self.directory,port=0,bind='127.0.0.1');self.invite=self.server.invite('127.0.0.1');self.a=secrets.token_hex(32);self.b=secrets.token_hex(32)
  self.call(self.a,'join',name='A',owner=self.server.session.s['owner']);self.call(self.b,'join',name='B')
 def tearDown(self):self.server.close();self.server.session.db.close();self.tmp.cleanup()
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
 def test_discovery_join_and_hide_started_lobby(self):
  from lan_discovery import scan
  found=scan(timeout=.25,hosts=['127.0.0.1'])
  entry=next(g for g in found if g['session']==self.server.session.s['id'])
  self.assertEqual(entry['players'],2);self.assertNotIn('owner',entry);self.assertNotIn('state',entry)
  c=secrets.token_hex(32)
  self.assertTrue(rpc(entry['invite'],dict(op='join',token=c,name='Found'))['ok'])
  self.call(c,'ready');self.start()
  self.assertFalse(any(g['session']==entry['session'] for g in scan(timeout=.25,hosts=['127.0.0.1'])))
 def test_discovery_stops_with_server(self):
  from lan_discovery import scan
  self.server.discovery.close()
  self.assertFalse(any(g['session']==self.server.session.s['id'] for g in scan(timeout=.25,hosts=['127.0.0.1'])))
if __name__=='__main__':unittest.main()

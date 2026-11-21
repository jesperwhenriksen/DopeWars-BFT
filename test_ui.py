import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QPushButton,QComboBox,QSpinBox
from PySide6.QtCore import QTimer
import app as ui
from game import new_game
from lan import save_credentials,load_credentials
from lan_ui import Lobby,Connection,LanWindow

class UIReleaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.q=QApplication.instance() or QApplication([]);ui.load_fonts();cls.q.setStyle('Fusion');cls.q.setStyleSheet(ui.STYLE)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=(ui.DATA,ui.SAVE,ui.SCORES);ui.DATA=Path(self.tmp.name);ui.SAVE=ui.DATA/'save.json';ui.SCORES=ui.DATA/'scores.json'
  self.g=new_game(seed=42);self.w=ui.Window(self.g);self.w.show();self.q.processEvents()
 def tearDown(self):
  if self.w.event_dialog:self.w.event_dialog.close()
  if self.w.panel:self.w.panel.close()
  self.w.close();self.q.processEvents();ui.DATA,ui.SAVE,ui.SCORES=self.old;self.tmp.cleanup()
 def test_market_selection_totals_and_icons(self):
  g=self.g;g.s['black']=10000;g.execute('buy',drug='hash',qty=2);g.execute('buy',drug='mdma',qty=2);self.w.render();self.q.processEvents()
  self.w.stock_table.selectRow(1);self.q.processEvents();self.assertEqual(self.w.sell_drug,'mdma')
  self.assertIn(ui.money(g.sell_quote('mdma')),self.w.sell_total.text())
  self.assertEqual(self.w.stock_table.item(0,2).text(),ui.average_cost(g.s['cost']['hash'],2))
  for i in range(6):self.assertFalse(self.w.market_table.item(i,0).icon().isNull())
 def test_same_day_sell_preview_shows_zero_loss(self):
  cash=self.g.s['black'];self.w.buy_btn.click();self.q.processEvents()
  self.assertIn('gevinst 0 kr.',self.w.sell_total.text())
  self.assertNotIn('5 %',self.w.sell_total.toolTip())
  self.assertIn(ui.money(self.g.quote('hash')),self.w.sell_btn.toolTip())
  self.w.sell_btn.click();self.q.processEvents();self.assertEqual(self.g.s['black'],cash)
 def test_earlier_highscores_remain_accessible_after_upgrade(self):
  import json
  record=dict(id='old',name='Gammel spiller',duration=31,score=12345,day=31,ruleset='bft-4')
  ui.SCORES.write_text(json.dumps([record]),encoding='utf-8')
  self.w.go(6);self.q.processEvents();body=self.w.panel_scroll.widget()
  rules=body.findChild(QComboBox,'score_ruleset');results=body.findChild(ui.QTableWidget)
  self.assertEqual(results.rowCount(),0);rules.setCurrentIndex(1)
  self.assertEqual(results.rowCount(),1);self.assertEqual(results.item(0,1).text(),'Gammel spiller')
  self.assertEqual(json.loads(ui.SCORES.read_text()),[record])
 def test_lan_does_not_reopen_police_while_command_pending_or_offline(self):
  from types import SimpleNamespace
  c=SimpleNamespace(view=dict(state=self.g.s,name='LAN'),c={'pending':{'op':'command'}},online=True)
  window=LanWindow(c,None);window.show();self.q.processEvents()
  with patch.object(ui.Window,'present_day_events') as show:
   window.present_day_events();show.assert_not_called()
   c.c={};c.online=False;window.present_day_events();show.assert_not_called()
   c.online=True;window.present_day_events();show.assert_called_once()
  window.hide();window.deleteLater();self.q.processEvents()
 def test_day_event_visible_only_once_despite_poll_refresh(self):
  self.g.s['day']=4
  with patch.object(self.g.rng,'random',return_value=1):self.w.act('wait')
  self.q.processEvents();dialog=self.w.event_dialog
  self.assertIsNotNone(dialog);self.assertTrue(dialog.isVisible())
  words=' '.join(x.text() for x in dialog.findChildren(ui.QLabel))
  event=self.g.s['day_events'][0]
  self.assertIn(event['title'],words);self.assertIn(ui.money(event['price']),words)
  for _ in range(4):self.w.present_day_events()
  self.assertIs(self.w.event_dialog,dialog)
  dialog.accept();self.q.processEvents();self.w.present_day_events()
  self.assertIsNone(self.w.event_dialog)
  self.w.buy_btn.click();self.q.processEvents();self.assertIsNone(self.w.event_dialog)
 def test_empty_police_stop_gets_visible_green_card(self):
  self.g.s['day']=6;self.g.s['last_market_event_day']=6
  with patch.object(self.g.rng,'random',return_value=1):self.w.act('wait')
  self.q.processEvents();self.assertTrue(self.g.s['green_card']);self.assertFalse(self.g.s['police'])
  words=' '.join(x.text() for x in self.w.event_dialog.findChildren(ui.QLabel))
  self.assertIn('Politiet stopper dig',words);self.assertIn('GREEN CARD',words)
 def test_market_notice_then_police_without_duplicate_dialogs(self):
  self.g.execute('buy',drug='hash',qty=1);self.g.s['day']=6
  def resolve():self.g.execute('police',choice='surrender')
  with patch.object(self.w,'police',side_effect=resolve) as police:
   with patch.object(self.g.rng,'random',return_value=1):self.w.act('wait')
   self.q.processEvents();self.assertIsNotNone(self.w.event_dialog);police.assert_not_called()
   self.w.event_dialog.accept();self.q.processEvents();self.w.present_day_events()
   police.assert_called_once();self.assertFalse(self.g.s['police'])
 def test_big_max_and_bank_control_not_wash_control(self):
  self.g.s.update(black=3_000_000_000,clean=9_000_000_000);self.w.go(3);self.q.processEvents()
  b=self.w.panel_scroll.widget();kind=b.findChild(QComboBox,'bank_kind');amount=b.findChild(ui.MoneySpinBox,'bank_amount');wash=b.findChild(ui.MoneySpinBox,'wash_amount')
  kind.setCurrentIndex(3);maximum=[x for x in amount.parent().findChildren(QPushButton) if x.text()=='Maks.'][0];maximum.click();self.assertEqual(amount.value(),9_000_000_000)
  amount.setValue(700);wash.setValue(123)
  submit=next(x for x in amount.parent().findChildren(QPushButton) if x.text()=='Gennemfør');submit.click();self.q.processEvents()
  self.assertEqual(self.g.s['clean'],9_000_000_000-700);self.assertEqual(self.g.s['black'],3_000_000_000+700)
 def test_zero_balances_and_completed_dialogs(self):
  self.g.s.update(black=0,clean=0,debt=0);self.w.render();self.q.processEvents();self.assertFalse(self.w.buy_btn.isEnabled());self.assertFalse(self.w.sell_btn.isEnabled())
  self.w.go(3);self.q.processEvents();b=self.w.panel_scroll.widget();wash=b.findChild(ui.MoneySpinBox,'wash_amount');self.assertEqual(wash.value(),0);self.assertFalse(wash.isEnabled())
  self.g.execute('finish');self.w.render()
  for page in range(1,10):
   self.w.go(page);self.q.processEvents();self.assertTrue(self.w.panel_scroll.widget().isVisible());self.w.panel.close()
 def test_mule_and_asset_maximum_capacity(self):
  g=self.g;g.s.update(black=100000,clean=10000);g.execute('hire',city='Aarhus',tier=0);g.execute('buy',drug='hash',qty=10);g.s['mules'][0]['inventory']['mdma']=495
  self.w.go(4);self.q.processEvents();b=self.w.panel_scroll.widget();maxi=next(x for x in b.findChildren(QPushButton) if x.text()=='Maks.');maxi.click();self.assertEqual(b.findChild(QSpinBox).value(),5)
  g.execute('asset',tier=0);aid=g.s['assets'][0]['id'];g.execute('fund',aid=aid,amount=4500)
  self.w.go(5);self.q.processEvents();b=self.w.panel_scroll.widget();next(x for x in b.findChildren(QPushButton) if x.text()=='Maks.').click();self.assertEqual(b.findChild(ui.MoneySpinBox).value(),500)
 def test_late_connection_events_ignored(self):
  lobby=Lobby();lobby.browsing=False;lobby.search_timer.stop()
  c1=Connection({'token':'a'*64,'invite':'127.0.0.1|1|'+'b'*64+'|c'},ui.DATA/'a');c1.timer.stop()
  c2=Connection({'token':'b'*64,'invite':'127.0.0.1|1|'+'b'*64+'|c'},ui.DATA/'b');c2.timer.stop();lobby.controller=c2
  lobby.received(c1,({}, {'ok':True,'view':{'started':True}}));lobby.failed(c1,'late')
  self.assertIs(lobby.controller,c2);self.assertIsNone(c2.view);self.assertIsNone(lobby.window)
  c1.stop();lobby.close()
 def test_failed_join_keeps_prior_session_and_archive(self):
  lobby=Lobby();lobby.browsing=False;lobby.search_timer.stop()
  old=dict(token='a'*64,invite='127.0.0.1|1|'+'b'*64+'|c',name='Old',session='session-old')
  save_credentials(lobby.path,old)
  new=dict(token='b'*64,invite=old['invite'],name='New',pending=dict(op='join',name='New'))
  with patch.object(Connection,'tick',return_value=None):lobby.begin(new)
  self.assertEqual(load_credentials(lobby.path),old)
  self.assertTrue(any(c['token']==old['token'] for _,c in lobby.saved_connections()))
  lobby.cancel();lobby.close()
 def test_poll_race_keeps_queued_command(self):
  lobby=Lobby();lobby.browsing=False;lobby.search_timer.stop()
  creds=dict(token='c'*64,invite='127.0.0.1|1|'+'b'*64+'|c')
  c=Connection(creds,ui.DATA/'c');c.timer.stop();lobby.controller=c
  view=dict(session='x',name='Lobby',days=31,complete=False,started=False,players=[dict(id='p',name='P',owner=False,ready=False,online=True)],me='p',revision=0,state=None)
  c.view=copy.deepcopy(view)
  with patch.object(Connection,'tick',return_value=None):
   c.busy=True;c.send('ready');pending=copy.deepcopy(c.c['pending']);lobby.received(c,({'op':'poll'},dict(ok=True,view=view)));self.assertEqual(c.c['pending'],pending)
   lobby.received(c,(dict(pending,token=c.c['token']),dict(ok=True,view=view)));self.assertNotIn('pending',c.c)
  lobby.close();self.q.processEvents()
 def test_TIP_7_same_day_tip_notice_without_replaying_market(self):
  self.g.s['day']=4
  with patch.object(self.g.rng,'random',return_value=1):self.w.act('wait')
  self.q.processEvents();market=self.g.s['day_events'][0]['title']
  self.w.event_dialog.accept();self.q.processEvents()
  self.g.s['tip_until_day']=10
  self.g.s['day_events'].append(dict(kind='tip',title='Politiet har fået et tip',text='Tippet til dag 10',day=5))
  self.w.render();self.w.present_day_events();self.q.processEvents()
  words=' '.join(x.text() for x in self.w.event_dialog.findChildren(ui.QLabel))
  self.assertIn('Politiet har fået et tip',words);self.assertNotIn(market,words);self.assertNotIn('GREEN CARD',words)
  self.assertIn('Tippet til dag 10',next(x for x in self.w.findChildren(ui.QLabel,'police_risk') if x.isVisible()).text())
  self.w.event_dialog.accept();self.q.processEvents();self.w.present_day_events();self.assertIsNone(self.w.event_dialog)
 def test_BAL_1_risk_preview_and_BAL_4_mule_explanation(self):
  self.g.s.update(heat=65,tip_until_day=6);self.w.render();self.q.processEvents()
  self.assertIn('62 %',next(x for x in self.w.findChildren(ui.QLabel,'police_risk') if x.isVisible()).text())
  self.g.s['black']=10000;self.g.execute('hire',city='Aarhus',tier=0)
  self.g.s['mules'][0]['inventory']['hash']=500
  self.w.go(4);self.q.processEvents()
  words=' '.join(x.text() for x in self.w.panel_scroll.widget().findChildren(ui.QLabel))
  self.assertIn('2,60 %',words)
 def test_TIP_9_lobby_defaults_and_started_sessions_filtered(self):
  lobby=Lobby();lobby.search_timer.stop()
  self.assertFalse(lobby.allow_tips.isChecked());self.assertTrue(lobby.shared_market.isChecked())
  opts=dict(allow_tips=True,shared_market=False)
  offer=dict(session='s',name='Test',days=31,players=2,options=opts,started=False,invite='test')
  lobby.browsing=True;lobby.found([offer,dict(offer,session='running',started=True)])
  self.assertEqual(lobby.games.count(),1);self.assertIn('Politi-tip: til',lobby.games.currentText())
  self.assertIn('Fælles marked: fra',lobby.games.currentText());lobby.close()
 def test_BAL_6_LAN_2_3_tip_controls_and_day_comparison(self):
  from types import SimpleNamespace
  players=[dict(id='me',name='A',day=10,score=900,history=[dict(day=10,score=900)],online=True,finished=False),
           dict(id='b',name='B',day=15,score=4000,history=[dict(day=10,score=700)],online=True,finished=False),
           dict(id='c',name='C',day=5,score=1000,history=[dict(day=5,score=1000)],online=False,finished=False)]
  view=dict(state=self.g.s,name='Test',days=31,complete=False,players=players,me='me',options=dict(allow_tips=True,shared_market=True),
            events=[dict(id=1,type='tip',player_id='b',data={})])
  c=SimpleNamespace(view=view,c={},online=True)
  w=LanWindow(c,SimpleNamespace(server=None));w.show();w.go(6);self.q.processEvents()
  body=w.panel_scroll.widget();body.findChild(QSpinBox,'compare_day').setValue(10);self.q.processEvents()
  body=w.panel_scroll.widget();table=body.findChild(ui.QTableWidget,'lan_standings')
  self.assertEqual([table.item(r,1).text() for r in range(3)],['A','B','C'])
  self.assertEqual(table.item(1,3).text(),'700 kr.');self.assertEqual(table.item(2,0).text(),'—')
  self.assertEqual(table.item(2,3).text(),'Ikke nået')
  self.assertIsNotNone(body.findChild(QPushButton,'tip_button'))
  from PySide6.QtWidgets import QListWidget
  self.assertIn('Nogen har tippet politiet om B',body.findChild(QListWidget,'lan_activity').item(0).text())
  w.panel.close();w.hide();w.deleteLater();self.q.processEvents()
 def test_LAN_3_2_unchanged_reply_restores_connection_status(self):
  lobby=Lobby();lobby.browsing=False;lobby.search_timer.stop()
  c=Connection(dict(token='x'*64,invite='127.0.0.1|1|'+'a'*64+'|code'),ui.DATA/'c');c.timer.stop();lobby.controller=c;lobby.window=self.w
  c.online=False;c.view={'revision':0};self.w.main.setEnabled(False);self.w.statusBar().showMessage('Genforbinder…')
  lobby.received(c,({'op':'poll'},dict(ok=True,view=dict(unchanged=True))))
  self.assertTrue(self.w.main.isEnabled());self.assertIn('Forbundet igen',self.w.statusBar().currentMessage());lobby.close()

 def test_TIP_7_open_police_dialog_updates_when_tip_arrives(self):
  self.g.s['inventory']['hash']=25;self.g.s['police']=True;observed=[]
  def remote_tip():
   self.g.s['tip_until_day']=6;self.w.render();d=self.w.police_dialog
   observed.extend([d.findChild(ui.QLabel,'police_chances').text(),d.findChild(ui.QLabel,'police_tip').text(),d.findChild(ui.QLabel,'police_tip').isVisible()]);d.accept()
  with patch.object(self.w,'act') as act:
   QTimer.singleShot(0,remote_tip);self.w.police();act.assert_called_once_with('police',choice='surrender')
  self.assertIn('Flugtchance: 35 %',observed[0]);self.assertIn('Tippet til dag 6',observed[1]);self.assertTrue(observed[2])
 def test_LAN_2_2_host_dnf_closes_police_without_extra_command(self):
  self.g.s['inventory']['hash']=1;self.g.s['police']=True
  def remote_dnf():self.g.s.update(finished=True,police=False);self.w.render()
  with patch.object(self.w,'act') as act:
   QTimer.singleShot(0,remote_dnf);self.w.police();act.assert_not_called()
  self.assertIsNone(self.w.police_dialog)

if __name__=='__main__':unittest.main()

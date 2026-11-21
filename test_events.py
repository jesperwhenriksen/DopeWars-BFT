"""Market round trips, event cadence and saved-session upgrade regressions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from game import (Game, new_game, DRUGS, CITIES, MARKET_EVENTS, RULESET,
                  MARKET_EVENT_MAX_GAP, POLICE_MAX_GAP, RuleError)
from lan import Session, PROTOCOL

EVENT_FIELDS = ('day_events', 'market_event_detail', 'last_market_event_day', 'last_police_day')


def legacy_state(state):
    state['ruleset'] = 'bft-4'
    for key in EVENT_FIELDS:
        state.pop(key, None)
    return state


class MarketEventTests(unittest.TestCase):
    def test_zero_difference_for_every_drug_and_market(self):
        for seed in (1, 42, 123):
            g = new_game(seed=seed)
            g.s['black'] = 100000
            prices = copy.deepcopy(g.s['markets'])
            rng = g.rng.getstate()
            for city in CITIES:
                for district in range(6):
                    g.s.update(city=city, district=district)
                    for drug in DRUGS:
                        cash = g.s['black']
                        g.execute('buy', drug=drug, qty=3)
                        g.execute('sell', drug=drug, qty=1)
                        g.execute('sell', drug=drug, qty=2)
                        self.assertEqual(g.s['black'], cash, (city, district, drug))
                        self.assertEqual(g.s['cost'][drug], 0)
            self.assertEqual(g.s['markets'], prices)
            self.assertEqual(g.rng.getstate(), rng)
            self.assertEqual(g.s['day'], 1)

    def test_sale_uses_new_day_price_and_preserves_average_cost(self):
        g = new_game(seed=18)
        g.s['black'] = 100000
        first = g.quote('hash')
        g.execute('buy', drug='hash', qty=2)
        with patch.object(g.rng, 'random', return_value=1):
            g.execute('travel', city='Randers', district=1)
        second = g.quote('hash')
        self.assertNotEqual(first, second)
        g.execute('buy', drug='hash', qty=2)
        self.assertEqual(g.s['cost']['hash'], 2 * first + 2 * second)
        cash = g.s['black']
        g.execute('sell', drug='hash', qty=1)
        self.assertEqual(g.s['black'] - cash, second)
        self.assertEqual(g.s['cost']['hash'], 3 * (first + second) // 2 + (first + second) % 2)

    def test_price_crashes_and_spikes_are_real_trade_prices(self):
        for event in MARKET_EVENTS:
            g = new_game(seed=5)
            g.s.update(day=4, black=100000)
            with patch.object(g.rng, 'uniform', return_value=1), \
                 patch.object(g.rng, 'random', return_value=1), \
                 patch.object(g.rng, 'choice', side_effect=['hash', event]):
                g.execute('wait')
            detail = g.s['day_events'][0]
            self.assertEqual(detail['kind'], 'market')
            self.assertEqual(detail['price'], round(detail['before'] * event[1]))
            self.assertEqual(g.quote('hash'), detail['price'])
            self.assertEqual(g.sell_quote('hash'), detail['price'])
            cash = g.s['black']
            g.execute('buy', drug='hash', qty=4)
            g.execute('sell', drug='hash', qty=4)
            self.assertEqual(g.s['black'], cash)
            g.execute('wait')
            self.assertTrue(all(e['day'] == g.s['day'] for e in g.s['day_events']))

    def test_31_days_cannot_pass_without_events_even_with_bad_rolls(self):
        g = new_game(seed=2)
        police_days, market_days = [1], [1]
        with patch.object(g.rng, 'random', return_value=1):
            for _ in range(30):
                g.execute('wait')
                for event in g.s['day_events']:
                    if event['kind'] == 'market':
                        market_days.append(g.s['day'])
                    else:
                        police_days.append(g.s['day'])
                        self.assertTrue(g.s['green_card'])
                self.assertLessEqual(g.s['day'] - market_days[-1], MARKET_EVENT_MAX_GAP)
                self.assertLessEqual(g.s['day'] - police_days[-1], POLICE_MAX_GAP)
        self.assertGreaterEqual(len(police_days) - 1, 5)
        self.assertGreaterEqual(len(market_days) - 1, 7)
        self.assertLessEqual(max(b-a for a, b in zip(police_days, police_days[1:])), 6)
        self.assertLessEqual(max(b-a for a, b in zip(market_days, market_days[1:])), 4)

    def test_controls_with_goods_block_trading_until_resolved(self):
        g = new_game(seed=4)
        g.s['black'] = 100000
        stops = 0
        with patch.object(g.rng, 'random', return_value=1):
            for _ in range(30):
                if not g.used:
                    g.execute('buy', drug='hash', qty=1)
                g.execute('wait')
                if g.s['police']:
                    stops += 1
                    before = copy.deepcopy(g.s)
                    with self.assertRaises(RuleError):
                        g.execute('sell', drug='hash', qty=1)
                    self.assertEqual(g.s, before)
                    g.execute('police', choice='surrender')
                    self.assertFalse(g.s['police'])
        self.assertGreaterEqual(stops, 5)

    def test_save_reload_preserves_events_and_future_randomness(self):
        g = new_game(seed=8)
        for _ in range(6):
            g.execute('wait')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'save.json'
            g.save(path)
            restored = Game.load(path)
        self.assertEqual(g.s, restored.s)
        self.assertEqual(g.rng.getstate(), restored.rng.getstate())
        for _ in range(10):
            g.execute('wait'); restored.execute('wait')
            self.assertEqual(g.s, restored.s)
            self.assertEqual(g.rng.getstate(), restored.rng.getstate())

    def test_upgrade_v1_save_keeps_prices_money_inventory_and_rng(self):
        g = new_game(seed=8)
        g.s['day'] = 17
        g.execute('buy', drug='hash', qty=2)
        original = legacy_state(copy.deepcopy(g.s))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'save.json'
            path.write_text(json.dumps(dict(state=original, rng=g.rng.getstate())), encoding='utf-8')
            restored = Game.load(path)
        for key, value in original.items():
            if key != 'ruleset':
                self.assertEqual(restored.s[key], value, key)
        self.assertEqual(restored.rng.getstate(), g.rng.getstate())
        self.assertEqual(restored.s['ruleset'], RULESET)
        self.assertEqual(restored.s['last_police_day'], 17)
        self.assertEqual(restored.s['last_market_event_day'], 17)
        self.assertEqual(restored.s['day_events'], [])

    def test_upgrade_lan_sessions_with_backup_and_unchanged_randomness(self):
        for old_protocol in ('bft-lan-1', 'bft-lan-2'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'session.sqlite'
                session = Session(path)
                g = new_game(seed=8)
                g.s['day'] = 17
                session.s.update(protocol=old_protocol, ruleset='bft-4', started=True)
                session.s['players'] = {'player': dict(state=legacy_state(copy.deepcopy(g.s)), rng=g.rng.getstate(), revision=17)}
                original = copy.deepcopy(session.s)
                session.commit(); session.db.close()
                session = Session(path)
                self.assertEqual(session.s['protocol'], PROTOCOL)
                self.assertEqual(session.s['ruleset'], RULESET)
                p = session.s['players']['player']
                self.assertEqual(p['state']['markets'], original['players']['player']['state']['markets'])
                self.assertEqual(session.game(p).rng.getstate(), g.rng.getstate())
                self.assertEqual(p['revision'], 17)
                backup = json.loads(path.with_suffix('.pre-v1.2.json').read_text(encoding='utf-8'))
                self.assertEqual(backup['protocol'], old_protocol)
                self.assertEqual(backup['ruleset'], 'bft-4')
                with self.assertRaisesRegex(ValueError, 'LAN-version'):
                    session.dispatch(dict(op='poll', protocol=old_protocol))
                session.db.close()


class CompatibilityAndDocsTests(unittest.TestCase):
    def test_TIP_11_NFR_1_bft5_save_backup_preserves_existing_orders(self):
        g=new_game(seed=8);g.s.update(black=20000,clean=5000)
        g.execute('asset',tier=0);g.execute('fund',aid=g.s['assets'][0]['id'],amount=1000)
        g.execute('wash',amount=1000,tier=0)
        old=copy.deepcopy(g.s);old['ruleset']='bft-5';old['assets'][0]['queue'][0]['payout']=750
        for key in ('tip_until_day','tip_cooldown_until','market_seed','entity_seq'):old.pop(key)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';path.write_text(json.dumps(dict(state=old,rng=g.rng.getstate())),encoding='utf-8')
            upgraded=Game.load(path)
            for key in ('markets','black','clean','debt','assets','mules','washing','history','inventory','cost','day'):
                self.assertEqual(upgraded.s[key],old[key],key)
            self.assertEqual(upgraded.rng.getstate(),g.rng.getstate())
            self.assertEqual(upgraded.s['tip_until_day'],0);self.assertFalse(upgraded.tip_active)
            backup=path.with_suffix('.pre-v1.2.json');original_backup=backup.read_bytes()
            self.assertEqual(json.loads(original_backup)['state'],old)
            upgraded.execute('wait');upgraded.save(path);Game.load(path)
            self.assertEqual(backup.read_bytes(),original_backup)
            for value in (-1,True,1.1):
                upgraded.s['tip_until_day']=value
                with self.assertRaises(RuleError):upgraded.check()

    def test_TIP_12_NFR_6_7_distribution_documents_and_build_options(self):
        import sys
        from game import VERSION
        root=(Path(sys.executable).parent/'source') if getattr(sys,'frozen',False) else Path(__file__).parent
        for name in ('README.md','LAN-LAES-MIG.txt','LAES-MIG.txt','BUILD.txt','RELEASE-NOTES.txt'):
            text=(root/name).read_text(encoding='utf-8')
            self.assertIn(VERSION,text,name)
        for name in ('README.md','LAN-LAES-MIG.txt'):
            text=(root/name).read_text(encoding='utf-8').lower()
            for word in ('politi-tip','fælles','spildag','certifikat','firewall'):self.assertIn(word,text,name)
        build=(root/'build.ps1').read_text(encoding='utf-8')
        for name in ('simulate_balance.py','benchmark_lan.py','release-self-test','self-test','installer.iss'):self.assertIn(name,build)
        for name in ('simulate_balance.py','benchmark_lan.py','SPEC-STATUS.md','DopeWars-BFT-SPEC.md','BALANCE-1.2.json','LAN-YDELSE.json'):
            self.assertTrue((root/name).is_file(),name)
        self.assertIn('"'+VERSION+'"',(root/'installer.iss').read_text(encoding='utf-8'))
        self.assertIn("'"+VERSION+"'",(root/'version_info.txt').read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()

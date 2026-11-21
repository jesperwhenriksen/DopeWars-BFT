import copy
import tempfile
import unittest
from pathlib import Path
from game import *


class GameTests(unittest.TestCase):
    def setUp(self):
        self.g = new_game(city='København',seed=42)

    def test_durations_and_maximum(self):
        for d in DURATIONS:
            g = new_game(days=d, seed=1)
            for _ in range(d-1):
                g.execute('wait')
            self.assertEqual(g.s['day'],d)
            self.assertFalse(g.s['finished'])
            g.execute('wait')
            self.assertTrue(g.s['finished'])
            with self.assertRaises(RuleError):g.execute('wait')
        with self.assertRaises(RuleError):new_game(days=366)

    def test_loan_is_black_cash_with_debt(self):
        before=self.g.score
        self.g.execute('bank',kind='borrow',amount=4000)
        self.assertEqual(self.g.s['black'],6000)
        self.assertEqual(self.g.s['clean'],0)
        self.assertEqual(self.g.score,before-4000)
        self.g.execute('bank',kind='repay_black',amount=4000)
        self.assertEqual(self.g.score,before)

    def test_compound_interest(self):
        self.g.execute('wait')
        self.assertEqual(self.g.s['debt'],5583)
        self.g.execute('wait')
        self.assertEqual(self.g.s['debt'],5667)

    def test_black_assets_excluded(self):
        before=self.g.score
        self.g.s['black']+=100000
        self.g.s['stash']+=100000
        self.g.s['inventory']['hash']=50
        self.assertEqual(before,self.g.score)
        self.assertNotIn('black',self.g.public_score())

    def test_negative_and_fractional_amounts(self):
        before=copy.deepcopy(self.g.s)
        for n in (-1,0,True,1.2):
            with self.assertRaises(RuleError):self.g.execute('bank',kind='borrow',amount=n)
        self.assertEqual(before,self.g.s)

    def test_failed_purchase_is_atomic(self):
        before=copy.deepcopy(self.g.s)
        with self.assertRaises(RuleError):self.g.execute('buy',drug='hash',qty=51)
        self.assertEqual(before,self.g.s)
        with self.assertRaises(RuleError):self.g.execute('buy',drug='cocaine',qty=50)
        self.assertEqual(before,self.g.s)

    def test_buy_sell_has_zero_spread(self):
        price=self.g.quote('hash')
        self.g.execute('buy',drug='hash',qty=2)
        self.g.execute('sell',drug='hash',qty=2)
        self.assertEqual(self.g.s['black'],2000)
        self.assertEqual(self.g.s['cost']['hash'],0)

    def test_direct_deposit_rejected(self):
        before=copy.deepcopy(self.g.s)
        with self.assertRaises(RuleError):self.g.execute('bank',kind='deposit',amount=1000)
        self.assertEqual(self.g.s,before)

    def test_clean_to_black_lowers_score(self):
        self.g.s['clean']=1000
        before=self.g.score
        self.g.execute('bank',kind='to_black',amount=1000)
        self.assertEqual(self.g.score,before-1000)

    def test_asset_queue_delay_fee_capacity(self):
        g=self.g
        g.s['clean']=3000
        g.s['black']=4000
        g.execute('asset',tier=0)
        aid=g.s['assets'][0]['id']
        g.execute('fund',aid=aid,amount=1000)
        g.execute('wait')
        self.assertEqual(g.s['clean'],10)  # Only operating income on day 2.
        g.execute('wait')
        self.assertEqual(g.s['clean'],460)  # BAL-3: 440 converted + 20 income.
        g.execute('wait')
        self.assertEqual(g.s['clean'],910)
        self.assertEqual(g.s['assets'][0]['queue'],[])

    def test_queue_capacity_shared_between_orders(self):
        g=self.g
        g.s['clean']=3000
        g.s['black']=5000
        g.execute('asset',tier=0)
        aid=g.s['assets'][0]['id']
        for _ in range(3):g.execute('fund',aid=aid,amount=500)
        g.execute('wait');g.execute('wait')
        self.assertEqual(sum(o['remaining'] for o in g.s['assets'][0]['queue']),1000)
        with self.assertRaises(RuleError):g.execute('sell_asset',aid=aid)

    def test_asset_resale_score_neutral(self):
        g=self.g;g.s['clean']=3000;g.execute('asset',tier=0)
        before=g.score
        g.execute('sell_asset',aid=g.s['assets'][0]['id'])
        self.assertEqual(g.score,before)

    def test_mule_transfers_no_duplication(self):
        g=self.g;g.s['black']=10000
        g.execute('hire',city='Aarhus',tier=0)
        g.execute('buy',drug='hash',qty=10)
        mid=g.s['mules'][0]['id']
        g.execute('dispatch',mid=mid,drug='hash',qty=10)
        self.assertEqual(g.used,0)
        self.assertEqual(g.s['mules'][0]['inventory']['hash'],10)
        g.execute('wait')
        self.assertEqual(g.s['mules'][0]['inventory']['hash'],5)
        self.assertGreater(g.s['mules'][0]['earned'],0)
        with self.assertRaises(RuleError):g.execute('dismiss',mid=mid)

    def test_mules_must_start_in_other_city(self):
        with self.assertRaises(RuleError):self.g.execute('hire',city='København',tier=0)

    def test_mule_relapse_loses_goods_and_pauses(self):
        from unittest.mock import patch
        g=self.g
        g.execute('hire',city='Aarhus',tier=0)
        m=g.s['mules'][0];m['inventory']['hash']=20
        with patch.object(g.rng,'random',return_value=0):g.execute('wait')
        self.assertEqual(m['inventory']['hash'],15)
        self.assertEqual(m['cooldown'],2)
        for _ in range(2):g.execute('wait')
        self.assertEqual(m['inventory']['hash'],15)

    def test_death_finishes_and_preserves_score(self):
        from unittest.mock import patch
        g=self.g;g.s['inventory']['hash']=1;g.s['police']=True;g.s['health']=1;g.s['clean']=1200
        score=g.score
        with patch.object(g.rng,'random',return_value=.99):g.execute('police',choice='fight')
        self.assertTrue(g.s['finished'])
        self.assertEqual(g.s['health'],0)
        self.assertEqual(g.score,score)

    def test_bag_and_weapon_upgrade_costs(self):
        g=self.g;g.s['black']=10000
        g.execute('bag',tier=1);g.execute('weapon',tier=1)
        self.assertEqual(g.capacity,100)
        self.assertEqual(g.s['weapon'],1)
        self.assertEqual(g.s['black'],6100)
        with self.assertRaises(RuleError):g.execute('bag',tier=1)

    def test_police_preserves_legal_assets(self):
        g=self.g;g.s['clean']=500;g.s['stash']=2000
        g.execute('buy',drug='hash',qty=2)
        score=g.score;g.s['police']=True
        with self.assertRaises(RuleError):g.execute('bank',kind='deposit',amount=100)
        g.execute('police',choice='surrender')
        self.assertEqual(g.used,0)
        self.assertEqual(g.score,score)
        self.assertEqual(g.s['stash'],2000)

    def test_save_preserves_future_rng(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json'
            self.g.save(path)
            restored=Game.load(path)
            self.g.execute('wait');restored.execute('wait')
            self.assertEqual(self.g.s,restored.s)

    def test_city_data_bounds_and_randers(self):
        for c in CITIES:
            for k in DRUGS:self.assertTrue(.8<=demand(c,k)<=1.25)
        self.assertEqual(demand('Randers','amphetamine'),1)
        self.assertGreater(demand('Esbjerg','amphetamine'),demand('København','amphetamine'))

    def test_same_location_cannot_reroll(self):
        before=copy.deepcopy(self.g.s)
        with self.assertRaises(RuleError):self.g.execute('travel',city='København',district=0)
        self.assertEqual(before,self.g.s)

    def test_random_legal_actions_never_break_invariants(self):
        for seed in range(12):
            g=new_game(seed=seed,days=365)
            for day in range(100):
                if g.s['finished']:break
                if g.s['police']:g.execute('police',choice='surrender')
                for k in DRUGS:
                    if g.s['inventory'][k]:g.execute('sell',drug=k,qty=g.s['inventory'][k])
                affordable=[k for k in DRUGS if g.quote(k)<=g.s['black']]
                if affordable:
                    k=min(affordable,key=lambda k:g.quote(k)/DRUGS[k][1])
                    qty=min(g.capacity,g.s['black']//g.quote(k))
                    g.execute('buy',drug=k,qty=qty)
                g.execute('wait')
                g.check()

    def test_purchases_only_spend_cash(self):
        g=self.g;g.s['black']=0;g.s['clean']=1000
        with self.assertRaises(RuleError):g.execute('buy',drug='hash',qty=1)
        g.execute('bank',kind='borrow',amount=1000)
        g.execute('buy',drug='hash',qty=1)
        self.assertEqual(g.s['clean'],1000)

    def test_wash_fee_delay_score_and_save(self):
        from unittest.mock import patch
        for tier,(_,fee,low,high) in enumerate(WASH_OPTIONS):
            for delay in (low,high):
                g=new_game(seed=42)
                score=g.score
                with patch.object(g.rng,'randint',return_value=delay):g.execute('wash',amount=1000,tier=tier)
                self.assertEqual(g.score,score)
                self.assertEqual(g.s['black'],1000)
                with tempfile.TemporaryDirectory() as d:
                    path=Path(d)/'s.json';g.save(path);g=Game.load(path)
                self.assertEqual(g.s['washing'][0]['ready'],1+delay)
                for _ in range(delay-1):g.execute('wait')
                self.assertEqual(g.s['clean'],0)
                g.execute('wait')
                self.assertEqual(g.s['clean'],1000*(100-fee)//100)
                self.assertEqual(g.s['washing'],[])
                g.execute('wait')
                self.assertEqual(g.s['clean'],1000*(100-fee)//100)

    def test_wash_failure_rolls_back_and_finished_queue_excluded(self):
        g=self.g;before=copy.deepcopy(g.s);rng=g.rng.getstate()
        with self.assertRaises(RuleError):g.execute('wash',amount=5000,tier=0)
        self.assertEqual(g.s,before);self.assertEqual(g.rng.getstate(),rng)
        g.execute('wash',amount=1000,tier=0);score=g.score
        g.execute('finish');self.assertEqual(g.score,score);self.assertEqual(g.s['clean'],0)

    def test_empty_stop_grants_one_card_without_penalty(self):
        from unittest.mock import patch
        g=self.g;cash=g.s['black']
        with patch.object(g.rng,'random',return_value=0):
            g.execute('wait');g.execute('wait')
        self.assertIs(g.s['green_card'],True)
        self.assertFalse(g.s['police'])
        self.assertEqual(g.s['black'],cash)
        self.assertEqual(g.s['health'],100)

    def test_card_outcomes_at_exact_half_boundary(self):
        from unittest.mock import patch
        for roll,success in [(0.4999,True),(0.5,False)]:
            g=new_game(seed=42);g.execute('buy',drug='hash',qty=2)
            g.s['green_card']=True;g.s['police']=True
            cash=g.s['black'];score=g.score
            with patch.object(g.rng,'random',return_value=roll):
                g.execute('police',choice='explain')
            self.assertFalse(g.s['green_card']);self.assertFalse(g.s['police'])
            self.assertEqual(g.used,2 if success else 0)
            self.assertEqual(g.s['black'],cash if success else cash-cash//4)
            self.assertEqual(g.s['health'],100);self.assertEqual(g.score,score)

    def test_explain_without_card_rolls_back(self):
        g=self.g;g.execute('buy',drug='hash',qty=1);g.s['police']=True
        before=copy.deepcopy(g.s);rng=g.rng.getstate()
        with self.assertRaises(RuleError):g.execute('police',choice='explain')
        self.assertEqual(g.s,before);self.assertEqual(g.rng.getstate(),rng)

    def test_old_save_migrates_and_card_persists(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';self.g.save(path)
            data=json.loads(path.read_text(encoding='utf-8'))
            data['state'].pop('green_card');data['state']['ruleset']='bft-1'
            path.write_text(json.dumps(data),encoding='utf-8')
            g=Game.load(path);self.assertFalse(g.s['green_card'])
            self.assertEqual(g.s['ruleset'],RULESET)
            g.s['green_card']=True;g.save(path)
            self.assertTrue(Game.load(path).s['green_card'])

    def test_city_areas_and_travel(self):
        for city in CITIES:
            self.assertEqual(len(DISTRICTS[city]),6)
            self.assertEqual(len(set(DISTRICTS[city])),6)
            g=new_game(city=city,seed=42)
            g.execute('travel',city=city,district=1)
            self.assertEqual(g.s['district'],1)
            self.assertIn(DISTRICTS[city][1],g.s['log'][0])
        self.assertIn('Randers Storcenter',DISTRICTS['Randers'])

    def test_fictional_area_factor_applied_to_prices(self):
        from unittest.mock import patch
        g=new_game(seed=42)
        with patch.object(g.rng,'uniform',return_value=1), patch.object(g.rng,'random',return_value=1):
            g.roll_markets()
        self.assertEqual(g.quote('hash','København',1),round(150*demand('København','hash')*.72))
        self.assertEqual(g.quote('hash','København',0),round(150*demand('København','hash')))
        self.assertEqual(area_factor('København',1,'cocaine'),1)

    def test_default_start_is_hoeje(self):
        self.assertEqual(new_game().s['city'],'Høje på Fyn')
        self.assertEqual(demand('Høje på Fyn','hash'),1)

    def test_old_save_gains_hoeje_market_without_reroll(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';self.g.save(path)
            data=json.loads(path.read_text(encoding='utf-8'))
            data['state']['markets'].pop('Høje på Fyn')
            path.write_text(json.dumps(data),encoding='utf-8')
            g=Game.load(path)
            self.assertEqual(g.s['markets']['København'],self.g.s['markets']['København'])
            self.assertEqual(g.rng.getstate(),self.g.rng.getstate())
            self.assertGreater(g.quote('hash','Høje på Fyn',0),0)


class SpecBalanceTests(unittest.TestCase):
    def test_TIP_1_singleplayer_cannot_tip(self):
        with self.assertRaises(RuleError):new_game(seed=1).execute('tip', target='anyone')

    def test_TIP_4_and_BAL_1_risk_expiry_and_next_day_preview(self):
        from unittest.mock import patch
        for day, expected in ((5,.38),(6,.38),(7,.18)):
            g=new_game(seed=1);g.s.update(day=day-1,last_police_day=day-1,tip_until_day=6)
            self.assertAlmostEqual(g.police_risk(next_day=True),expected)
            with patch.object(g,'roll_markets'), patch.object(g.rng,'random',return_value=.28):
                g.execute('wait')
            self.assertEqual(g.s['last_police_day']==day,day<=6)
        g.s.update(heat=65,last_police_day=g.s['day'])
        self.assertAlmostEqual(g.police_risk(next_day=True),.18+60/250)
        g.s['last_police_day']=g.s['day']-5
        self.assertEqual(g.police_risk(next_day=True),1)

    def test_TIP_5_escape_threshold_green_card_and_fight_unchanged(self):
        from unittest.mock import patch
        for qty in (1,25,50):
            normal=.65-.2*qty/50
            for tipped in (False,True):
                chance=max(.15,normal-(.2 if tipped else 0))
                for choice,threshold in (('run',chance),('fight',.58),('explain',.5)):
                    for roll,success in ((threshold-.00001,True),(threshold,False)):
                        g=new_game(seed=8);g.s.update(police=True,green_card=True,weapon=1,tip_until_day=6 if tipped else 0)
                        g.s['inventory']['hash']=qty
                        self.assertAlmostEqual(g.run_chance,chance)
                        with patch.object(g.rng,'random',return_value=roll):g.execute('police',choice=choice)
                        self.assertEqual(g.used,qty if success else 0,(qty,tipped,choice,roll))

    def test_TIP_6_failed_tipped_escape_is_half_damage_and_nonlethal(self):
        from unittest.mock import patch
        for health,expected in ((100,77),(10,1),(1,1)):
            g=new_game(seed=1);g.s.update(health=health,police=True,tip_until_day=6)
            g.s['inventory']['hash']=1
            with patch.object(g.rng,'random',return_value=.99),patch.object(g.rng,'randint',return_value=45):
                g.execute('police',choice='run')
            self.assertEqual(g.s['health'],expected);self.assertFalse(g.s['finished'])

    def test_BAL_1_TIP_4_10000_day_measurement(self):
        from simulate_balance import police_sample
        normal=police_sample();tip=police_sample(tipped=True)
        self.assertTrue(.24<normal['rate']<.28,normal)
        self.assertTrue(.38<tip['rate']<.43,tip)
        self.assertGreater(police_sample(heat=60)['rate'],police_sample(heat=5)['rate']+.1)

    def test_BAL_2_each_affordable_weapon_has_a_use(self):
        # Compare the owned/affordable weapon against flight. A cheaper weapon
        # cannot rationally beat an already owned rifle with these fixed rules.
        for tier in (1,2,3):
            self.assertTrue(any(WEAPONS[tier][2]>.65-.2*fill for fill in (0,.25,.5,.75,1)))
        self.assertGreater(.65,WEAPONS[1][2])
        self.assertGreater(WEAPONS[1][2],.45)
        self.assertEqual([w[2] for w in WEAPONS],[.12,.58,.67,.82])

    def test_BAL_3_business_strategy_beats_cheap_wash_at_all_horizons(self):
        from simulate_balance import economy
        import statistics
        for days in (90,180,365):
            with self.subTest(days=days):
                business=statistics.median(economy(days,s,True,0) for s in range(7))
                wash=statistics.median(economy(days,s,False,0) for s in range(7))
                self.assertGreater(business,wash)

    def test_BAL_4_larger_mule_stock_increases_actual_loss(self):
        from unittest.mock import patch
        for stock,loses in ((5,False),(100,False),(500,True)):
            g=new_game(seed=8);g.execute('hire',city='Aarhus',tier=0)
            g.s['mules'][0]['inventory']['hash']=stock
            with patch.object(g.rng,'random',return_value=.01):g.execute('wait')
            self.assertEqual(g.s['mules'][0]['lost']>0,loses)
        rng=random.Random(20261121);rolls=[rng.random() for _ in range(10000)]
        losses=[sum(v<mule_risk(n) for v in rolls) for n in (5,100,500)]
        self.assertLess(losses[0],losses[1]);self.assertLess(losses[1],losses[2])

    def test_BAL_5_shared_world_personal_rng_and_routes(self):
        a=new_game(seed=10,market_seed='shared');b=new_game(seed=20,market_seed='shared')
        self.assertEqual(a.s['markets'],b.s['markets'])
        for day in range(2,32):
            # Different routes, cash operations and random draws cannot reroll
            # another player's world or the shared event's drug/factor.
            a.rng.random();a.execute('wash',amount=1_000 if day==2 else 10,tier=0) if a.s['black']>=10 else None
            a.execute('wait');b.execute('travel',city=CITIES[day%8],district=day%6)
            self.assertEqual(a.s['markets'],b.s['markets'])
            ea=a.s['market_event_detail'];eb=b.s['market_event_detail']
            self.assertEqual(ea is None,eb is None)
            if ea:self.assertEqual((ea['title'],ea['drug']),(eb['title'],eb['drug']))
        before=a.rng.getstate();a.roll_shared_markets();self.assertEqual(before,a.rng.getstate())
        self.assertNotEqual(new_game(seed=10).s['markets'],new_game(seed=20).s['markets'])

    def test_BAL_6_history_contains_latest_score_once_per_day(self):
        g=new_game(seed=5);g.execute('bank',kind='borrow',amount=100)
        self.assertEqual(g.s['history'],[dict(day=1,score=g.score)])
        previous=g.score;g.execute('wait');g.execute('bank',kind='repay_black',amount=100)
        self.assertEqual(g.s['history'],[dict(day=1,score=previous),dict(day=2,score=g.score)])
        g.execute('finish');self.assertEqual(len(g.s['history']),2)

    def test_NFR_3_seeded_entity_ids_and_commands_deterministic(self):
        games=[new_game(seed=67) for _ in range(2)]
        for g in games:
            g.s.update(black=100000,clean=100000)
            g.execute('hire',city='Odense',tier=1);g.execute('asset',tier=0)
            g.execute('buy',drug='hash',qty=10)
            g.execute('dispatch',mid=g.s['mules'][0]['id'],drug='hash',qty=10)
            g.execute('fund',aid=g.s['assets'][0]['id'],amount=1000)
            for _ in range(10):g.execute('wait')
        self.assertEqual(games[0].s,games[1].s);self.assertEqual(games[0].rng.getstate(),games[1].rng.getstate())

if __name__=='__main__':unittest.main(verbosity=2)

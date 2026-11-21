"""Dope Wars - BFT edition. Independent, turn-based game simulation.

Money uses integer game-kroner. No real trading or financial services.
The command boundary is deliberately independent of Qt for a future server.
"""
from __future__ import annotations
import copy
import json
import math
import inspect
import random
import uuid
import hashlib
from pathlib import Path

VERSION = '1.3.0'
RULESET = 'bft-6'
DURATIONS = (31, 90, 180, 365)
DRUGS = {'hash': ('Hash', 150), 'cocaine': ('Kokain', 900),
         'amphetamine': ('Amfetamin', 300), 'mdma': ('MDMA', 450),
         'ketamine': ('Ketamin', 550), 'meth': ('Metamfetamin', 700)}
CITIES = ['København', 'Aarhus', 'Odense', 'Aalborg', 'Esbjerg', 'Næstved', 'Randers', 'Høje på Fyn']
# Real place names, fictional market profiles; not local drug-market evidence.
DISTRICTS = {
 'Høje på Fyn': ['Landsbyen', 'Bykanten', 'Landevejen', 'Markvejen', 'Skovkanten', 'Udkanten'],
 'København': ['Indre By', 'Christiania', 'Nørrebro', 'Vesterbro', 'Østerbro', 'Amagerbro'],
 'Aarhus': ['Midtbyen', 'Latinerkvarteret', 'Frederiksbjerg', 'Trøjborg', 'Aarhus Ø', 'Godsbanen'],
 'Odense': ['Centrum', 'Brandts-kvarteret', 'Storms Pakhus', 'Skibhuskvarteret', 'Odense Havn', 'Bolbro'],
 'Aalborg': ['Centrum', 'Havnefronten', 'Vestbyen', 'Øgadekvarteret', 'Nordkraft', 'Nørresundby'],
 'Esbjerg': ['Torvet', 'Esbjerg Havn', 'Sædding', 'Hjerting', 'Vognsbølparken', 'Esbjerg Station'],
 'Næstved': ['Axeltorv', 'Næstved Storcenter', 'Næstved Havn', 'Herlufsholm', 'Grønnegade', 'Næstved Station'],
 'Randers': ['Rådhustorvet', 'Randers Storcenter', 'Randers Havn', 'Vorup', 'Dronningborg', 'Kristrup'],
}
# Fixed design modifiers apply to the daily random price; never a guaranteed best price.
AREA_PROFILES = [({}, 'Blandet marked'),
                ({'hash': .72}, 'Hash: basispris −28 %'),
                ({'mdma': .85}, 'MDMA: basispris −15 %'),
                ({'amphetamine': .85}, 'Amfetamin: basispris −15 %'),
                ({'cocaine': 1.15}, 'Kokain: basispris +15 %'),
                ({'ketamine': .85}, 'Ketamin: basispris −15 %')]


def area_factor(city, district, drug):
    return AREA_PROFILES[district][0].get(drug, 1.0)


def area_description(city, district):
    return AREA_PROFILES[district][1]

# Table 3, weekly means, 2024 samples, published June 2025, AU/SST.
# Same-substance comparisons only. Catchments, not whole municipalities.
OBSERVED = {
 'hash': [123, 63, 78, 91, 111, 94],
 'cocaine': [548, 279, 407, 488, 383, 298],
 'amphetamine': [96, 72, 122, 113, 200, 179],
 'mdma': [37, 12, 10, 18, 6.7, 7.1],
 'ketamine': [33, 3.3, 7.2, 30, 6.8, 15],
 'meth': [25, 6.4, 1.5, 4.2, 2.5, .8],
}
SOURCE = 'https://www.sst.dk/media/ge5pvsjy/national-kortlaegning-af-rusmidler-i-spildevand-fra-danske-byer.pdf'
LATEST_SOURCE = 'https://www.sst.dk/Vidensbank-om-opioider/Spildevandsovervaagning'
BAGS = [('Frakkelommer', 50, 0), ('Rygsæk', 100, 1400), ('Sportstaske', 200, 4200), ('Rejsetaske', 350, 9500), ('Ekspeditionstaske', 600, 20000)]
WEAPONS = [('Ingen', 0, .12), ('Pistol', 2500, .58), ('Haglgevær', 7000, .67), ('Riffel', 16000, .82)]
MULE_TIERS = [('Begynder', 800, 5, 12), ('Erfaren', 2400, 12, 20), ('Specialist', 6500, 25, 28)]
ASSETS = [('Designstudio', 3000, 500, 12, 2, 10),
          ('Spillehal', 9000, 1800, 11, 3, 24),
          ('Pladeselskab', 26000, 6000, 10, 4, 60)]
MULE_RISK = .001  # Per active day; ~30.6% chance of >=1 event over 365 days.
HEAT_DIVISOR = 250
TIP_DAYS = 5
TIP_RISK_BONUS = .20
TIP_RUN_PENALTY = .20
TIP_COOLDOWN = 10


def tip_cost(black):
    return max(500, (black * 4 + 99) // 100)


def mule_risk(stock):
    return min(.026, MULE_RISK + max(0, stock) / 20000)
WASH_OPTIONS = [('Billig', 15, 5, 12), ('Standard', 25, 3, 7), ('Hurtig', 40, 1, 3)]
INTEREST_BP = 150  # 1.5% per day, rounded up, compound.
MARKET_EVENT_CHANCE = .35
MARKET_EVENT_MAX_GAP = 4
POLICE_BASE_CHANCE = .18
POLICE_MAX_GAP = 6
MARKET_EVENTS = (
    ('Stor levering', .20, 'En uventet stor levering oversvømmer markedet. Prisen på {drug} styrtdykker.'),
    ('Lagerudsalg', .30, 'En bagmand rydder sit lager. {drug} bliver solgt til spotpris.'),
    ('Politirazzia', 3.0, 'Politiet har beslaglagt en stor sending. Der er akut mangel på {drug}.'),
    ('Panikkøb', 4.0, 'Et rygte får efterspørgslen til at eksplodere. Alle vil købe {drug}.'),
)


class RuleError(ValueError):
    pass


def money(n):
    return f'{int(n):,}'.replace(',', '.') + ' kr.'


def demand(city, drug):
    """Bounded design mapping, NOT a measured price or a prevalence estimate."""
    i = CITIES.index(city)
    if i >= 6:
        return 1.0
    values = OBSERVED[drug]
    mean = sum(values) / len(values)
    return round(max(.80, min(1.25, 1 + .18 * math.log2(values[i] / mean))), 3)


def new_game(name='Spiller', city='Høje på Fyn', days=31, seed=None, market_seed=None):
    if city not in CITIES or type(days) is not int or days not in DURATIONS:
        raise RuleError('Vælg en gyldig by og tidshorisont.')
    g = Game()
    g.rng = random.Random(seed)
    gid=uuid.uuid4().hex if seed is None else hashlib.sha256(('bft6:'+str(seed)).encode()).hexdigest()[:32]
    g.s = dict(schema=1, ruleset=RULESET, id=gid, name=(''.join(c for c in str(name) if c.isprintable()).strip() or 'Spiller')[:24],
               city=city, district=0, day=1, duration=days, black=2000, stash=0, clean=0,
               debt=5500, health=100, heat=0, bag=0, weapon=0,
               inventory={k: 0 for k in DRUGS}, cost={k: 0 for k in DRUGS},
               markets={}, mules=[], assets=[], washing=[], log=[], history=[], finished=False,
               reason='', police=False, green_card=False, market_event='', market_event_detail=None,
               last_market_event_day=1, last_police_day=1, day_events=[],
               market_seed=market_seed, entity_seq=0, tip_until_day=0, tip_cooldown_until=0,
               last_summary='Din første dag starter nu.')
    g.roll_markets()
    g.log('Velkommen til BFT. Kun lovlig nettoformue tæller på highscorelisten.')
    g.record_score()
    return g


class Game:
    def __init__(self):
        self.s = {}
        self.rng = random.Random()

    @property
    def used(self):
        return sum(self.s['inventory'].values())

    @property
    def capacity(self):
        return BAGS[self.s['bag']][1]

    @property
    def asset_value(self):
        return sum(ASSETS[a['tier']][1] * 60 // 100 for a in self.s['assets'])

    @property
    def score(self):
        return self.s['clean'] + self.asset_value - self.s['debt']

    @property
    def loan_room(self):
        return max(0, 10000 + self.asset_value * 40 // 100 - self.s['debt'])

    @property
    def next_interest(self):
        return (self.s['debt'] * INTEREST_BP + 9999) // 10000

    @property
    def tip_active(self):
        return 0 < self.s.get('tip_until_day', 0) and self.s['day'] <= self.s['tip_until_day']

    def police_risk(self, next_day=False):
        day=self.s['day']+int(next_day)
        heat=max(0,self.s['heat']-5) if next_day else self.s['heat']
        if day-self.s['last_police_day'] >= POLICE_MAX_GAP:return 1.0
        tipped=0 < self.s.get('tip_until_day',0) and day<=self.s['tip_until_day']
        return min(1.0, POLICE_BASE_CHANCE+heat/HEAT_DIVISOR+(TIP_RISK_BONUS if tipped else 0))

    @property
    def run_chance(self):
        normal=.65-.2*self.used/max(1,self.capacity)
        return max(.15,normal-(TIP_RUN_PENALTY if self.tip_active else 0))

    def record_score(self):
        # BAL-6: the last observed score for each personal day, never private data.
        record=dict(day=self.s['day'],score=self.score)
        if self.s['history'] and self.s['history'][-1]['day']==self.s['day']:self.s['history'][-1]=record
        else:self.s['history'].append(record)

    def entity_id(self):
        # NFR-3: stable identifiers without consuming the gameplay RNG stream.
        self.s['entity_seq']=self.s.get('entity_seq',0)+1
        return hashlib.sha256((self.s['id']+':'+str(self.s['entity_seq'])).encode()).hexdigest()[:16]

    def log(self, msg):
        self.s['log'].insert(0, f"Dag {self.s['day']:03d}  ·  {msg}")
        self.s['log'] = self.s['log'][:160]

    def quote(self, drug, city=None, district=None):
        city = city or self.s['city']
        district = self.s['district'] if district is None else district
        return self.s['markets'][city][district][drug]

    def roll_markets(self):
        if self.s.get('market_seed') is not None:
            self.roll_shared_markets()
            return
        self.s['markets'] = {}
        # Markets are fixed for the day. No reroll by reopening screens or saves.
        for city in CITIES:
            self.s['markets'][city] = []
            for district in range(6):
                prices = {}
                for k, (_, base) in DRUGS.items():
                    weekend = 1.15 if self.s['day'] % 7 in (6, 0) and k in ('cocaine', 'mdma') else 1
                    prices[k] = max(10, round(base * self.rng.uniform(.50, 1.65) * demand(city, k) * weekend * area_factor(city, district, k)))
                self.s['markets'][city].append(prices)
        self.s['market_event'] = ''
        self.s['market_event_detail'] = None
        overdue = self.s['day'] - self.s['last_market_event_day'] >= MARKET_EVENT_MAX_GAP
        if self.s['day'] > 1 and (self.rng.random() < MARKET_EVENT_CHANCE or overdue):
            k = self.rng.choice(list(DRUGS))
            headline, factor, story = self.rng.choice(MARKET_EVENTS)
            market = self.s['markets'][self.s['city']][self.s['district']]
            before = market[k]
            market[k] = max(1, round(before * factor))
            change = round((market[k] / before - 1) * 100)
            detail = dict(kind='market', title=headline, drug=k, before=before, price=market[k],
                          change=change, text=story.format(drug=DRUGS[k][0]), day=self.s['day'])
            self.s['market_event_detail'] = detail
            self.s['day_events'].append(copy.deepcopy(detail))
            self.s['last_market_event_day'] = self.s['day']
            self.s['market_event'] = f"{DRUGS[k][0]} {change:+d} % · {money(before)} → {money(market[k])}"

    def roll_shared_markets(self):
        """BAL-5: one world per session/day, independent of route and personal RNG.

        Corresponding cities/areas share prices. Daily shocks affect every city;
        local profiles still apply, and future prices/seeds never leave the host.
        """
        seed=self.s['market_seed'];day=self.s['day']
        rng=random.Random(f'{seed}:prices:{day}')
        self.s['markets']={city:[{k:max(10,round(base*rng.uniform(.5,1.65)*demand(city,k)*
            (1.15 if day%7 in (6,0) and k in ('cocaine','mdma') else 1)*area_factor(city,area,k)))
            for k,(_,base) in DRUGS.items()} for area in range(6)] for city in CITIES}
        # The cadence is a function of session seed and day, not player history.
        last=1;event_rng=None
        for d in range(2,day+1):
            daily=random.Random(f'{seed}:event:{d}')
            if daily.random()<MARKET_EVENT_CHANCE or d-last>=MARKET_EVENT_MAX_GAP:
                last=d
                if d==day:event_rng=daily
        self.s['last_market_event_day']=last
        self.s['market_event']='';self.s['market_event_detail']=None
        if event_rng is None:return
        k=event_rng.choice(list(DRUGS));headline,factor,story=event_rng.choice(MARKET_EVENTS)
        before=self.quote(k)
        for areas in self.s['markets'].values():
            for market in areas:market[k]=max(1,round(market[k]*factor))
        price=self.quote(k);change=round((price/before-1)*100)
        detail=dict(kind='market',title=headline,drug=k,before=before,price=price,change=change,
                    text=story.format(drug=DRUGS[k][0]),day=day)
        self.s['market_event_detail']=detail;self.s['day_events'].append(copy.deepcopy(detail))
        self.s['market_event']=f'{DRUGS[k][0]} {change:+d} % · {money(before)} → {money(price)}'

    def require_active(self, police_ok=False):
        if self.s['finished']:
            raise RuleError('Spillet er afsluttet. Start et nyt spil.')
        if self.s['police'] and not police_ok:
            raise RuleError('Afslut mødet med politiet først.')

    def amount(self, n):
        if type(n) is not int or n <= 0 or n > 10**12:
            raise RuleError('Beløbet eller antallet skal være et positivt heltal.')

    def pay(self, n, wallet='black'):
        self.amount(n)
        if self.s[wallet] < n:
            raise RuleError('Ikke nok ' + ('lovlige penge.' if wallet == 'clean' else 'sorte kontanter.'))
        self.s[wallet] -= n

    def execute(self, action, **args):
        """Atomic command boundary: failed commands cannot partially mutate state/RNG."""
        allowed = {'buy', 'sell', 'travel', 'wait', 'bag', 'weapon', 'bank', 'hire',
                   'dispatch', 'dismiss', 'asset', 'fund', 'sell_asset', 'heal', 'police', 'finish', 'wash'}
        if type(action) is not str or action not in allowed:
            raise RuleError('Ukendt handling.')
        try:
            inspect.signature(getattr(self, 'do_' + action)).bind(**args)
        except TypeError as e:
            raise RuleError('Handlingen har ugyldige argumenter.') from e
        for key, value in args.items():
            if key in ('amount', 'qty', 'tier', 'district'):
                if type(value) is not int or abs(value) > 10**12:
                    raise RuleError('Beløb og antal skal være hele tal inden for spillets grænse.')
            elif type(value) is not str or len(value) > 100:
                raise RuleError('Handlingen har et ugyldigt tekstfelt.')
        self.require_active(action == 'police')
        before, rng = copy.deepcopy(self.s), self.rng.getstate()
        try:
            getattr(self, 'do_' + action)(**args)
            self.record_score()
            self.check()
        except Exception:
            self.s, _ = before, self.rng.setstate(rng)
            raise

    def do_buy(self, drug, qty):
        self.amount(qty)
        if drug not in DRUGS:
            raise RuleError('Ukendt vare.')
        if self.used + qty > self.capacity:
            raise RuleError('Der er ikke plads i tasken.')
        total = self.quote(drug) * qty
        self.pay(total)
        self.s['inventory'][drug] += qty
        self.s['cost'][drug] += total
        self.s['heat'] = min(100, self.s['heat'] + max(1, qty // 15))
        self.log(f"Købt {qty} {DRUGS[drug][0]} for {money(total)}")

    def remove_goods(self, drug, qty):
        self.amount(qty)
        if drug not in DRUGS:raise RuleError('Ukendt vare.')
        owned = self.s['inventory'][drug]
        if qty > owned:
            raise RuleError('Du har ikke så mange varer.')
        cost = self.s['cost'][drug] * qty // owned
        self.s['inventory'][drug] -= qty
        self.s['cost'][drug] -= cost
        return cost

    def do_sell(self, drug, qty):
        self.remove_goods(drug, qty)
        value = self.sell_quote(drug) * qty
        self.s['black'] += value
        self.s['heat'] = min(100, self.s['heat'] + max(1, qty // 20))
        self.log(f"Solgt {qty} {DRUGS[drug][0]} for {money(value)}")

    def do_bag(self, tier):
        if not self.s['bag'] < tier < len(BAGS):
            raise RuleError('Vælg en større taske.')
        self.pay(BAGS[tier][2])
        self.s['bag'] = tier
        self.log(f'Taske opgraderet til {BAGS[tier][0]}.')

    def do_weapon(self, tier):
        if not self.s['weapon'] < tier < len(WEAPONS):
            raise RuleError('Vælg en bedre våbenklasse.')
        self.pay(WEAPONS[tier][1])
        self.s['weapon'] = tier
        self.log(f'Købt {WEAPONS[tier][0]}.')

    def do_heal(self):
        if self.s['health'] == 100:
            raise RuleError('Dit helbred er allerede fuldt.')
        self.pay((100 - self.s['health']) * 20)
        self.s['health'] = 100
        self.log('Helbredet er genoprettet.')

    def do_bank(self, kind, amount):
        self.amount(amount)
        if kind == 'borrow':
            if amount > self.loan_room:
                raise RuleError('Beløbet overstiger din lånegrænse.')
            self.s['debt'] += amount
            self.s['black'] += amount
        elif kind in ('repay_black', 'repay_clean'):
            if amount > self.s['debt']:
                raise RuleError('Du kan ikke betale mere end din gæld.')
            self.pay(amount, 'black' if kind == 'repay_black' else 'clean')
            self.s['debt'] -= amount
        elif kind == 'deposit':
            raise RuleError('Kontanter skal hvidvaskes før de kan komme i banken.')
        elif kind == 'withdraw':
            self.pay(amount, 'stash')
            self.s['black'] += amount
        elif kind == 'to_black':
            self.pay(amount, 'clean')
            self.s['black'] += amount
        else:
            raise RuleError('Ukendt bankhandling.')
        names = dict(borrow='Lånt', repay_black='Afdraget med sorte penge', repay_clean='Afdraget med lovlige penge',
                     deposit='Indsat i sort depot', withdraw='Hævet fra sort depot', to_black='Overført til sort økonomi')
        self.log(f'{names[kind]}: {money(amount)}')

    def require_queue_room(self):
        # Bound persistent/network payloads and dialog size without losing existing orders.
        if len(self.s['washing']) + sum(len(a['queue']) for a in self.s['assets']) >= 128:
            raise RuleError('Du har 128 ventende ordrer. Vent til nogle er behandlet.')

    def sell_quote(self, drug):
        return self.quote(drug)

    def do_wash(self, amount, tier):
        self.require_queue_room()
        self.amount(amount)
        if type(tier) is not int or not 0 <= tier < len(WASH_OPTIONS):
            raise RuleError('Vælg et gyldigt gebyrniveau.')
        name, fee, low, high = WASH_OPTIONS[tier]
        self.pay(amount)
        delay = self.rng.randint(low, high)
        payout = amount * (100-fee) // 100
        if payout < 1:
            raise RuleError('Beløbet er for lille efter gebyr.')
        self.s['washing'].append(dict(amount=amount, payout=payout, tier=tier,
                                      started=self.s['day'], ready=self.s['day']+delay))
        self.log(f'{money(amount)} til hvidvaskning: {name}, {fee} % gebyr, {low}–{high} dage. Udbetaling {money(payout)}.')

    def do_hire(self, city, tier):
        if city not in CITIES or city == self.s['city']:
            raise RuleError('Vælg en anden by end den, du opholder dig i.')
        if len(self.s['mules']) >= 6:
            raise RuleError('Du kan højst have seks mules.')
        if type(tier) is not int or not 0 <= tier < len(MULE_TIERS):
            raise RuleError('Ugyldigt niveau.')
        self.pay(MULE_TIERS[tier][1])
        mid = self.entity_id()
        self.s['mules'].append(dict(id=mid, city=city, tier=tier, inventory={k: 0 for k in DRUGS},
                                    earned=0, cut_paid=0, lost=0, cooldown=0))
        self.log(f'{MULE_TIERS[tier][0]} mule hyret i {city}.')

    def mule(self, mid):
        for m in self.s['mules']:
            if m['id'] == mid:
                return m
        raise RuleError('Denne mule findes ikke længere.')

    def do_dispatch(self, mid, drug, qty):
        m = self.mule(mid)
        if sum(m['inventory'].values()) + qty > 500:
            raise RuleError('En mule kan højst have 500 enheder på lager.')
        self.remove_goods(drug, qty)
        m['inventory'][drug] += qty
        self.log(f'{qty} {DRUGS[drug][0]} sendt til din mule i {m["city"]}. Salg fra næste dag.')

    def do_dismiss(self, mid):
        m = self.mule(mid)
        if sum(m['inventory'].values()):
            raise RuleError('Vent med at afskedige, til lageret er solgt.')
        self.s['mules'].remove(m)
        self.log(f'Mule i {m["city"]} afskediget.')

    def do_asset(self, tier):
        if type(tier) is not int or not 0 <= tier < len(ASSETS):
            raise RuleError('Ugyldig investering.')
        if len(self.s['assets']) >= 6:
            raise RuleError('Du kan højst eje seks virksomheder.')
        self.pay(ASSETS[tier][1], 'clean')
        self.s['assets'].append(dict(id=self.entity_id(), tier=tier, queue=[], converted=0, income=0))
        self.log(f'{ASSETS[tier][0]} købt for lovlige penge.')

    def asset(self, aid):
        for a in self.s['assets']:
            if a['id'] == aid:
                return a
        raise RuleError('Virksomheden findes ikke længere.')

    def do_fund(self, aid, amount):
        a = self.asset(aid)
        self.require_queue_room()
        self.amount(amount)
        _, _, capacity, fee, delay, _ = ASSETS[a['tier']]
        pending = sum(x['remaining'] for x in a['queue'])
        if pending + amount > capacity * 10:
            raise RuleError('Køen har kun plads til ti dages kapacitet.')
        self.pay(amount)
        # Round fee once per order; processing cannot exploit per-day rounding.
        a['queue'].append(dict(remaining=amount, original=amount, processed=0, paid=0,
                               payout=amount * (100-fee) // 100, ready=self.s['day'] + delay))
        self.log(f'{money(amount)} sat i kø hos {ASSETS[a["tier"]][0]}. Tidligst dag {self.s["day"] + delay}.')

    def do_sell_asset(self, aid):
        a = self.asset(aid)
        if a['queue']:
            raise RuleError('Virksomheden kan først sælges, når køen er tom.')
        value = ASSETS[a['tier']][1] * 60 // 100
        self.s['clean'] += value
        self.s['assets'].remove(a)
        self.log(f'Virksomhed solgt for {money(value)} i lovlige penge.')

    def do_travel(self, city, district):
        if city not in CITIES or type(district) is not int or not 0 <= district < 6:
            raise RuleError('Ugyldig destination.')
        if city == self.s['city'] and district == self.s['district']:
            raise RuleError('Du er allerede her. Brug Næste dag for at vente.')
        if self.s['day'] >= self.s['duration']:
            raise RuleError('Det er sidste dag. Afslut spillet, når du er klar.')
        self.s['city'], self.s['district'] = city, district
        self.advance()
        self.log(f'Ankommet til {city} · {DISTRICTS[city][district]}.')

    def do_wait(self):
        if self.s['day'] >= self.s['duration']:
            self.finish('Tidshorisonten er nået.')
        else:
            self.advance()

    def advance(self):
        self.s['day'] += 1
        self.s['day_events'] = []
        interest = self.next_interest
        self.s['debt'] += interest
        self.s['heat'] = max(0, self.s['heat'] - 5)
        self.roll_markets()
        mule_net = clean_gain = 0
        for m in self.s['mules']:
            if m['cooldown']:
                m['cooldown'] -= 1
                continue
            if not sum(m['inventory'].values()):
                continue
            if self.rng.random() < mule_risk(sum(m['inventory'].values())):
                lost = 0
                for k, n in m['inventory'].items():
                    loss = (n + 3) // 4
                    m['inventory'][k] -= loss
                    lost += loss
                m['lost'] += lost
                m['cooldown'] = 2
                self.log(f'Mule i {m["city"]}: tilbagefald, {lost} varer mistet og to dages pause.')
                continue
            _, _, volume, cut = MULE_TIERS[m['tier']]
            for k in DRUGS:
                qty = min(m['inventory'][k], volume)
                if not qty:
                    continue
                gross = self.quote(k, m['city'], 0) * qty
                commission = (gross * cut + 99) // 100
                net = gross - commission
                m['inventory'][k] -= qty
                volume -= qty
                m['earned'] += net
                m['cut_paid'] += commission
                mule_net += net
        self.s['black'] += mule_net
        for a in self.s['assets']:
            _, _, remaining_capacity, _, _, income = ASSETS[a['tier']]
            clean_gain += income
            a['income'] += income
            for order in a['queue']:
                if order['ready'] > self.s['day']:
                    continue
                processed = min(remaining_capacity, order['remaining'])
                order['remaining'] -= processed
                order['processed'] += processed
                remaining_capacity -= processed
                cumulative = order['payout'] * order['processed'] // order['original']
                released = cumulative - order['paid']
                order['paid'] = cumulative
                clean_gain += released
                a['converted'] += released
            a['queue'] = [o for o in a['queue'] if o['remaining']]
        for order in self.s['washing']:
            if order['ready'] <= self.s['day']:
                clean_gain += order['payout']
                self.log('Hvidvaskning afsluttet: ' + money(order['payout']) + ' indsat i banken.')
        self.s['washing'] = [o for o in self.s['washing'] if o['ready'] > self.s['day']]
        self.s['clean'] += clean_gain
        self.s['health'] = min(100, self.s['health'] + 1)
        self.s['last_summary'] = f'Rente −{money(interest)}   ·   Mules +{money(mule_net)}   ·   Lovligt +{money(clean_gain)}'
        self.log(self.s['last_summary'])
        if self.s['market_event']:
            self.log(self.s['market_event'])
        risk = self.police_risk()
        overdue = self.s['day'] - self.s['last_police_day'] >= POLICE_MAX_GAP
        if self.rng.random() < risk or overdue:
            self.s['last_police_day'] = self.s['day']
            if self.used == 0:
                self.s['green_card'] = True
                message = 'Politikontrol: ingen varer fundet. Du har et green card (maks. ét).'
                self.log(message)
                self.s['day_events'].append(dict(kind='clear_police', title='Politiet stopper dig',
                                                text='Tasken er tom, så du får lov at gå. Dit green card er klar til næste kontrol.',
                                                day=self.s['day']))
            else:
                self.s['police'] = True
                self.log('Politiet stopper dig. Vælg din handling.')

    def do_police(self, choice):
        if not self.s['police'] or choice not in ('fight', 'run', 'surrender', 'explain'):
            raise RuleError('Der er ikke en gyldig politihændelse.')
        if self.used == 0:
            self.s['green_card'] = True
            self.log('Ingen varer fundet. Du får et green card (maks. ét).')
        elif choice == 'explain':
            if not self.s['green_card']:
                raise RuleError('Du har ikke et green card.')
            self.s['green_card'] = False
            if self.rng.random() < .5:
                self.log('Din forklaring blev accepteret. Green card brugt; du beholder alt.')
            else:
                self.confiscate()
                self.log('Politiet troede ikke på dig. Green card brugt; varer og 25 % af sorte kontanter beslaglagt.')
        elif choice == 'surrender':
            self.confiscate()
            self.log('Du overgav dig. Varer og 25 % af sorte kontanter beslaglagt.')
        else:
            chance = WEAPONS[self.s['weapon']][2] if choice == 'fight' else self.run_chance
            success = self.rng.random() < chance
            damage = self.rng.randint(3, 14) if success else self.rng.randint(20, 45)
            if self.tip_active and choice=='run' and not success:
                damage=min((damage+1)//2,max(0,self.s['health']-1))
            self.s['health'] = max(0, self.s['health'] - damage)
            if not success:
                self.confiscate()
            self.log(('Du slap væk.' if success else 'Politiet vandt. Varer og 25 % af sorte kontanter beslaglagt.') + f' Helbred −{damage}.')
        self.s['heat'] = 0
        self.s['police'] = False
        if self.s['health'] <= 0:
            self.finish('Du døde. Din lovlige nettoformue er bevaret som slutscore.')

    def confiscate(self):
        self.s['inventory'] = {k: 0 for k in DRUGS}
        self.s['cost'] = {k: 0 for k in DRUGS}
        self.s['black'] -= self.s['black'] // 4

    def do_finish(self):
        self.finish('Spillet afsluttet.')

    def finish(self, reason):
        self.s['finished'] = True
        self.s['reason'] = reason
        self.s['police'] = False
        self.log(f'{reason} Slutscore: {money(self.score)}')
        self.record_score()

    def public_score(self):
        # Future public leaderboard projection intentionally excludes black assets.
        return dict(id=self.s['id'], name=self.s['name'], duration=self.s['duration'],
                    day=self.s['day'], score=self.score, ruleset=RULESET, reason=self.s['reason'])

    def check(self):
        s = self.s
        for key in ('day','duration','district','bag','weapon'):
            if type(s[key]) is not int:raise RuleError('Spiltilstanden indeholder et ugyldigt tal.')
        for key in ('finished','police'):
            if type(s[key]) is not bool:raise RuleError('Spiltilstanden indeholder en ugyldig status.')
        for key in ('last_market_event_day','last_police_day'):
            if type(s[key]) is not int or not 1 <= s[key] <= s['day']:
                raise RuleError('Ugyldig hændelseshistorik.')
        if not isinstance(s['day_events'], list) or len(s['day_events']) > 3:
            raise RuleError('Ugyldige dagshændelser.')
        for key in ('tip_until_day','tip_cooldown_until','entity_seq'):
            if type(s.get(key,0)) is not int or not 0<=s.get(key,0)<=10**12:raise RuleError('Ugyldig tip- eller identitetshistorik.')
        if s.get('market_seed') is not None and (not isinstance(s['market_seed'],str) or len(s['market_seed'])>100):raise RuleError('Ugyldigt fælles marked.')
        if set(s['cost']) != set(DRUGS):raise RuleError('Ugyldige indkøbspriser.')
        for o in s['washing']:
            if not (0 <= o['tier'] < len(WASH_OPTIONS)):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
            if not (0 < o['payout'] <= o['amount']):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
            if not (o['started'] < o['ready']):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (type(s['green_card']) is bool):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (s['city'] in CITIES and s['duration'] in DURATIONS):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (1 <= s['day'] <= s['duration'] and 0 <= s['district'] < 6):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (all(type(s[k]) is int and s[k] >= 0 for k in ('black','stash','clean','debt','health','heat'))):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (0 <= s['health'] <= 100 and 0 <= s['heat'] <= 100):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (0 <= s['bag'] < len(BAGS) and 0 <= s['weapon'] < len(WEAPONS)):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (self.used <= self.capacity):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (set(s['inventory']) == set(DRUGS)):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (all(type(v) is int and v >= 0 for v in s['inventory'].values())):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (all(type(v) is int and v >= 0 for v in s['cost'].values())):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        if not (len(s['mules']) <= 6 and len(s['assets']) <= 6):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        for m in s['mules']:
            if not (m['city'] in CITIES and 0 <= m['tier'] < 3):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
            if not (all(type(v) is int and v >= 0 for v in m['inventory'].values())):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
        for a in s['assets']:
            if not (0 <= a['tier'] < 3):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
            for o in a['queue']:
                if not (o['remaining'] > 0 and o['original'] == o['remaining'] + o['processed']):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')
                if not (0 <= o['paid'] <= o['payout'] <= o['original']):raise RuleError('Spiltilstanden er ugyldig eller beskadiget.')


    def save(self, path):
        self.check()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(state=self.s, rng=self.rng.getstate())
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        temp.replace(path)

    @classmethod
    def load(cls, path):
        def tuples(x):
            return tuple(map(tuples, x)) if isinstance(x, list) else x
        d = json.loads(Path(path).read_text(encoding='utf-8'))
        if d['state'].get('schema') != 1 or d['state'].get('ruleset') not in ('bft-1', 'bft-2', 'bft-3', 'bft-4', 'bft-5', RULESET):
            raise RuleError('Denne gemte fil bruger en anden spilversion.')
        if d['state'].get('ruleset')!=RULESET:
            backup=Path(path).with_suffix('.pre-v1.2.json')
            if not backup.exists():backup.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
        g = cls()
        g.s = d['state']
        g.upgrade_events()
        g.s.setdefault('green_card', False)
        g.s.setdefault('washing', [])
        # Retire the black depot without converting it to legal funds.
        g.s['black'] += g.s['stash']
        g.s['stash'] = 0
        # Preserve old daily prices and RNG while adding the new destination.
        g.s['markets'].setdefault('Høje på Fyn', copy.deepcopy(g.s['markets']['Odense']))
        g.s['ruleset'] = RULESET
        g.rng.setstate(tuples(d['rng']))
        g.check()
        return g

    def upgrade_events(self):
        """Add event cadence without rerolling an existing day's prices or RNG."""
        self.s.setdefault('last_market_event_day', self.s['day'])
        self.s.setdefault('last_police_day', self.s['day'])
        self.s.setdefault('day_events', [])
        self.s.setdefault('market_event_detail', None)
        self.s.setdefault('tip_until_day',0)
        self.s.setdefault('tip_cooldown_until',0)
        self.s.setdefault('market_seed',None)
        self.s.setdefault('entity_seq',0)
        self.s['ruleset'] = RULESET

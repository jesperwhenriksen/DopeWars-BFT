"""NFR-6: reproducible game-balance measurements, not real-world economics.

The economic comparison holds incoming fictional cash and initial wealth equal.
It uses the real queue, payout and score code, with market generation disabled
because no drugs are traded. Police cadence uses the game's probability helper.
"""
import argparse
import json
import random
import statistics
from pathlib import Path
from unittest.mock import patch
import game


def police_sample(days=10000, heat=0, tipped=False, legacy=False):
    rng = random.Random(20261121)
    g = game.new_game(seed=20261121, days=365)
    last = 0
    controls = 0
    for day in range(1, days + 1):
        if legacy:
            risk = .18 + heat / 500 + (.20 if tipped else 0)
        else:
            # Real engine probability; the 10,000-day sample is a statistical
            # experiment, not a saved game beyond the 365-day limit.
            g.s.update(day=day, heat=heat, last_police_day=last,
                       tip_until_day=days if tipped else 0)
            risk = g.police_risk()
        if rng.random() < risk or day - last >= game.POLICE_MAX_GAP:
            controls += 1
            last = day
    return dict(days=days, controls=controls, rate=round(controls/days, 4))


def economy(days, seed, business, tier=0):
    g = game.new_game(days=days, seed=seed)
    capacity = game.ASSETS[tier][2]
    g.s.update(debt=0, black=0, clean=game.ASSETS[tier][1])
    if business:
        g.execute('asset', tier=tier)
    # Isolate economic rules. The same external fictional income feeds both runs.
    with patch.object(g, 'roll_markets'):
        while g.s['day'] < days:
            g.s['black'] += capacity
            if business:
                a = g.s['assets'][0]
                available = capacity * 10 - sum(o['remaining'] for o in a['queue'])
                amount = min(g.s['black'], available)
                if amount:
                    g.execute('fund', aid=a['id'], amount=amount)
            elif g.s['black']:
                g.execute('wash', amount=g.s['black'], tier=0)
            g.execute('wait')
    return g.score


def measure(seeds=31):
    data = dict(version=game.VERSION, ruleset=game.RULESET, seed=20261121,
                assumptions='Samme startformue og faste fiktive indtægter; ingen handel, lån eller geninvestering.',
                police={name: police_sample(heat=heat, tipped=tip)
                        for name, heat, tip in [('normal', 0, False), ('tip', 0, True), ('low_heat', 5, False), ('high_heat', 60, False)]},
                weapons=[], businesses=[], mules=[])
    for tier, (name, price, chance) in enumerate(game.WEAPONS):
        for fill in (0, .25, .5, .75, 1):
            run = .65 - .2 * fill
            data['weapons'].append(dict(weapon=name, price=price, fill=fill, fight=chance, run=round(run, 3),
                best_available='Kæmp' if chance > run else 'Flygt'))
    for days in (90, 180, 365):
        for tier, asset in enumerate(game.ASSETS):
            wash = statistics.median(economy(days, seed, False, tier) for seed in range(seeds))
            business = statistics.median(economy(days, seed, True, tier) for seed in range(seeds))
            data['businesses'].append(dict(days=days, asset=asset[0], fee=asset[3], seeds=seeds,
                                          wash_median=wash, business_median=business, difference=business-wash))
    for stock in (5, 100, 500):
        risk = game.mule_risk(stock) if hasattr(game, 'mule_risk') else game.MULE_RISK
        rng = random.Random(20261121)
        data['mules'].append(dict(stock=stock, risk=risk, losses=sum(rng.random()<risk for _ in range(100000))))
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('dist/reports/balance.json'))
    parser.add_argument('--seeds', type=int, default=31)
    args = parser.parse_args()
    data = measure(args.seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(police=data['police'], businesses=data['businesses'], mules=data['mules']), ensure_ascii=False))

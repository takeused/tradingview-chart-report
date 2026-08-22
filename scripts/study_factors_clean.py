# 팩터 등록부 재검정 — 무수정 원자료 유니버스 위에서
#
# 왜 있나 (2026-08-22, 2회차): `study_factors.py` 의 결과는 전부 오염된 유니버스
#   (`pit_pool` = 수정주가 x 거래량) 위에서 나왔다. 같은 등록부를 무수정 시가총액
#   유니버스에서 다시 돌린다. 등록부·비용·음성 대조군은 그대로 두고 유니버스만 바꾼다.
#
# 표본이 6.6년(리밸런싱 82회)뿐이라 검정력이 낮다. **여기서 못 나온다고 없는 것은 아니다.**
#   반대로 여기서 나오면 오염 없이 나온 것이므로 값어치가 있다.
#
# 판정에 로그(기하) 초과수익을 함께 낸다 — 저변동처럼 변동성이 낮은 전략은 기하수익에서
#   벌고 산술평균은 그걸 못 잡는다(유니버스 감사에서 누적 2.94배 vs 1.71배인데 t=1.04였다).
#
# 사용법
#   python scripts/study_factors_clean.py [--pit 300] [--panel weekly_krx15]

import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import regime_of, round_trip_cost, stat, bh_reject, PANELS
from study_factors import FACTORS, FRACS, HORIZON, market_series
from study_clean_universe import run, by_score, START
from study_universe_audit import compound
from universe_pit import load_market, pool_cap

COST = round_trip_cost()


def main():
    which = sys.argv[sys.argv.index('--panel') + 1] if '--panel' in sys.argv else 'weekly_krx15'
    pit = int(sys.argv[sys.argv.index('--pit') + 1]) if '--pit' in sys.argv else 300
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_%s.csv' % which))
    M = load_market()
    mkt = market_series(P)
    t0 = P.di[min(d for d in P.dates if d >= START)]
    pool_fn = lambda t: pool_cap(P, M, t, pit)

    print('팩터 등록부 재검정(무수정 유니버스) — %s ~ %s · 시가총액 상위 %d · 월간(%d주) · 비용 %.2f%%'
          % (P.dates[t0], P.dates[-1], pit, HORIZON, COST))
    print('유니버스는 공공데이터포털 무수정 시가총액, 수익률은 수정주가 패널.')
    print('')
    print('%-22s %5s %4s %9s %6s %6s %9s %6s  %s'
          % ('팩터', '분위%', 'n', '산술순%', 't', 'BH', '로그순%', 't', '국면별(강세/횡보/약세)'))
    print('-' * 118)

    out = []
    for name, (why, fn) in FACTORS.items():
        for frac in FRACS:
            sel = by_score(lambda t, c, fn=fn: fn(P, c, t, mkt))
            rows = run(P, M, pool_fn, sel, t0, frac)
            if len(rows) < 20:
                continue
            ari = stat([r['net'] for r in rows])
            log = stat([100 * (math.log(1 + (r['port'] - COST * r['turn']) / 100)
                               - math.log(1 + r['bm'] / 100)) for r in rows])
            reg = {}
            for r in rows:
                g = regime_of(P, P.di[r['date']], PANELS['weekly']['regime_back'])
                if g:
                    reg.setdefault(g, []).append(r['net'])
            out.append({'name': name, 'why': why, 'frac': frac, 'ari': ari, 'log': log,
                        'reg': {g: round(stat(v)['mean'], 2) for g, v in reg.items() if stat(v)},
                        'eq': compound([r['port'] - r['turn'] * COST for r in rows]),
                        'bm': compound([r['bm'] for r in rows])})

    out.sort(key=lambda x: -x['ari']['mean'])
    rej = bh_reject([x['ari']['p'] for x in out])
    for i, x in enumerate(out):
        g = x['reg']
        print('%-22s %5.0f %4d %9.3f %6.2f %6s %9.3f %6.2f  %s'
              % (x['name'], x['frac'] * 100, x['ari']['n'], x['ari']['mean'], x['ari']['t'],
                 'O' if rej[i] else '-', x['log']['mean'], x['log']['t'],
                 ' / '.join('%+.2f' % g[k] for k in ('강세', '횡보', '약세') if k in g)))
    print('-' * 118)

    ctrl = [x for x in out if '대조군' in x['name']]
    print('음성 대조군(난수) — 산술 %s · BH 통과 %d건 (정상: 0건)'
          % (' / '.join('%+.3f' % c['ari']['mean'] for c in ctrl),
             sum(1 for i, x in enumerate(out) if rej[i] and '대조군' in x['name'])))
    win = [x for i, x in enumerate(out) if rej[i] and x['ari']['mean'] > 0 and '대조군' not in x['name']]
    print('BH 통과 + 산술 양수: %d건 / %d조합' % (len(win), len(out)))
    for x in win:
        print('  → %s (분위 %.0f%%) 산술 %+.3f · 로그 %+.3f · 누적 %.2f배 vs %.2f배 · 근거: %s'
              % (x['name'], x['frac'] * 100, x['ari']['mean'], x['log']['mean'],
                 x['eq'], x['bm'], x['why']))
    if not win:
        print('  이 표본에서 오염 없이 살아남는 팩터는 없다.')
    logwin = [x for x in out if x['log']['t'] >= 2.0 and '대조군' not in x['name']]
    print('로그 초과 t>=2.0: %d건%s'
          % (len(logwin), ' — ' + ', '.join('%s(%.0f%%)' % (x['name'], x['frac'] * 100)
                                            for x in logwin) if logwin else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())

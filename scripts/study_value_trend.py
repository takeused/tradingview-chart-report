# 밸류 x 추세 결합 — 싼 것 중에 오르는 것만 사면 나아지는가
#
# 왜 있나 (2026-08-22, 3회차): 무수정 유니버스에서 살아남은 것이 둘이다.
#   저PBR·저PSR(밸류, t=2.4~3.4)과 52주신고가 근접(추세, t=1.84). 딥밸류의 고질병은
#   **가치 함정** — 싼 데는 이유가 있고 계속 싸다는 것이다. 추세를 필터로 걸면
#   그 함정을 피할 수 있다는 가설이 오래됐다(Asness-Moskowitz-Pedersen 2013 Value+Momentum).
#
# **경고 — 조합을 만들면 가설 수가 늘어 BH 문턱이 높아진다.** 결합이 단독보다 나아 보여도
#   그건 자유도를 하나 더 쓴 결과일 수 있다. 그래서 여기서는 결합 방식을 **사전에 셋으로
#   고정**하고(순위합·교집합·밸류 안에서 추세 상위) 전부 보고한다. 좋은 것만 고르지 않는다.
#
# 사용법
#   python scripts/study_value_trend.py [--pit 300]

import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import regime_of, round_trip_cost, stat, PANELS
from study_factors import HORIZON, _hi52
from study_clean_universe import run, START
from study_universe_audit import compound
from universe_pit import load_market, pool_cap
from factors_fundamental import load_financials, at

COST = round_trip_cost()


def ranks(pairs):
    """(code, score) 목록 → code -> 백분위 순위(1 이 최고)."""
    pairs = [(c, v) for c, v in pairs if v is not None and math.isfinite(v)]
    pairs.sort(key=lambda x: -x[1])
    n = len(pairs)
    return {c: 1.0 - i / float(n - 1) if n > 1 else 1.0 for i, (c, _) in enumerate(pairs)}


def make_sel(P, M, fin, mode, key='equity'):
    def val(t, c):
        d = M.get((c, P.dates[t]))
        a = at(fin, c, P.dates[t])
        if not d or not a or d['cap'] <= 0 or a.get(key) is None or a[key] <= 0:
            return None
        return a[key] / d['cap']

    def f(t, pool, K):
        rv = ranks([(c, val(t, c)) for c in pool])
        rt = ranks([(c, _hi52(P, c, t)) for c in pool])
        both = [c for c in pool if c in rv and c in rt]
        if len(both) < max(30, 3 * K):
            return None
        if mode == '밸류만':
            sc = [(c, rv[c]) for c in both]
        elif mode == '추세만':
            sc = [(c, rt[c]) for c in both]
        elif mode == '순위합':
            sc = [(c, rv[c] + rt[c]) for c in both]
        elif mode == '교집합':
            # 각각 상위 30% 에 드는 종목만. 수가 모자라면 순위합으로 채운다
            hit = [c for c in both if rv[c] >= 0.7 and rt[c] >= 0.7]
            if len(hit) >= K:
                hit.sort(key=lambda c: -(rv[c] + rt[c]))
                return hit[:K]
            sc = [(c, (2 if c in set(hit) else 0) + rv[c] + rt[c]) for c in both]
        elif mode == '밸류내 추세':
            # 먼저 밸류 상위 30% 로 좁히고 그 안에서 추세 상위
            pre = sorted(both, key=lambda c: -rv[c])[:max(K, int(len(both) * 0.3))]
            sc = [(c, rt[c]) for c in pre]
        else:
            raise ValueError(mode)
        sc.sort(key=lambda x: -x[1])
        return [c for c, _ in sc[:K]]
    return f


def report(name, rows):
    ari = stat([r['net'] for r in rows])
    log = stat([100 * (math.log(1 + (r['port'] - COST * r['turn']) / 100)
                       - math.log(1 + r['bm'] / 100)) for r in rows])
    turn = sum(r['turn'] for r in rows[1:]) / max(1, len(rows) - 1)
    reg = {}
    for r in rows:
        g = regime_of(None, None, None) if False else None
    print('  %-12s n=%3d · 산술 %+.3f t=%5.2f · 로그 %+.3f t=%5.2f · 회전율 %3.0f%% · 누적 %.2f배'
          % (name, ari['n'], ari['mean'], ari['t'], log['mean'], log['t'], turn * 100,
             compound([r['port'] - r['turn'] * COST for r in rows])))
    return ari


def main():
    pit = int(sys.argv[sys.argv.index('--pit') + 1]) if '--pit' in sys.argv else 300
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_weekly_krx15.csv'))
    M = load_market()
    fin = load_financials()
    t0 = P.di[min(d for d in P.dates if d >= START)]
    pool_fn = lambda t: pool_cap(P, M, t, pit)

    print('밸류 x 추세 결합 — %s ~ %s · 시총 상위 %d · 월간(%d주) · 비용 %.2f%%'
          % (P.dates[t0], P.dates[-1], pit, HORIZON, COST))
    print('결합 방식 3종을 사전 고정하고 전부 보고한다. 좋은 것만 고르면 그게 과최적화다.')
    print('')
    MODES = ['밸류만', '추세만', '순위합', '교집합', '밸류내 추세']
    for frac in (0.10, 0.20):
        print('[분위 상위 %.0f%%]' % (frac * 100))
        base = None
        for mode in MODES:
            rows = run(P, M, pool_fn, make_sel(P, M, fin, mode), t0, frac)
            if len(rows) < 20:
                continue
            a = report(mode, rows)
            if mode == '밸류만':
                base = a
        if base:
            print('  ※ 판정 기준 — 결합이 밸류 단독(%+.3f)을 **의미 있게** 넘는가.'
                  ' 소폭 개선은 자유도 하나를 쓴 대가일 수 있다.' % base['mean'])
        print('')
    return 0


if __name__ == '__main__':
    sys.exit(main())

# 밸류 스트레스 테스트 — 첫 히트는 믿지 않는다
#
# 왜 있나 (2026-08-22, 3회차): 무수정 유니버스에서 저PBR·저PSR 이 t=2.8~3.0, 3국면 전부
#   양수로 나왔다. **저변동성도 처음엔 정확히 이렇게 보였다가** 유니버스 오염이 드러나며
#   무너졌다. 그래서 저변동성에 걸었던 검사를 그대로 건다.
#
#   특히 이 표본(2020-04~2026-08)은 2022~2023 가치주 반등과 2024~2025 밸류업 국면을
#   포함한다. **국면 베팅일 위험**이 가장 큰 후보다. 시기 분할을 반드시 본다.
#
#   또 하나 — 저PBR 은 소형주로 쏠린다. 그런데 이 표본에서 소형주 팩터 자체는 음수다.
#   그래서 크기 중립성(대/중/소 3분위 각각 양수인가)을 따로 확인한다.
#
# 사용법
#   python scripts/study_value.py [--pit 300]

import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import round_trip_cost, stat
from study_factors import HORIZON, market_series
from study_clean_universe import run, by_score, START
from study_universe_audit import compound
from universe_pit import load_market, pool_cap
from factors_fundamental import load_financials, at

COST = round_trip_cost()
FRACS = [0.05, 0.10, 0.20]
UNIS = [200, 300, 500]
COSTS = [0.15, 0.28, 0.50]


def value_score(P, M, fin, key):
    """계정/시가총액 — 클수록 싸다. 자본잠식·적자는 제외(None)."""
    def f(t, c):
        d = M.get((c, P.dates[t]))
        a = at(fin, c, P.dates[t])
        if not d or not a or d['cap'] <= 0 or a.get(key) is None or a[key] <= 0:
            return None
        return a[key] / d['cap']
    return f


def cap_tercile(P, M, t, pool, which):
    caps = [(M[(c, P.dates[t])]['cap'], c) for c in pool if (c, P.dates[t]) in M]
    caps.sort(key=lambda x: -x[0])
    n = len(caps) // 3
    seg = {'대형': caps[:n], '중형': caps[n:2 * n], '소형': caps[2 * n:]}[which]
    return [c for _, c in seg]


def drawdown(xs):
    eq, peak, mdd, under, worst = 1.0, 1.0, 0.0, 0, 0
    for x in xs:
        eq *= (1 + x / 100.0)
        if eq >= peak:
            peak, under = eq, 0
        else:
            under += 1
            worst = max(worst, under)
            mdd = min(mdd, eq / peak - 1)
    return eq, mdd * 100, worst


def summarize(rows):
    ari = stat([r['net'] for r in rows])
    log = stat([100 * (math.log(1 + (r['port'] - COST * r['turn']) / 100)
                       - math.log(1 + r['bm'] / 100)) for r in rows])
    turn = sum(r['turn'] for r in rows[1:]) / max(1, len(rows) - 1)
    return ari, log, turn


def main():
    pit = int(sys.argv[sys.argv.index('--pit') + 1]) if '--pit' in sys.argv else 300
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_weekly_krx15.csv'))
    M = load_market()
    fin = load_financials()
    t0 = P.di[min(d for d in P.dates if d >= START)]
    MEAS = {'저PBR': 'equity', '저PSR': 'sales', '저PER': 'netinc'}

    print('밸류 스트레스 테스트 — %s ~ %s · 월간(%d주) · 왕복비용 %.2f%%'
          % (P.dates[t0], P.dates[-1], HORIZON, COST))
    print('회전율은 실측한다. 비용은 매 시점 실측 회전율만큼만 물린다.')
    print('')

    # ── [1] 격자 ───────────────────────────────────────────────────────────
    print('[1] 사전 지정 격자 — 측정 3 x 분위 3 x 유니버스 3 = 27칸')
    print('  %-8s %5s %5s %4s %9s %6s %8s %7s %8s'
          % ('측정', '분위', '유니', 'n', '산술%/월', 't', '로그 t', '회전율', '누적배수'))
    print('  ' + '-' * 74)
    cells, pos = {}, 0
    for mname, key in MEAS.items():
        for frac in FRACS:
            for uni in UNIS:
                rows = run(P, M, lambda t, u=uni: pool_cap(P, M, t, u),
                           by_score(value_score(P, M, fin, key)), t0, frac)
                if len(rows) < 20:
                    continue
                ari, log, turn = summarize(rows)
                cells[(mname, frac, uni)] = rows
                pos += ari['mean'] > 0
                print('  %-8s %5.0f%% %5d %4d %9.3f %6.2f %8.2f %6.0f%% %8.2f'
                      % (mname, frac * 100, uni, ari['n'], ari['mean'], ari['t'],
                         log['t'], turn * 100,
                         compound([r['port'] - r['turn'] * COST for r in rows])))
    print('  → 27칸 중 산술 양수 %d칸' % pos)

    ref = ('저PBR', 0.10, 300)
    rows = cells[ref]

    # ── [2] 비용 민감도 ────────────────────────────────────────────────────
    ari, log, turn = summarize(rows)
    print('\n[2] 비용 민감도 (기준칸 %s 분위%.0f%% 유니버스%d · 실측 회전율 %.0f%%)'
          % (ref[0], ref[1] * 100, ref[2], turn * 100))
    gross = sum(r['port'] - r['bm'] for r in rows) / len(rows)
    for c in COSTS:
        print('  왕복 %.2f%% → %+.3f%%/월' % (c, gross - c * turn))

    # ── [3] 크기 중립성 ────────────────────────────────────────────────────
    print('\n[3] 크기 중립성 — 저PBR 은 소형주로 쏠린다. 3분위 각각에서도 되는가')
    for seg in ('대형', '중형', '소형'):
        rs = run(P, M, lambda t, s=seg: cap_tercile(P, M, t, pool_cap(P, M, t, 500), s),
                 by_score(value_score(P, M, fin, 'equity')), t0, 0.20)
        if len(rs) >= 20:
            a, l, tn = summarize(rs)
            print('  %s 3분위 내 저PBR 상위20%%  n=%3d · 산술 %+.3f t=%5.2f · 로그 t=%5.2f'
                  % (seg, a['n'], a['mean'], a['t'], l['t']))

    # ── [4] 시기 분할 ──────────────────────────────────────────────────────
    print('\n[4] 시기 분할 — 국면 베팅인가')
    for k in [('저PBR', 0.10, 300), ('저PSR', 0.10, 300)]:
        rs = cells[k]
        h = len(rs) // 2
        a1, a2 = stat([r['net'] for r in rs[:h]]), stat([r['net'] for r in rs[h:]])
        print('  %-6s 전반(%s~%s) %+.3f t=%5.2f | 후반(%s~%s) %+.3f t=%5.2f'
              % (k[0], rs[0]['date'][:7], rs[h - 1]['date'][:7], a1['mean'], a1['t'],
                 rs[h]['date'][:7], rs[-1]['date'][:7], a2['mean'], a2['t']))
    print('  연도별(저PBR 10% 유니버스300 · 비용차감)')
    yr = {}
    for r in rows:
        yr.setdefault(r['date'][:4], []).append(r['net'])
    print('    ' + ' · '.join('%s %+.1f%%' % (y, sum(v)) for y, v in sorted(yr.items())))

    # ── [5] 자산곡선 ───────────────────────────────────────────────────────
    print('\n[5] 자산곡선과 낙폭 — 못 버티는 전략은 못 버는 전략이다')
    ps = [r['port'] - r['turn'] * COST for r in rows]
    pe, pm, pu = drawdown(ps)
    be, bm_, bu = drawdown([r['bm'] for r in rows])
    re_, rm, ru = drawdown([r['net'] for r in rows])
    print('  전략 %.2f배 · MDD %.1f%% · 최장부진 %d회' % (pe, pm, pu))
    print('  벤치 %.2f배 · MDD %.1f%% · 최장부진 %d회' % (be, bm_, bu))
    print('  초과 %.2f배 · MDD %.1f%% · 최장부진 %d회' % (re_, rm, ru))

    # ── [6] 독립성 ─────────────────────────────────────────────────────────
    print('\n[6] 저PBR 과 저PSR 은 독립 발견 2건인가')
    a = [r['net'] for r in cells[('저PBR', 0.10, 300)]]
    b = [r['net'] for r in cells[('저PSR', 0.10, 300)]]
    n = min(len(a), len(b))
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = math.sqrt(sum((a[i] - ma) ** 2 for i in range(n)))
    vb = math.sqrt(sum((b[i] - mb) ** 2 for i in range(n)))
    print('  월별 초과수익 상관 %.2f — 1 에 가까우면 같은 현상의 두 얼굴이다'
          % (cov / (va * vb) if va and vb else float('nan')))
    return 0


if __name__ == '__main__':
    sys.exit(main())

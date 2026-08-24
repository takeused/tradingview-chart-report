# 52주신고가 근접 스트레스 테스트 — 사전 등록(data/prereg_hi52_2026-08-24.md)대로만 돌린다
#
# 왜 있나 (2026-08-24, 4회차): 15.6년 재검정에서 가격 계열이 전부 죽었는데 이것 하나만
#   세 유니버스에서 일관되게 양수였다(상위 1000·20% 로그 t 2.28). 밸류에 걸었던 검사를
#   그대로 걸되, **격자와 통과 기준을 돌리기 전에 파일로 박고** 시작한다.
#
# **표본외는 없다.** 이 후보는 15.6년 전체를 보고 골랐다. 여기서 시기를 쪼개는 것은
#   표본내 분할이다. 그래서 이 스크립트는 "맞다"를 보이지 않는다 — **깨지는지**를 본다.
#
# 사용법
#   python scripts/study_hi52.py --market data/krx_marketdata_full.csv --start 2010-04-02

import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import round_trip_cost, stat, regime_of, PANELS
from study_factors import HORIZON, market_series
from study_clean_universe import run, by_score
from study_universe_audit import compound
from universe_pit import load_market, pool_cap
from study_value import cap_tercile, summarize

COST = round_trip_cost()
WINS = [26, 52, 104]          # 신고가 창(주)
FRACS = [0.05, 0.10, 0.20]
UNIS = [300, 500, 1000]
REF = (52, 0.20, 1000)        # 기준칸 — 사전 등록에 박아 둔 그것


def hi_score(P, n):
    """현재가 / n주 최고가. 1 에 가까울수록 신고가 근처."""
    def f(t, c):
        cl, hi = P.c[c], P.h[c]
        if cl[t] is None:
            return None
        hs = [hi[k] for k in range(max(0, t - n + 1), t + 1) if hi[k]]
        if len(hs) < n * 0.6:
            return None
        m = max(hs)
        return cl[t] / m if m else None
    return f


def beta_adjusted(rows, P, mkt):
    """포트폴리오 수익을 시장에 회귀해 남는 절편 — 시장 노출을 다르게 부른 것인지 가른다.

    시장 대용치로 `market_series`(전 패널 동일가중)를 쓰면 안 된다. 2026-08-24 확인 —
    월간 평균 +9.7%, 표준편차 **129%** 가 나온다. 초저가주 주간 폭등이 그대로 섞여
    들어와 회귀가 무의미해지고 β 가 0.00 으로 찍힌다. 유니버스 동일가중 보유
    수익률(`r['bm']`, 월 0.23%)이 이 검정에 맞는 시장이다 — 비교 대상도 그것이다.
    """
    xs, ys = [], []
    for r in rows:
        xs.append(r['bm'])
        ys.append(r['port'] - COST * r['turn'])
    if len(xs) < 20:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var if var else 0.0
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    sd = math.sqrt(sum(e * e for e in res) / (len(res) - 2))
    se = sd / math.sqrt(var) if var else None
    sea = sd * math.sqrt(1.0 / len(xs) + mx * mx / var) if var else None
    return {'alpha': a, 't': a / sea if sea else 0.0, 'beta': b, 'n': len(xs)}


def main():
    mpath = sys.argv[sys.argv.index('--market') + 1] if '--market' in sys.argv else None
    start = sys.argv[sys.argv.index('--start') + 1] if '--start' in sys.argv else '2010-04-02'
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_weekly_krx15.csv'))
    M = load_market(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', mpath)
                    ) if mpath else load_market()
    mkt = market_series(P)
    t0 = P.di[min(d for d in P.dates if d >= start)]

    print('52주신고가 스트레스 테스트 — %s ~ %s · 월간(%d주) · 왕복비용 %.2f%%'
          % (P.dates[t0], P.dates[-1], HORIZON, COST))
    print('사전 등록 data/prereg_hi52_2026-08-24.md · 표본외 없음(깨지는지만 본다)')
    print('')

    print('[1] 격자 — 창 3 x 분위 3 x 유니버스 3 = 27칸  (기준 ①: 양수 24칸 이상)')
    print('  %-6s %5s %5s %4s %9s %6s %8s %7s %8s'
          % ('창(주)', '분위', '유니', 'n', '산술%/월', 't', '로그 t', '회전율', '누적배수'))
    print('  ' + '-' * 72)
    cells, pos = {}, 0
    for w in WINS:
        for frac in FRACS:
            for uni in UNIS:
                rows = run(P, M, lambda t, u=uni: pool_cap(P, M, t, u),
                           by_score(hi_score(P, w)), t0, frac)
                if len(rows) < 20:
                    continue
                ari, log, turn = summarize(rows)
                cells[(w, frac, uni)] = rows
                pos += ari['mean'] > 0
                print('  %-6d %5.0f%% %5d %4d %9.3f %6.2f %8.2f %6.0f%% %8.2f'
                      % (w, frac * 100, uni, ari['n'], ari['mean'], ari['t'], log['t'],
                         turn * 100, compound([r['port'] - r['turn'] * COST for r in rows])))
    print('  → 27칸 중 산술 양수 %d칸 · 기준 ① %s' % (pos, '통과' if pos >= 24 else '실패'))

    rows = cells[REF]
    ari, log, turn = summarize(rows)
    print('\n[2] 기준칸 %d주 · %.0f%% · 상위%d  (기준 ②: 로그 t >= 2.0)'
          % (REF[0], REF[1] * 100, REF[2]))
    print('  산술 %+.3f%%/월 (t %.2f) · 로그 t %.2f · 회전율 %.0f%% · 기준 ② %s'
          % (ari['mean'], ari['t'], log['t'], turn * 100,
             '통과' if log['t'] >= 2.0 else '실패'))

    print('\n[3] β 조정 후 절편  (기준 ③: 양수)')
    ba = beta_adjusted(rows, P, mkt)
    if ba:
        print('  α %+.3f%%/월 (t %.2f) · β %.2f · n %d · 기준 ③ %s'
              % (ba['alpha'], ba['t'], ba['beta'], ba['n'],
                 '통과' if ba['alpha'] > 0 else '실패'))

    print('\n[4] 크기 중립성  (기준 ④: 대/중/소 3분위 각각 양수)')
    okc = 0
    for seg in ('대형', '중형', '소형'):
        rs = run(P, M, lambda t, s=seg: cap_tercile(P, M, t, pool_cap(P, M, t, 1000), s),
                 by_score(hi_score(P, 52)), t0, 0.20)
        if len(rs) >= 20:
            a, l, tn = summarize(rs)
            okc += a['mean'] > 0
            print('  %s 3분위 내 상위20%%  n=%3d · 산술 %+.3f t=%5.2f · 로그 t=%5.2f'
                  % (seg, a['n'], a['mean'], a['t'], l['t']))
    print('  기준 ④ %s' % ('통과' if okc == 3 else '실패'))

    print('\n[5] 비용 민감도  (기준 ⑤: 왕복 0.56%%에서도 양수)')
    gross = sum(r['port'] - r['bm'] for r in rows) / len(rows)
    for c in (0.28, 0.56):
        print('  왕복 %.2f%% → %+.3f%%/월' % (c, gross - c * turn))
    print('  기준 ⑤ %s' % ('통과' if gross - 0.56 * turn > 0 else '실패'))

    print('\n[6] 국면별  (기준 ⑥: 약세 손실 -1.5%%/월 이내)')
    reg = {}
    for r in rows:
        g = regime_of(P, P.di[r['date']], PANELS['weekly']['regime_back'])
        if g:
            reg.setdefault(g, []).append(r['net'])
    bear = None
    for g in ('강세', '횡보', '약세'):
        if g in reg:
            s = stat(reg[g])
            print('  %s n=%3d · 산술 %+.3f (t %.2f)' % (g, s['n'], s['mean'], s['t']))
            if g == '약세':
                bear = s['mean']
    print('  기준 ⑥ %s' % ('통과' if bear is not None and bear > -1.5 else '실패'))

    print('\n[7] 자산곡선')
    eq = compound([r['port'] - r['turn'] * COST for r in rows])
    bm = compound([r['bm'] for r in rows])
    print('  전략 %.2f배 · 벤치 %.2f배' % (eq, bm))
    return 0


if __name__ == '__main__':
    sys.exit(main())

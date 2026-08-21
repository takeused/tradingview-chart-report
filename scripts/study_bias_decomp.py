# 모멘텀 결과의 반전이 '편향 제거' 때문인지 '유니버스 정의 변경' 때문인지 분리한다
#
# 왜 있나 (2026-08-22): 고정 유니버스(오늘 시총 상위 300, TradingView)에서는 모멘텀
#   롱온리가 +1.78%/월(t=2.87, BH 통과)이었는데, 시점별 유니버스(FDR, 폐지 포함)로
#   바꾸니 -0.50%/월로 뒤집혔다. 그런데 그 사이에 세 가지가 동시에 바뀌었다.
#     (1) 생존편향 제거 — 상장폐지 종목이 들어왔다
#     (2) 유니버스 룩어헤드 제거 — 매 시점 그때 기준으로 유니버스를 다시 잡는다
#     (3) 유니버스 정의 변경 — 시총 상위 → 거래대금 상위
#   (3)이 원인이면 편향 이야기가 아니라 그냥 다른 전략을 본 것이다. 분리해야 한다.
#
# 어떻게 분리하는가 — **데이터 소스를 FDR 하나로 고정**하고 유니버스만 바꿔 가며 본다.
#   A) 오늘 살아있는 종목 중 오늘 거래대금 상위 300 (고정) — 편향 둘 다 있음
#   B) 오늘 살아있는 종목 중 매 시점 거래대금 상위 300 — 룩어헤드만 제거
#   C) 폐지 포함 전 종목 중 매 시점 거래대금 상위 300 — 둘 다 제거 (진짜 시점별)
#   A→B 차이 = 룩어헤드 기여, B→C 차이 = 생존편향 기여.
#
# 사용법
#   python scripts/study_bias_decomp.py [--top 300] [--back 52]

import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import PANELS, round_trip_cost, stat, _mom
from study_momentum import HORIZON, SKIP, pit_universe, PIT_LIQ_WEEKS

PANEL = 'panel_weekly_krx.csv'


def liquidity_at(P, t, code, weeks=PIT_LIQ_WEEKS):
    cl, vo = P.c[code], P.v[code]
    vals = [cl[k] * vo[k] for k in range(max(0, t - weeks), t)
            if cl[k] is not None and vo[k] is not None]
    return (sum(vals) / len(vals)) if len(vals) >= weeks * 0.7 else None


def alive_at_end(P):
    """마지막 시점에 시세가 있는 종목 = 오늘까지 살아남은 종목."""
    return {c for c in P.stocks if P.c[c][P.T - 1] is not None}


def grid(P, back, frac, cost, universe=None, pit_top=None, survivors_only=None):
    K = max(3, int(round((pit_top or (len(universe) if universe else len(P.stocks))) * frac)))
    lo, ls = [], []
    warm = max(PANELS['weekly']['warmup'], back + SKIP + 2)
    cache = {}
    for t in range(warm, P.T - HORIZON - 2, HORIZON):
        if pit_top:
            if t not in cache:
                pool = P.stocks if survivors_only is None else [c for c in P.stocks if c in survivors_only]
                scored = [(c, liquidity_at(P, t, c)) for c in pool
                          if P.c[c][t] is not None]
                scored = [x for x in scored if x[1] is not None]
                scored.sort(key=lambda x: -x[1])
                cache[t] = {c for c, _ in scored[:pit_top]}
            pool = list(cache[t])
        else:
            pool = list(universe)
        sc = [(c, _mom(P, c, t, back, SKIP)) for c in pool]
        sc = [x for x in sc if x[1] is not None]
        if len(sc) < max(20, 3 * K):
            continue
        rs = {c: P.ret_oo(c, t, HORIZON) for c, _ in sc}
        allr = [v for v in rs.values() if v is not None]
        if len(allr) < max(20, 3 * K):
            continue
        bm = sum(allr) / len(allr)
        sc.sort(key=lambda x: -x[1])
        top = [rs[c] for c, _ in sc[:K] if rs.get(c) is not None]
        bot = [rs[c] for c, _ in sc[-K:] if rs.get(c) is not None]
        if len(top) < K * 0.8 or len(bot) < K * 0.8:
            continue
        mt, mb = sum(top) / len(top), sum(bot) / len(bot)
        lo.append(mt - bm)
        ls.append(mt - mb)
    s_lo, s_ls = stat(lo), stat(ls)
    if not s_lo:
        return None
    return {'n': s_lo['n'],
            'lo_net': round(s_lo['mean'] - cost, 3), 'lo_t': s_lo['t'],
            'ls_net': round(s_ls['mean'] - 2 * cost, 3) if s_ls else None,
            'ls_t': s_ls['t'] if s_ls else None}


def main():
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 300
    back = int(sys.argv[sys.argv.index('--back') + 1]) if '--back' in sys.argv else 52
    cost = round_trip_cost()
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', PANEL))
    surv = alive_at_end(P)
    T = P.T - 1

    # A) 고정 유니버스 = 오늘 살아있는 종목 중 오늘 거래대금 상위 N
    scored = [(c, liquidity_at(P, T, c)) for c in surv]
    scored = [x for x in scored if x[1] is not None]
    scored.sort(key=lambda x: -x[1])
    fixed = {c for c, _ in scored[:top]}

    print('편향 분해 — 패널 %s · %d주 · 전체 %d종목(생존 %d) · 되돌 %d주 · 상위 %d · 월간 · 비용 %.2f%%'
          % (PANEL, P.T, len(P.stocks), len(surv), back, top, cost))
    print('데이터 소스를 FDR 하나로 고정하고 유니버스만 바꾼다 — 정의 변경 효과를 배제하기 위함')
    print('')
    print('%-46s %5s %11s %7s %11s %7s' % ('유니버스', 'n', '롱온리비용차감', 't', '롱숏비용차감', 't'))
    print('-' * 92)

    rows = [
        ('A) 오늘 거래대금 상위 %d 고정 (생존자만)' % top,
         grid(P, back, 0.10, cost, universe=fixed)),
        ('B) 매시점 거래대금 상위 %d (생존자만)' % top,
         grid(P, back, 0.10, cost, pit_top=top, survivors_only=surv)),
        ('C) 매시점 거래대금 상위 %d (폐지 포함)' % top,
         grid(P, back, 0.10, cost, pit_top=top)),
    ]
    for name, r in rows:
        if r is None:
            print('%-46s %5s %11s' % (name, '-', '표본부족'))
            continue
        print('%-46s %5d %11.3f %7.2f %11.3f %7.2f'
              % (name, r['n'], r['lo_net'], r['lo_t'],
                 r['ls_net'] if r['ls_net'] is not None else 0,
                 r['ls_t'] if r['ls_t'] is not None else 0))
    print('-' * 92)
    a, b, c = (x[1] for x in rows)
    if a and b and c:
        print('룩어헤드 기여 (A→B): %+.3f%%p · 생존편향 기여 (B→C): %+.3f%%p · 합계 %+.3f%%p'
              % (b['lo_net'] - a['lo_net'], c['lo_net'] - b['lo_net'], c['lo_net'] - a['lo_net']))
        print('※ A 가 양수이고 C 가 음수면, 앞서 본 모멘텀 초과수익은 편향의 산물이다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

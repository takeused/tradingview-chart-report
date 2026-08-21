# 횡단면 모멘텀 강건성 연구 — 사전 지정 격자를 한 번에 돌리고 전부 보고한다
#
# 왜 있나 (2026-08-22): 주봉 5.8년 검정에서 유일하게 세 국면 모두 양수였던 것이
#   'XS 모멘텀 52주(4주 스킵) 월간 리밸런싱' 하나였다(초과 +2.76%/회, t=2.21, n=60).
#   여기서 파라미터를 만지작거리면 그때부터는 과최적화다. 그래서 **격자를 미리 못 박고
#   한 번만 돌린 뒤 실패한 조합까지 전부 인쇄한다.**
#
# 반드시 같이 보는 것
#   1) **롱온리** — 한국 개인은 공매도가 사실상 막혀 있다. 롱숏 수치는 실행 불가능한 숫자다.
#      롱온리는 동일가중 보유 벤치마크 대비 초과로 본다(1다리 비용).
#   2) **국면별** — 강세장에서만 사는 것은 팩터가 아니라 베타다.
#   3) **격자 전체의 분포** — 한 칸만 좋고 이웃 칸이 나쁘면 그건 잡음이다.
#   4-b) **시점별 유니버스** (`--pit N`, 2026-08-22 추가) — 이게 진짜 해답이다.
#      매 리밸런싱 시점에 **그때 살아 있던 종목** 중 직전 12주 평균 거래대금 상위 N 을
#      유니버스로 잡는다. 상장폐지 종목이 그 시점까지는 포함되고, 나중에 커진 종목이
#      미리 들어오지도 않는다. `data/panel_weekly_krx.csv`(FDR, 폐지 포함)와 함께 쓴다.
#      시총 대신 거래대금을 쓰는 이유 — 과거 시점의 상장주식수를 구하기 어렵고,
#      거래대금은 관측값만으로 계산되며 매매 가능성(비용)과도 직결된다.
#
#   4) **시총 계층 진단** (2026-08-22 추가) — 유니버스가 '오늘 기준' 시총 상위라
#      과거 구간에는 룩어헤드가 있다. 그동안 커진 종목이 처음부터 목록에 있는 것이고,
#      하필 모멘텀 검정에는 가짜 수익을 만드는 최악의 조합이다.
#      편향이 원인이라면 **하위 계층(커져서 편입된 쪽)에서 효과가 훨씬 크게** 나온다.
#      상위 계층(메가캡, 편출입이 드묾)에서도 살아 있어야 신호로 본다.
#
# 사용법
#   python scripts/study_momentum.py [--cost 0.28] [--panel weekly_krx] [--pit 300]

import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import (PANELS, regime_of, round_trip_cost, stat, bh_reject, _mom)

# ── 사전 지정 격자 (돌리기 전에 확정. 돌려 보고 바꾸지 않는다) ──────────────
LOOKBACKS = [26, 39, 52]     # 되돌아보기(주)
SKIP = 4                     # 최근 4주 제외 — 단기 반전 회피, 학계 표준
FRACS = [0.05, 0.10, 0.20]   # 분위 비율(유니버스 크기와 무관하게 비교하려면 개수가 아니라 비율)
HORIZON = 4                  # 월간 리밸런싱
TIERS = [(1, 100), (101, 200), (201, 300)]   # 시총 계층 진단 구간


def _spread(P, t, sc, K, rs, bm):
    sc.sort(key=lambda x: -x[1])
    top = [rs[c] for c, _ in sc[:K] if rs.get(c) is not None]
    bot = [rs[c] for c, _ in sc[-K:] if rs.get(c) is not None]
    if len(top) < K * 0.8 or len(bot) < K * 0.8:
        return None, None
    mt, mb = sum(top) / len(top), sum(bot) / len(bot)
    return mt - mb, mt - bm


PIT_LIQ_WEEKS = 12       # 유니버스 선정에 쓰는 거래대금 평균 창(주)


def pit_universe(P, t, top_n):
    """t 시점에 살아 있던 종목 중 직전 12주 평균 거래대금 상위 N.

    '살아 있다' 는 t 시점에 종가와 거래량이 있다는 뜻이다. 나중에 폐지된 종목도
    그때까지는 포함되고(생존편향 제거), 나중에 커진 종목이 미리 들어오지도 않는다.
    """
    out = []
    for c in P.stocks:
        cl, vo = P.c[c], P.v[c]
        if t >= P.T or cl[t] is None or vo[t] is None:
            continue
        vals = [cl[k] * vo[k] for k in range(max(0, t - PIT_LIQ_WEEKS), t)
                if cl[k] is not None and vo[k] is not None]
        if len(vals) < PIT_LIQ_WEEKS * 0.7:
            continue
        out.append((c, sum(vals) / len(vals)))
    out.sort(key=lambda x: -x[1])
    return {c for c, _ in out[:top_n]}


def run_grid(P, spec, cost, fracs=FRACS, universe=None, pit_top=None):
    """universe 를 주면 그 종목만 쓴다(시총 계층 진단용).
    pit_top 을 주면 매 시점 거래대금 상위 N 으로 유니버스를 다시 잡는다(시점별)."""
    RB = spec['regime_back']
    stocks = [c for c in P.stocks if (universe is None or c in universe)]
    rows = []
    pit_cache = {}
    for back in LOOKBACKS:
        for fr in fracs:
            K = max(3, int(round((pit_top or len(stocks)) * fr)))
            ls, lo = [], []
            reg_ls, reg_lo = {}, {}
            warm = max(spec['warmup'], back + SKIP + 2)
            for t in range(warm, P.T - HORIZON - 2, HORIZON):
                if pit_top:
                    if t not in pit_cache:
                        pit_cache[t] = pit_universe(P, t, pit_top)
                    pool = [c for c in stocks if c in pit_cache[t]]
                else:
                    pool = stocks
                sc = [(c, _mom(P, c, t, back, SKIP)) for c in pool]
                sc = [x for x in sc if x[1] is not None]
                if len(sc) < max(20, 3 * K):
                    continue
                rs = {c: P.ret_oo(c, t, HORIZON) for c, _ in sc}
                allr = [v for v in rs.values() if v is not None]
                if len(allr) < max(20, 3 * K):
                    continue
                bm = sum(allr) / len(allr)
                a, b = _spread(P, t, sc, K, rs, bm)
                if a is None:
                    continue
                g = regime_of(P, t, RB)
                ls.append(a)
                lo.append(b)
                if g:
                    reg_ls.setdefault(g, []).append(a)
                    reg_lo.setdefault(g, []).append(b)
            s_ls, s_lo = stat(ls), stat(lo)
            if not s_ls or not s_lo:
                continue
            rows.append({
                'back': back, 'frac': fr, 'K': K, 'n_universe': len(stocks),
                'ls': s_ls, 'ls_net': round(s_ls['mean'] - 2 * cost, 3),
                'lo': s_lo, 'lo_net': round(s_lo['mean'] - 1 * cost, 3),
                'ls_reg': {g: round(stat(v)['mean'] - 2 * cost, 2)
                           for g, v in reg_ls.items() if stat(v)},
                'lo_reg': {g: round(stat(v)['mean'] - 1 * cost, 2)
                           for g, v in reg_lo.items() if stat(v)},
            })
    return rows


def load_tiers():
    """유니버스 CSV 에서 시총 계층을 읽는다. 없으면 계층 진단을 건너뛴다."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data',
                     'universe_top300.csv')
    if not os.path.exists(p):
        return None
    import csv
    out = {}
    for r in csv.DictReader(open(p, encoding='utf-8')):
        out[r['code']] = int(r['mcap_rank'])
    return out


def main():
    cost = round_trip_cost()
    if '--cost' in sys.argv:
        cost = float(sys.argv[sys.argv.index('--cost') + 1])
    which = sys.argv[sys.argv.index('--panel') + 1] if '--panel' in sys.argv else 'weekly'
    pit = int(sys.argv[sys.argv.index('--pit') + 1]) if '--pit' in sys.argv else None
    spec = PANELS['weekly']
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data',
                        'panel_%s.csv' % which)
    P = panel_io.load(path)
    rows = run_grid(P, spec, cost, pit_top=pit)
    if not rows:
        print('격자에서 유효한 조합이 없다.')
        return 1

    rej_lo = bh_reject([r['lo']['p'] for r in rows])
    rej_ls = bh_reject([r['ls']['p'] for r in rows])

    print('횡단면 모멘텀 강건성 — 패널 %s · %d주 · 종목 %d · 월간(%d주) · 왕복비용 %.2f%%'
          % (which, P.T, len(P.stocks), HORIZON, cost))
    if pit:
        print('**시점별 유니버스** — 매 시점 직전 %d주 거래대금 상위 %d종목 '
              '(상장폐지 종목 포함, 유니버스 룩어헤드 없음)' % (PIT_LIQ_WEEKS, pit))
    else:
        print('※ 고정 유니버스 — 오늘 기준 목록이라 과거 구간에 룩어헤드가 있다(--pit 로 해소)')
    print('격자: 되돌아보기 %s주 x 분위비율 %s (스킵 %d주 고정) — 사전 지정, 사후 조정 없음'
          % (LOOKBACKS, FRACS, SKIP))
    print('')
    print('%-6s %-6s %-4s %5s | %9s %6s %8s %3s | %9s %6s %8s %3s'
          % ('되돌', '분위', '종목', 'n', '롱숏초과%', 't', '비용차감', 'BH',
             '롱온리초과%', 't', '비용차감', 'BH'))
    print('-' * 112)
    for r, a, b in zip(rows, rej_ls, rej_lo):
        print('%-6d %-6.0f%% %-4d %5d | %9.3f %6.2f %8.3f %3s | %9.3f %6.2f %8.3f %3s'
              % (r['back'], r['frac'] * 100, r['K'], r['lo']['n'],
                 r['ls']['mean'], r['ls']['t'], r['ls_net'], 'O' if a else '-',
                 r['lo']['mean'], r['lo']['t'], r['lo_net'], 'O' if b else '-'))
    print('-' * 112)

    print('\n국면별 비용차감 초과수익 (롱온리 — 개인이 실제로 실행 가능한 쪽)')
    for r in rows:
        g = r['lo_reg']
        print('  되돌 %2d주 · 분위 %.0f%%  %s' % (r['back'], r['frac'] * 100,
              ' / '.join('%s %+.2f' % (k, g[k]) for k in ('강세', '횡보', '약세') if k in g)))

    lo_pos = sum(1 for r in rows if r['lo_net'] > 0)
    lo_all = sum(1 for r in rows if r['lo_net'] > 0 and len(r['lo_reg']) >= 3
                 and all(v > 0 for v in r['lo_reg'].values()))
    print('\n격자 %d칸 — 롱온리 비용차감 양수 %d칸 · 세 국면 모두 양수 %d칸'
          % (len(rows), lo_pos, lo_all))

    # ── 시총 계층 진단 (유니버스 룩어헤드) ──
    tiers = load_tiers()
    if tiers and len(P.stocks) > 100 and not pit:
        print('\n시총 계층 진단 — 유니버스 룩어헤드가 원인이면 하위 계층에서 효과가 커진다')
        print('%-12s %5s | %10s %6s | %s' % ('계층', '종목', '롱온리비용차감', 't', '국면별'))
        for lo_r, hi_r in TIERS:
            uni = {c for c, rk in tiers.items() if lo_r <= rk <= hi_r and c in P.stocks}
            if len(uni) < 40:
                continue
            sub = run_grid(P, spec, cost, fracs=[0.10], universe=uni)
            for r in sub:
                if r['back'] != 52:
                    continue
                g = r['lo_reg']
                print('%-12s %5d | %10.3f %6.2f | %s'
                      % ('%d~%d위' % (lo_r, hi_r), len(uni), r['lo_net'], r['lo']['t'],
                         ' / '.join('%s %+.2f' % (k, g[k])
                                    for k in ('강세', '횡보', '약세') if k in g)))
        print('  (되돌 52주 · 분위 10%% 기준. 상위 계층에서도 살아 있어야 신호로 본다)')

    print('\n판정 — 이웃 칸이 함께 양수여야 신호다. 한 칸만 좋으면 잡음으로 본다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

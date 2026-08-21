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
#
# 사용법
#   python scripts/study_momentum.py [--cost 0.28]

import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import (PANELS, regime_of, round_trip_cost, stat, bh_reject, _mom)

# ── 사전 지정 격자 (돌리기 전에 확정. 돌려 보고 바꾸지 않는다) ──────────────
LOOKBACKS = [26, 39, 52]     # 되돌아보기(주)
SKIP = 4                     # 최근 4주 제외 — 단기 반전 회피, 학계 표준
KS = [5, 10, 15]             # 분위당 종목 수
HORIZON = 4                  # 월간 리밸런싱


def run_grid(P, spec, cost):
    RB = spec['regime_back']
    rows = []
    for back in LOOKBACKS:
        for K in KS:
            ls, lo = [], []
            reg_ls, reg_lo = {}, {}
            warm = max(spec['warmup'], back + SKIP + 2)
            for t in range(warm, P.T - HORIZON - 2, HORIZON):
                sc = [(c, _mom(P, c, t, back, SKIP)) for c in P.stocks]
                sc = [x for x in sc if x[1] is not None]
                if len(sc) < 30:
                    continue
                rs = {c: P.ret_oo(c, t, HORIZON) for c, _ in sc}
                allr = [v for v in rs.values() if v is not None]
                if len(allr) < 30:
                    continue
                bm = sum(allr) / len(allr)
                sc.sort(key=lambda x: -x[1])
                top = [rs[c] for c, _ in sc[:K] if rs[c] is not None]
                bot = [rs[c] for c, _ in sc[-K:] if rs[c] is not None]
                if len(top) < K * 0.8 or len(bot) < K * 0.8:
                    continue
                mt, mb = sum(top) / len(top), sum(bot) / len(bot)
                g = regime_of(P, t, RB)
                ls.append(mt - mb)
                lo.append(mt - bm)                     # 롱온리: 벤치마크 대비 초과
                if g:
                    reg_ls.setdefault(g, []).append(mt - mb)
                    reg_lo.setdefault(g, []).append(mt - bm)
            s_ls, s_lo = stat(ls), stat(lo)
            if not s_ls or not s_lo:
                continue
            rows.append({
                'back': back, 'K': K,
                'ls': s_ls, 'ls_net': round(s_ls['mean'] - 2 * cost, 3),
                'lo': s_lo, 'lo_net': round(s_lo['mean'] - 1 * cost, 3),
                'ls_reg': {g: round(stat(v)['mean'] - 2 * cost, 2)
                           for g, v in reg_ls.items() if stat(v)},
                'lo_reg': {g: round(stat(v)['mean'] - 1 * cost, 2)
                           for g, v in reg_lo.items() if stat(v)},
            })
    return rows


def main():
    cost = round_trip_cost()
    if '--cost' in sys.argv:
        cost = float(sys.argv[sys.argv.index('--cost') + 1])
    spec = PANELS['weekly']
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   '..', 'data', spec['file']))
    rows = run_grid(P, spec, cost)
    if not rows:
        print('격자에서 유효한 조합이 없다.')
        return 1

    rej_lo = bh_reject([r['lo']['p'] for r in rows])
    rej_ls = bh_reject([r['ls']['p'] for r in rows])

    print('횡단면 모멘텀 강건성 — 주봉 %d주 · 종목 %d · 월간(%d주) 리밸런싱 · 왕복비용 %.2f%%'
          % (P.T, len(P.stocks), HORIZON, cost))
    print('격자: 되돌아보기 %s주 x 분위 %s종목 (스킵 %d주 고정) — 사전 지정, 사후 조정 없음'
          % (LOOKBACKS, KS, SKIP))
    print('')
    print('%-6s %-4s %5s | %9s %6s %8s %3s | %9s %6s %8s %3s'
          % ('되돌', '분위', 'n', '롱숏초과%', 't', '비용차감', 'BH', '롱온리초과%', 't', '비용차감', 'BH'))
    print('-' * 104)
    for r, a, b in zip(rows, rej_ls, rej_lo):
        print('%-6d %-4d %5d | %9.3f %6.2f %8.3f %3s | %9.3f %6.2f %8.3f %3s'
              % (r['back'], r['K'], r['lo']['n'],
                 r['ls']['mean'], r['ls']['t'], r['ls_net'], 'O' if a else '-',
                 r['lo']['mean'], r['lo']['t'], r['lo_net'], 'O' if b else '-'))
    print('-' * 104)

    print('\n국면별 비용차감 초과수익 (롱온리 — 개인이 실제로 실행 가능한 쪽)')
    print('%-6s %-4s  %s' % ('되돌', '분위', '강세 / 횡보 / 약세'))
    for r in rows:
        g = r['lo_reg']
        print('%-6d %-4d  %s' % (r['back'], r['K'],
              ' / '.join('%s %+.2f' % (k, g[k]) for k in ('강세', '횡보', '약세') if k in g)))

    lo_pos = sum(1 for r in rows if r['lo_net'] > 0)
    lo_all = sum(1 for r in rows
                 if r['lo_net'] > 0 and len(r['lo_reg']) >= 3
                 and all(v > 0 for v in r['lo_reg'].values()))
    print('\n격자 %d칸 — 롱온리 비용차감 양수 %d칸 · 세 국면 모두 양수 %d칸'
          % (len(rows), lo_pos, lo_all))
    print('판정 — 이웃 칸이 함께 양수여야 신호다. 한 칸만 좋으면 잡음으로 본다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

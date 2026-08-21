# 저변동성을 실제로 태울 수 있는가 — 시기 분할 · 경로 · 낙폭 · 전진 선택
#
# 왜 있나 (2026-08-22, 2회차): 지금까지 이 팩터를 평균과 t 로만 봤다. 그런데 돈을 넣는
#   결정에는 그 둘로 부족하다.
#     (a) 15.6년 평균이 양수여도 **앞뒤 반이 다르면** 이미 죽은 팩터일 수 있다
#     (b) 평균이 같아도 **낙폭이 40%면 못 버틴다**. 못 버티는 전략은 못 버는 전략이다
#     (c) 27칸 중 제일 좋은 칸을 사후에 고르는 건 검정이 아니다. 실전은 **그 시점까지의
#         정보만으로 칸을 골라야 한다**. 그래서 전진 선택을 따로 돌린다
#
# 무엇을 새로 하는가
#   - 비용을 **매 시점 실측 회전율로** 물린다(기존은 전체 평균 회전율 한 값)
#   - 벤치마크(시점별 유니버스 동일가중) 대비 **상대 자산곡선**과 최대낙폭을 낸다
#   - 27칸 중 사후 최적이 아니라 **과거만 보고 고른 칸**의 성적을 낸다(음성 대조군: 무작위 칸)
#
# 사용법
#   python scripts/study_lowvol_path.py [--panel weekly_krx15] [--min-hist 24]

import math, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import PANELS, regime_of, round_trip_cost, stat
from study_factors import (HORIZON, WARMUP, market_series, pit_pool,
                           _rets, _std, _ivol, _maxret)
from study_lowvol import MEASURES, LOOKBACKS, UNIVERSES, FRAC


def cell_series(P, mkt, fn, back, pit, frac, cost):
    """한 칸의 시점별 기록. 비용은 그 시점 실측 회전율로 물린다."""
    K = max(5, int(round(pit * frac)))
    out = []
    prev = None
    for t in range(WARMUP, P.T - HORIZON - 2, HORIZON):
        pool = pit_pool(P, t, pit)
        if len(pool) < max(30, 3 * K):
            continue
        r = {c: P.ret_oo(c, t, HORIZON) for c in pool}
        vals = [v for v in r.values() if v is not None]
        if len(vals) < 30:
            continue
        bm = sum(vals) / len(vals)
        sc = []
        for c in pool:
            try:
                v = fn(P, c, t, mkt, back)
            except Exception:
                v = None
            if v is not None and math.isfinite(v):
                sc.append((c, v))
        if len(sc) < max(30, 3 * K):
            continue
        sc.sort(key=lambda x: -x[1])
        sel = [c for c, _ in sc[:K]]
        top = [r[c] for c in sel if r.get(c) is not None]
        if len(top) < K * 0.8:
            continue
        turn = 1.0 if prev is None else 1 - len(set(sel) & prev) / float(K)
        prev = set(sel)
        port = sum(top) / len(top)
        out.append({'t': t, 'date': P.dates[t], 'port': port, 'bm': bm,
                    'turn': turn, 'net': port - bm - cost * turn})
    return out


def drawdown(xs):
    """누적곱 자산곡선의 최대낙폭(%)과 최장 부진 구간(관측 수)."""
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


def show_path(name, rows):
    """전략·벤치마크 절대 경로와 상대(초과) 경로를 함께 본다."""
    ps = [r['port'] - r['turn'] * COST for r in rows]
    bs = [r['bm'] for r in rows]
    rs = [r['net'] for r in rows]
    pe, pmdd, pu = drawdown(ps)
    be, bmdd, bu = drawdown(bs)
    re_, rmdd, ru = drawdown(rs)
    print('%-18s %8.2f배 %8.1f%% %6d회 | %7.2f배 %8.1f%% %6d회 | %7.2f배 %8.1f%% %6d회'
          % (name, pe, pmdd, pu, be, bmdd, bu, re_, rmdd, ru))


def yearly(rows):
    out = {}
    for r in rows:
        out.setdefault(r['date'][:4], []).append(r['net'])
    return out


COST = round_trip_cost()


def main():
    which = sys.argv[sys.argv.index('--panel') + 1] if '--panel' in sys.argv else 'weekly_krx15'
    min_hist = int(sys.argv[sys.argv.index('--min-hist') + 1]) if '--min-hist' in sys.argv else 24
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_%s.csv' % which))
    mkt = market_series(P)

    print('저변동성 실전성 검정 — 패널 %s · %d주 · %d종목 · 월간(%d주) · 왕복비용 %.2f%%'
          % (which, P.T, len(P.stocks), HORIZON, COST))
    print('비용은 매 시점 실측 회전율로 물린다(전체 평균 한 값이 아니다).')
    print('')

    cells = {}
    for mname, fn in MEASURES.items():
        for back in LOOKBACKS:
            for pit in UNIVERSES:
                s = cell_series(P, mkt, fn, back, pit, FRAC, COST)
                if len(s) >= 40:
                    cells[(mname, back, pit)] = s
    keys = sorted(cells)
    n = min(len(cells[k]) for k in keys)
    print('격자 %d칸 · 시점 %d회 (%s ~ %s)'
          % (len(keys), n, cells[keys[0]][0]['date'], cells[keys[0]][-1]['date']))

    # ── 1. 시기 분할 ────────────────────────────────────────────────────────
    print('\n[1] 시기 분할 — 앞뒤 반이 같은 팩터인가')
    half = n // 2
    mid = cells[keys[0]][half]['date']
    print('  분할점 %s · 각 %d시점' % (mid, half))
    print('  %-30s %10s %10s %8s' % ('칸', '전반%/월', '후반%/월', '후반t'))
    pos_a = pos_b = 0
    for k in keys:
        s = cells[k]
        a = [r['net'] for r in s[:half]]
        b = [r['net'] for r in s[half:]]
        sa, sb = stat(a), stat(b)
        if not sa or not sb:
            continue
        pos_a += sa['mean'] > 0
        pos_b += sb['mean'] > 0
        if k[0] == '수익률표준편차' or (k[1] == 26 and k[2] == 300):
            print('  %-30s %10.3f %10.3f %8.2f'
                  % ('%s %d주 상위%d' % k, sa['mean'], sb['mean'], sb['t']))
    print('  전반 양수 %d/%d칸 · 후반 양수 %d/%d칸' % (pos_a, len(keys), pos_b, len(keys)))

    # ── 2. 연도별 ──────────────────────────────────────────────────────────
    ref = ('수익률표준편차', 26, 300)
    print('\n[2] 연도별 초과수익 (기준칸 %s %d주 상위%d · 비용차감)' % ref)
    ys = yearly(cells[ref])
    neg = 0
    for y in sorted(ys):
        v = sum(ys[y])
        neg += v < 0
        print('  %s %+7.2f%% (%d회) %s' % (y, v, len(ys[y]), '■' * int(abs(v) / 2) if v > 0 else '□' * int(abs(v) / 2)))
    print('  음수 해 %d/%d' % (neg, len(ys)))

    # ── 3. 경로와 낙폭 ─────────────────────────────────────────────────────
    print('\n[3] 자산곡선과 낙폭 — 못 버티는 전략은 못 버는 전략이다')
    print('%-18s %8s %9s %6s | %7s %9s %6s | %7s %9s %6s'
          % ('', '전략배수', '전략MDD', '부진', '벤치배수', '벤치MDD', '부진', '초과배수', '초과MDD', '부진'))
    for k in [ref, ('이질변동성', 52, 150), ('MAX주간수익률', 26, 300)]:
        if k in cells:
            show_path('%s %d주 상위%d' % k, cells[k])

    # ── 4. 전진 선택 ───────────────────────────────────────────────────────
    print('\n[4] 전진 선택 — 그 시점까지의 정보만으로 칸을 고른다')
    print('  최소 이력 %d시점. 사후 최적 칸 고르기(=지금까지 해온 것)와 비교한다.' % min_hist)
    fwd, chosen = [], []
    for i in range(min_hist, n):
        best, bv = None, None
        for k in keys:
            h = [r['net'] for r in cells[k][:i]]
            m = sum(h) / len(h)
            if bv is None or m > bv:
                best, bv = k, m
        fwd.append(cells[best][i]['net'])
        chosen.append(best)
    sf = stat(fwd)
    print('  전진 선택      %+.3f%%/월 · t=%.2f · n=%d' % (sf['mean'], sf['t'], sf['n']))

    tail = {k: stat([r['net'] for r in cells[k][min_hist:n]]) for k in keys}
    bestk = max(keys, key=lambda k: tail[k]['mean'])
    print('  사후 최적 칸   %+.3f%%/월 · t=%.2f  (%s %d주 상위%d) ← 실전에선 못 고른다'
          % (tail[bestk]['mean'], tail[bestk]['t'], bestk[0], bestk[1], bestk[2]))
    avg = sum(tail[k]['mean'] for k in keys) / len(keys)
    print('  27칸 평균      %+.3f%%/월  ← 아무 칸이나 골랐을 때의 기대' % avg)

    random.seed(7)
    rnd = [cells[random.choice(keys)][i]['net'] for i in range(min_hist, n)]
    sr = stat(rnd)
    print('  [대조] 무작위 칸 %+.3f%%/월 · t=%.2f' % (sr['mean'], sr['t']))

    swaps = sum(1 for a, b in zip(chosen, chosen[1:]) if a != b)
    top = max(set(chosen), key=chosen.count)
    print('  선택이 바뀐 횟수 %d/%d · 최다선택 %s %d주 상위%d (%d회)'
          % (swaps, len(chosen) - 1, top[0], top[1], top[2], chosen.count(top)))
    fe, fmdd, fu = drawdown(fwd)
    print('  전진 선택 초과 자산곡선 %.2f배 · 최대낙폭 %.1f%% · 최장부진 %d회'
          % (fe, fmdd, fu))
    return 0


if __name__ == '__main__':
    sys.exit(main())

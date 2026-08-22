# 무수정 원자료 유니버스로 재검정 — 오염을 제거한 뒤 팩터가 남는가
#
# 왜 있나 (2026-08-22, 2회차): 유니버스 감사에서 기존 `pit_pool` 이 미래 분할·감자 정보를
#   담고 있음이 드러났다(벤치마크가 15.6년간 -88%). 공공데이터포털 금융위원회_주식시세정보로
#   **무수정 시가총액·거래대금**을 받아 유니버스를 다시 정의하고 같은 검정을 돌린다.
#
#   자료 범위가 2020-01-02 ~ 2026-08-20 이라 표본이 6.6년(리밸런싱 약 85회)뿐이다.
#   짧다. 그래서 이 결과는 "오염을 걷어내면 무엇이 남는가"의 1차 답이지 최종 판정이 아니다.
#   수익률은 계속 수정주가 패널에서 가져온다(분할이 수익률을 만들면 안 되므로 그쪽이 맞다).
#
# 오염 규모 — 2020-01-03 시점 종목의 **40%가 이후 corporate action 을 겪었다.**
#   수정계수 f 는 0.002 ~ 19.3 범위였다. f=0.002 면 그 종목의 계산 거래대금이 500배 부풀려진다.
#
# 사용법
#   python scripts/study_clean_universe.py [--panel weekly_krx15]

import math, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import round_trip_cost, stat
from study_factors import HORIZON, _rets, _std, _maxret
from study_universe_audit import compound, BIG
from universe_pit import load_market, pool_cap, pool_value

COST = round_trip_cost()
START = '2020-04-03'      # 원자료 시작(2020-01-02) + 유니버스 되돌아보기 12주


def run(P, M, pool_fn, sel_fn, t_from, frac=0.10):
    out, prev = [], None
    for t in range(t_from, P.T - HORIZON - 2, HORIZON):
        pool = pool_fn(t)
        if len(pool) < 60:
            continue
        r = {c: P.ret_oo(c, t, HORIZON) for c in pool}
        vals = [v for v in r.values() if v is not None]
        if len(vals) < 30:
            continue
        bm = sum(vals) / len(vals)
        K = max(5, int(round(len(pool) * frac)))
        sel = sel_fn(t, pool, K)
        if sel is None:
            continue
        top = [r[c] for c in sel if r.get(c) is not None]
        if len(top) < K * 0.8:
            continue
        turn = 1.0 if prev is None else 1 - len(set(sel) & prev) / float(K)
        prev = set(sel)
        port = sum(top) / len(top)
        out.append({'date': P.dates[t], 'port': port, 'bm': bm, 'turn': turn,
                    'net': port - bm - COST * turn, 'n': len(pool)})
    return out


def by_score(score_fn):
    def f(t, pool, K):
        sc = []
        for c in pool:
            v = score_fn(t, c)
            if v is not None and math.isfinite(v):
                sc.append((c, v))
        if len(sc) < max(30, 3 * K):
            return None
        sc.sort(key=lambda x: -x[1])
        return [c for c, _ in sc[:K]]
    return f


def line(name, rows):
    ari = stat([r['net'] for r in rows])
    log = stat([100 * (math.log(1 + (r['port'] - COST * r['turn']) / 100)
                       - math.log(1 + r['bm'] / 100)) for r in rows])
    pe = compound([r['port'] - r['turn'] * COST for r in rows])
    be = compound([r['bm'] for r in rows])
    print('  %-22s n=%3d | 산술 %+.3f t=%5.2f | 로그 %+.3f t=%5.2f | 누적 %.2f배 vs %.2f배'
          % (name, ari['n'], ari['mean'], ari['t'], log['mean'], log['t'], pe, be))
    return ari


def main():
    which = sys.argv[sys.argv.index('--panel') + 1] if '--panel' in sys.argv else 'weekly_krx15'
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_%s.csv' % which))
    M = load_market()
    t0 = P.di[min(d for d in P.dates if d >= START)]

    print('무수정 원자료 유니버스 재검정 — 패널 %s · 표본 %s ~ %s · 월간(%d주) · 비용 %.2f%%'
          % (which, P.dates[t0], P.dates[-1], HORIZON, COST))
    print('유니버스와 시가총액은 공공데이터포털 무수정 원자료, 수익률은 수정주가 패널.')
    print('')

    # ── [0] 벤치마크 온전성 ─────────────────────────────────────────────────
    print('[0] 벤치마크 온전성 — 6.6년 누적이 상식적인가')
    big = [c for c in BIG if c in P.c]
    bigret = []
    for t in range(t0, P.T - HORIZON - 2, HORIZON):
        rs = [x for x in (P.ret_oo(c, t, HORIZON) for c in big) if x is not None]
        if len(rs) >= 10:
            bigret.append(sum(rs) / len(rs))
    print('  고정 대형주 %d종목 동일가중        %.2f배  ← 기준점' % (len(big), compound(bigret)))
    pools = [('시가총액 상위300', lambda t: pool_cap(P, M, t, 300)),
             ('시가총액 상위500', lambda t: pool_cap(P, M, t, 500)),
             ('거래대금 상위300(무수정)', lambda t: pool_value(P, M, t, 300))]
    for nm, fn in pools:
        rs = run(P, M, fn, lambda t, pool, K: pool, t0, 1.0)
        print('  %-24s %.2f배 (평균 %d종목)'
              % (nm, compound([r['bm'] for r in rs]), sum(r['n'] for r in rs) / len(rs)))

    # ── [1] 저변동성 ───────────────────────────────────────────────────────
    print('\n[1] 저변동성 — 오염 제거 후')
    for nm, fn in pools[:2]:
        print(' [%s]' % nm)
        for back in (13, 26, 52):
            sel = by_score(lambda t, c, b=back: (lambda s: None if s is None else -s)
                           (_std(_rets(P, c, t, b))))
            line('저변동 %d주' % back, run(P, M, fn, sel, t0))
        sel = by_score(lambda t, c: (lambda x: None if x is None else -x)(_maxret(P, c, t, 12)))
        line('MAX낮음 12주', run(P, M, pools[0][1] if nm == pools[0][0] else fn, sel, t0))

    # ── [2] 음성 대조군 ────────────────────────────────────────────────────
    print('\n[2] 음성 대조군 — 난수 팩터. 여기서 유의하게 나오면 하네스가 고장난 것이다')
    random.seed(11)
    noise = {}
    sel = by_score(lambda t, c: noise.setdefault((t, c), random.random()))
    line('난수', run(P, M, pools[0][1], sel, t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())

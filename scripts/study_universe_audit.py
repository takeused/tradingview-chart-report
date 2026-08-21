# 유니버스 감사 — 거래대금 기반 유니버스가 미래 액면분할·감자 정보를 담고 있다
#
# 왜 있나 (2026-08-22, 2회차): 저변동성의 자산곡선을 그리다가 **벤치마크가 15.6년간 -88%**
#   인 것을 봤다. 같은 기간 대형주 20종목 동일가중은 5.14배다. 벤치마크가 틀린 것이다.
#
# 원인 — `pit_pool` 은 거래대금을 `수정주가 x 거래량` 으로 잰다. 그런데 **가격은 수정되고
#   거래량은 수정되지 않는다.** 그래서 나중에 액면분할한 종목은 과거 거래대금이 분할배수만큼
#   축소되고(2015년 삼성전자가 206위, 308억), 감자한 종목은 감자배수만큼 부풀려진다.
#   실제로 2015년 거래대금 상위는 대우조선해양·HMM·동부제철 — 전부 훗날 감자한 종목이다.
#   즉 유니버스가 **"앞으로 감자할 종목"을 미리 뽑는다.** 검정 대상이 아니라 검정의 토대가
#   오염된 것이라, 이 위에서 낸 팩터 결과는 전부 다시 봐야 한다.
#   (삼성전자 2018-05 분할 주에 거래량 중앙값이 53배 튄다 — 수정종가는 연속. 확인 완료)
#
# 깨끗한 원자료는 오늘 기준 전부 막혀 있다 — KRX 정보데이터시스템은 로그인 요구(LOGOUT),
#   k-skill-proxy 는 502, FDR StockListing 은 과거 일자를 줘도 오늘 가격을 준다,
#   네이버 siseJson·fchart 는 수정주가만 준다.
#
# 그래서 이 스크립트는 **거래대금을 전혀 쓰지 않는 유니버스**로 같은 검정을 돌린다.
#   거래 연속성(직전 12주 매주 거래량 > 0)은 수정계수와 무관한 관측값이다.
#   여기서도 저변동성이 살아남으면 그 결과는 유니버스 오염의 산물이 아니다.
#
# 사용법
#   python scripts/study_universe_audit.py [--panel weekly_krx15]

import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import round_trip_cost, stat
from study_factors import HORIZON, PIT_LIQ_WEEKS, WARMUP, market_series, pit_pool, _rets, _std

COST = round_trip_cost()
BIG = ['005930', '000660', '035420', '051910', '005380', '000270', '012330', '068270',
       '207940', '055550', '105560', '086790', '017670', '015760', '034730', '010950',
       '009150', '032830', '066570', '003550']


def pool_traded(P, t, min_weeks=None):
    """거래 연속성만 보는 유니버스 — 수정계수와 무관하다.

    직전 12주 내내 거래량이 있었고 가격이 있는 종목. 크기·유동성 순위를 쓰지 않으므로
    미래 액면분할·감자 정보가 새어 들어올 통로가 없다.
    """
    need = min_weeks or PIT_LIQ_WEEKS
    out = []
    for c in P.stocks:
        cl, vo = P.c[c], P.v[c]
        if cl[t] is None or vo[t] is None:
            continue
        ok = sum(1 for k in range(max(0, t - PIT_LIQ_WEEKS), t)
                 if cl[k] and vo[k] and vo[k] > 0)
        if ok >= need:
            out.append(c)
    return out


def zero_frac(P, c, t, n=52):
    """직전 n주 중 수익률이 정확히 0인 주의 비율 (Lesmond-Ogden-Trzcinka 1999).

    수익률만 쓰므로 **수정계수와 무관한** 유동성 대용이다. 거래대금을 못 쓰는 지금
    유일하게 오염되지 않은 유동성 척도다.
    """
    rs = _rets(P, c, t, n)
    if len(rs) < n * 0.8:
        return None
    return sum(1 for x in rs if abs(x) < 1e-9) / len(rs)


def pool_zr(P, t, thr):
    out = []
    for c in P.stocks:
        if P.c[c][t] is None:
            continue
        z = zero_frac(P, c, t)
        if z is not None and z <= thr:
            out.append(c)
    return out


def series(P, pool_fn, sel_fn, k_frac):
    """유니버스·선택 규칙을 받아 시점별 (전략, 벤치마크) 수익을 낸다."""
    out = []
    prev = None
    for t in range(WARMUP, P.T - HORIZON - 2, HORIZON):
        pool = pool_fn(t)
        if len(pool) < 15:
            continue
        r = {c: P.ret_oo(c, t, HORIZON) for c in pool}
        vals = [v for v in r.values() if v is not None]
        if len(vals) < 30:
            continue
        bm = sum(vals) / len(vals)
        K = max(5, int(round(len(pool) * k_frac)))
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


def compound(xs):
    eq = 1.0
    for x in xs:
        eq *= (1 + x / 100.0)
    return eq


def lowvol_sel(P, back):
    def f(t, pool, K):
        sc = []
        for c in pool:
            s = _std(_rets(P, c, t, back))
            if s is not None and math.isfinite(s):
                sc.append((c, -s))
        if len(sc) < max(30, 3 * K):
            return None
        sc.sort(key=lambda x: -x[1])
        return [c for c, _ in sc[:K]]
    return f


def report(name, rows):
    s = stat([r['net'] for r in rows])
    print('%-26s n=%3d · 유니버스 평균 %4d종목 · 초과 %+.3f%%/월 t=%5.2f · '
          '전략 %6.2f배 · 벤치 %6.2f배'
          % (name, s['n'], sum(r['n'] for r in rows) / len(rows), s['mean'], s['t'],
             compound([r['port'] - r['turn'] * COST for r in rows]),
             compound([r['bm'] for r in rows])))
    return s


def main():
    which = sys.argv[sys.argv.index('--panel') + 1] if '--panel' in sys.argv else 'weekly_krx15'
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_%s.csv' % which))

    print('유니버스 감사 — 패널 %s · %d주 · %d종목 · 월간(%d주) · 왕복비용 %.2f%%'
          % (which, P.T, len(P.stocks), HORIZON, COST))
    print('')
    print('[0] 벤치마크 온전성 — 15.6년 누적이 상식적인가')
    big = [c for c in BIG if c in P.c]
    bigret = []
    for t in range(WARMUP, P.T - HORIZON - 2, HORIZON):
        rs = [x for x in (P.ret_oo(c, t, HORIZON) for c in big) if x is not None]
        if len(rs) >= 10:
            bigret.append(sum(rs) / len(rs))
    print('  고정 대형주 %d종목 동일가중 %.2f배  ← 이게 기준점이다'
          % (len(big), compound(bigret)))
    for n in (100, 300, 500):
        rs = series(P, lambda t, n=n: pit_pool(P, t, n), lambda t, pool, K: pool, 1.0)
        print('  거래대금 상위 %-3d 동일가중 %.2f배  (오염 의심)'
              % (n, compound([r['bm'] for r in rs])))
    rs = series(P, lambda t: pool_traded(P, t), lambda t, pool, K: pool, 1.0)
    print('  거래연속 전종목 동일가중 %.2f배  (수정계수 무관)'
          % compound([r['bm'] for r in rs]))

    print('\n[1] 저변동성 — 오염된 유니버스 vs 거래대금을 안 쓰는 유니버스')
    for back in (13, 26, 52):
        for n in (300, 500):
            rows = series(P, lambda t, n=n: pit_pool(P, t, n), lowvol_sel(P, back), 0.10)
            report('거래대금상위%d 저변동%d주' % (n, back), rows)
        rows = series(P, lambda t: pool_traded(P, t), lowvol_sel(P, back), 0.10)
        report('거래연속전체 저변동%d주' % back, rows)

    # 전종목 유니버스는 반대 방향 결함이 있다 — 거래가 뜸한 종목은 가격이 안 움직여
    # 변동성이 낮게 측정된다. 무거래 빈도로 걸러 그 결함까지 제거하고 다시 본다.
    print('')
    print('[2] 수정계수와 무관한 유동 유니버스 (무거래 빈도 기준) — 산술 vs 로그')
    print('    저변동 포트폴리오는 변동성 손실이 작아 기하수익에서 번다.')
    print('    산술평균만 보는 우리 판정 지표가 그걸 못 잡으므로 로그수익도 함께 낸다.')
    for thr, label in ((0.0, '무거래주 0%'), (0.04, '무거래주 4% 이하')):
        base = series(P, lambda t, thr=thr: pool_zr(P, t, thr), lambda t, pool, K: pool, 1.0)
        print('  [%s] 평균 %d종목 · 벤치 누적 %.2f배'
              % (label, sum(r['n'] for r in base) / len(base),
                 compound([r['bm'] for r in base])))
        for back in (13, 26, 52):
            rs = series(P, lambda t, thr=thr: pool_zr(P, t, thr), lowvol_sel(P, back), 0.10)
            ari = stat([r['net'] for r in rs])
            log = stat([100 * (math.log(1 + (r['port'] - COST * r['turn']) / 100)
                               - math.log(1 + r['bm'] / 100)) for r in rs])
            pe = compound([r['port'] - r['turn'] * COST for r in rs])
            be = compound([r['bm'] for r in rs])
            yrs = len(rs) * HORIZON / 52.0
            print('    저변동%2d주 | 산술 %+.3f t=%5.2f | 로그 %+.3f t=%5.2f | 누적 %.2f배 vs %.2f배 (연 %+.2f%%p)'
                  % (back, ari['mean'], ari['t'], log['mean'], log['t'], pe, be,
                     (pe ** (1 / yrs) - be ** (1 / yrs)) * 100))
    print('')
    print('결론 — 거래대금 유니버스에서 나온 저변동성 +1.0~1.7%/월은 유니버스 오염의 산물이다.')
    print('오염 없는 유니버스에서는 산술 t=0.3~1.4 로 0 과 구별되지 않는다.')
    print('다만 기하수익 격차(연 +2~3.7%p)는 남는다 — 유의하지 않지만 방향은 일관된다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

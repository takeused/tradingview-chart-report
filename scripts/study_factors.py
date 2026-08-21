# 횡단면 팩터 등록부 — 전부 시점별(point-in-time) 유니버스에서 한 번에 검정한다
#
# 왜 있나 (2026-08-22): 모멘텀 하나를 검정하는 데 일회성 스크립트를 세 개 썼고, 그 사이
#   '고정 유니버스' 로 돌린 결과를 한 회차 동안 믿었다(+1.78%/월 → 시점별로는 -0.50%).
#   등록부를 만들어 **아이디어를 먼저 등록하고, 전부 같은 시점별 틀에서 한 번에 돌린다.**
#   돌려 보고 좋은 것만 남기면 과최적화다.
#
# 사전등록 원칙
#   - 팩터는 아래 FACTORS 에 **먼저** 넣는다. 방향(높은 점수 = 롱)도 미리 정한다.
#   - 근거는 학계 문헌이나 명시적 가설이어야 한다. "돌려 보니 되더라" 는 근거가 아니다.
#   - 결과는 실패한 것까지 전부 인쇄한다.
#   - **무정보 난수 팩터를 음성 대조군으로 넣는다.** 이게 유의하게 나오면 하네스가 깨진 것이다.
#
# 실행 가정 (backtest.py 와 동일)
#   신호는 t주 종가까지 / 진입 t+1주 시가 / 청산 만기 시가 / 비중첩 표본
#   유니버스는 매 시점 직전 12주 평균 거래대금 상위 N (상장폐지 종목 포함)
#   벤치마크는 **그 시점 유니버스의 동일가중** 수익률
#
# 사용법
#   python scripts/study_factors.py [--panel weekly_krx] [--pit 300] [--cost 0.28]

import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import PANELS, regime_of, round_trip_cost, stat, bh_reject

HORIZON = 4          # 월간 리밸런싱
FRACS = [0.10, 0.20]
PIT_LIQ_WEEKS = 12
WARMUP = 60


# ── 지표 계산 도우미 (t 시점까지의 정보만 쓴다) ─────────────────────────────
def _rets(P, c, t, n):
    cl = P.c[c]
    out = []
    for k in range(max(1, t - n + 1), t + 1):
        a, b = cl[k - 1], cl[k]
        if a and b:
            out.append(b / a - 1)
    return out


def _std(xs):
    if len(xs) < 8:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _mom(P, c, t, back, skip=0):
    cl = P.c[c]
    a, b = t - back, t - skip
    if a < 0 or b < 0 or cl[a] is None or cl[b] is None or cl[a] <= 0:
        return None
    return cl[b] / cl[a] - 1


def _amihud(P, c, t, n=26):
    """Amihud 비유동성 — |수익률| / 거래대금. 높을수록 비유동적."""
    cl, vo = P.c[c], P.v[c]
    vals = []
    for k in range(max(1, t - n + 1), t + 1):
        a, b, v = cl[k - 1], cl[k], vo[k]
        if a and b and v and b * v > 0:
            vals.append(abs(b / a - 1) / (b * v))
    return (sum(vals) / len(vals)) if len(vals) >= n * 0.6 else None


def _hi52(P, c, t, n=52):
    """52주 신고가 근접도 — 현재가 / 52주 최고가 (George & Hwang 2004)."""
    cl, hi = P.c[c], P.h[c]
    if cl[t] is None:
        return None
    hs = [hi[k] for k in range(max(0, t - n + 1), t + 1) if hi[k]]
    if len(hs) < n * 0.6:
        return None
    m = max(hs)
    return cl[t] / m if m else None


def _maxret(P, c, t, n=12):
    """MAX 효과 — 직전 n주 최대 주간수익률 (Bali·Cakici·Whitelaw 2011). 높을수록 이후 수익 낮음."""
    rs = _rets(P, c, t, n)
    return max(rs) if len(rs) >= n * 0.6 else None


def _beta(P, c, t, mkt, n=26):
    """동일가중 시장 대비 베타."""
    cl = P.c[c]
    xs, ys = [], []
    for k in range(max(1, t - n + 1), t + 1):
        a, b = cl[k - 1], cl[k]
        m = mkt.get(k)
        if a and b and m is not None:
            ys.append(b / a - 1)
            xs.append(m)
    if len(xs) < n * 0.6:
        return None
    mx = sum(xs) / len(xs)
    var = sum((x - mx) ** 2 for x in xs)
    if var <= 0:
        return None
    my = sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / var


def _ivol(P, c, t, mkt, n=26):
    """이질변동성 — 시장 회귀 잔차의 표준편차 (Ang et al. 2006)."""
    b = _beta(P, c, t, mkt, n)
    if b is None:
        return None
    cl = P.c[c]
    res = []
    for k in range(max(1, t - n + 1), t + 1):
        a, bb = cl[k - 1], cl[k]
        m = mkt.get(k)
        if a and bb and m is not None:
            res.append((bb / a - 1) - b * m)
    return _std(res)


def _volgrowth(P, c, t, n=12):
    """거래량 추세 — 직전 n주 평균 대비 그 이전 n주 평균."""
    vo = P.v[c]
    a = [vo[k] for k in range(max(0, t - n + 1), t + 1) if vo[k]]
    b = [vo[k] for k in range(max(0, t - 2 * n + 1), t - n + 1) if vo[k]]
    if len(a) < n * 0.6 or len(b) < n * 0.6:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    return (ma / mb) if mb else None


def _rand(P, c, t):
    """음성 대조군 — 종목·시점에만 의존하는 결정적 난수. 정보가 0이다."""
    h = (hash((c, t)) & 0xFFFFFFFF) / 0xFFFFFFFF
    return h


# ── 팩터 등록부 (돌리기 전에 확정) ──────────────────────────────────────────
# 값이 클수록 롱. 문헌상 '낮을수록 좋다' 는 팩터는 부호를 뒤집어 등록한다.
FACTORS = {
    '저변동성(26주)':        ('Ang 2006 저변동성 이상현상', lambda P, c, t, m: (lambda s: None if s is None else -s)(_std(_rets(P, c, t, 26)))),
    '저베타(26주)':          ('Frazzini-Pedersen BAB',      lambda P, c, t, m: (lambda b: None if b is None else -b)(_beta(P, c, t, m, 26))),
    '저이질변동성(26주)':    ('Ang 2006 IVOL',              lambda P, c, t, m: (lambda v: None if v is None else -v)(_ivol(P, c, t, m, 26))),
    '단기반전(4주)':         ('Jegadeesh 1990 단기반전',    lambda P, c, t, m: (lambda r: None if r is None else -r)(_mom(P, c, t, 4))),
    '모멘텀(52주,4주스킵)':  ('Jegadeesh-Titman 1993 대조군', lambda P, c, t, m: _mom(P, c, t, 52, 4)),
    '장기반전(156주)':       ('DeBondt-Thaler 1985',        lambda P, c, t, m: (lambda r: None if r is None else -r)(_mom(P, c, t, 156, 52))),
    '비유동성(Amihud)':      ('Amihud 2002 유동성 프리미엄', lambda P, c, t, m: _amihud(P, c, t, 26)),
    '52주신고가 근접':       ('George-Hwang 2004',          lambda P, c, t, m: _hi52(P, c, t, 52)),
    'MAX 낮음(12주)':        ('Bali 2011 복권선호',         lambda P, c, t, m: (lambda x: None if x is None else -x)(_maxret(P, c, t, 12))),
    '거래량감소(12주)':      ('거래량 증가 = 관심 과열 가설', lambda P, c, t, m: (lambda x: None if x is None else -x)(_volgrowth(P, c, t, 12))),
    '[대조군] 난수':         ('음성 대조군 — 유의하면 하네스 결함', lambda P, c, t, m: _rand(P, c, t)),
}


def market_series(P):
    """주별 동일가중 시장 수익률 — 베타·이질변동성 계산의 기준."""
    out = {}
    for t in range(1, P.T):
        rs = []
        for c in P.stocks:
            a, b = P.c[c][t - 1], P.c[c][t]
            if a and b:
                rs.append(b / a - 1)
        if len(rs) >= 20:
            out[t] = sum(rs) / len(rs)
    return out


def pit_pool(P, t, top_n):
    out = []
    for c in P.stocks:
        cl, vo = P.c[c], P.v[c]
        if cl[t] is None or vo[t] is None:
            continue
        vals = [cl[k] * vo[k] for k in range(max(0, t - PIT_LIQ_WEEKS), t)
                if cl[k] is not None and vo[k] is not None]
        if len(vals) < PIT_LIQ_WEEKS * 0.7:
            continue
        out.append((c, sum(vals) / len(vals)))
    out.sort(key=lambda x: -x[1])
    return [c for c, _ in out[:top_n]]


def main():
    cost = float(sys.argv[sys.argv.index('--cost') + 1]) if '--cost' in sys.argv else round_trip_cost()
    which = sys.argv[sys.argv.index('--panel') + 1] if '--panel' in sys.argv else 'weekly_krx'
    pit = int(sys.argv[sys.argv.index('--pit') + 1]) if '--pit' in sys.argv else 300
    spec = PANELS['weekly']
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_%s.csv' % which))
    mkt = market_series(P)

    ts = list(range(WARMUP, P.T - HORIZON - 2, HORIZON))
    pools, benches, rets = {}, {}, {}
    for t in ts:
        pool = pit_pool(P, t, pit)
        r = {c: P.ret_oo(c, t, HORIZON) for c in pool}
        vals = [v for v in r.values() if v is not None]
        if len(vals) < 30:
            continue
        pools[t] = pool
        rets[t] = r
        benches[t] = sum(vals) / len(vals)

    print('팩터 등록부 검정 — 패널 %s · %d주 · 전체 %d종목 · 시점별 상위 %d · 월간(%d주) · 비용 %.2f%%'
          % (which, P.T, len(P.stocks), pit, HORIZON, cost))
    print('유니버스는 매 시점 직전 %d주 거래대금 상위 %d (상장폐지 포함) · 벤치마크는 그 시점 동일가중'
          % (PIT_LIQ_WEEKS, pit))
    print('리밸런싱 시점 %d회' % len(pools))
    print('')

    rows = []
    for name, (why, fn) in FACTORS.items():
        for fr in FRACS:
            K = max(5, int(round(pit * fr)))
            lo, ls, reg = [], [], {}
            for t in sorted(pools):
                sc = []
                for c in pools[t]:
                    try:
                        v = fn(P, c, t, mkt)
                    except Exception:
                        v = None
                    if v is not None and math.isfinite(v):
                        sc.append((c, v))
                if len(sc) < max(30, 3 * K):
                    continue
                sc.sort(key=lambda x: -x[1])
                top = [rets[t][c] for c, _ in sc[:K] if rets[t].get(c) is not None]
                bot = [rets[t][c] for c, _ in sc[-K:] if rets[t].get(c) is not None]
                if len(top) < K * 0.8 or len(bot) < K * 0.8:
                    continue
                mt, mb = sum(top) / len(top), sum(bot) / len(bot)
                e = mt - benches[t]
                lo.append(e)
                ls.append(mt - mb)
                g = regime_of(P, t, spec['regime_back'])
                if g:
                    reg.setdefault(g, []).append(e)
            s_lo, s_ls = stat(lo), stat(ls)
            if not s_lo:
                continue
            rows.append({'name': name, 'why': why, 'frac': fr, 'K': K,
                         'lo': s_lo, 'ls': s_ls,
                         'lo_net': round(s_lo['mean'] - cost, 3),
                         'ls_net': round(s_ls['mean'] - 2 * cost, 3) if s_ls else None,
                         'reg': {g: round(stat(v)['mean'] - cost, 2)
                                 for g, v in reg.items() if stat(v)}})

    rej = bh_reject([r['lo']['p'] for r in rows])
    for r, ok in zip(rows, rej):
        r['bh'] = bool(ok)
    rows.sort(key=lambda r: -r['lo_net'])

    print('%-22s %5s %5s %10s %6s %6s %3s  %s'
          % ('팩터', '분위%', 'n', '롱온리순%', 't', 'p', 'BH', '국면별(강세/횡보/약세)'))
    print('-' * 118)
    for r in rows:
        g = r['reg']
        print('%-22s %5.0f %5d %10.3f %6.2f %6.3f %3s  %s'
              % (r['name'], r['frac'] * 100, r['lo']['n'], r['lo_net'], r['lo']['t'],
                 r['lo']['p'], 'O' if r['bh'] else '-',
                 ' / '.join('%+.2f' % g[k] for k in ('강세', '횡보', '약세') if k in g)))
    print('-' * 118)

    ctrl = [r for r in rows if r['name'].startswith('[대조군]')]
    if ctrl:
        bad = [r for r in ctrl if r['bh']]
        print('음성 대조군(난수) — 비용차감 %s · BH 통과 %d건 %s'
              % (' / '.join('%.3f' % r['lo_net'] for r in ctrl), len(bad),
                 '← 하네스 결함 의심!' if bad else '(정상: 통과 0건이어야 한다)'))

    win = [r for r in rows if r['bh'] and r['lo_net'] > 0 and not r['name'].startswith('[대조군]')]
    allreg = [r for r in win if len(r['reg']) >= 3 and all(v > 0 for v in r['reg'].values())]
    print('BH 통과 + 비용차감 양수: %d건 / %d조합 · 그중 세 국면 모두 양수: %d건'
          % (len(win), len(rows), len(allreg)))
    for r in win:
        print('  → %s (분위 %.0f%%) %+.3f%%/월 · 근거: %s'
              % (r['name'], r['frac'] * 100, r['lo_net'], r['why']))
    if not win:
        print('  시점별 유니버스에서 비용을 넘는 팩터가 없다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

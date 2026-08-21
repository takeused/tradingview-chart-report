# 저변동성 계열 강건성 — 회전율을 실제로 재고, 유니버스·창·비용을 흔들어 본다
#
# 왜 있나 (2026-08-22): 팩터 등록부 검정에서 시점별 유니버스를 통과한 것이
#   저변동성 / 저이질변동성 / MAX낮음 셋이었다. 그런데 이 셋은 **같은 현상의 세 얼굴**이라
#   독립 발견 3건이 아니다. 그래서 계열 전체를 한 번에 흔들어 본다.
#
# 특히 회전율을 잰다 — backtest 의 비용 모델은 **매달 전량 교체**를 가정하는데,
#   변동성은 지속성이 높아 저변동성 포트폴리오는 종목이 상당수 유지된다.
#   회전율을 재지 않으면 비용을 과대 계상해서 실제보다 나쁘게 본다.
#
# 사용법
#   python scripts/study_lowvol.py [--panel weekly_krx]

import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import PANELS, regime_of, round_trip_cost, stat
from study_factors import (HORIZON, PIT_LIQ_WEEKS, WARMUP, market_series, pit_pool,
                           _rets, _std, _ivol, _maxret)

# ── 사전 지정 격자 ──────────────────────────────────────────────────────────
MEASURES = {
    '수익률표준편차': lambda P, c, t, m, n: (lambda s: None if s is None else -s)(_std(_rets(P, c, t, n))),
    '이질변동성':     lambda P, c, t, m, n: (lambda v: None if v is None else -v)(_ivol(P, c, t, m, n)),
    'MAX주간수익률':  lambda P, c, t, m, n: (lambda x: None if x is None else -x)(_maxret(P, c, t, min(n, 26))),
}
LOOKBACKS = [13, 26, 52]
UNIVERSES = [150, 300, 500]
FRAC = 0.10
COSTS = [0.15, 0.28, 0.50]


def run(P, mkt, fn, back, pit, frac, base_cost):
    K = max(5, int(round(pit * frac)))
    ts = range(WARMUP, P.T - HORIZON - 2, HORIZON)
    lo, reg, turn = [], {}, []
    prev = None
    for t in ts:
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
        if prev is not None:
            turn.append(1 - len(set(sel) & prev) / float(K))
        prev = set(sel)
        e = sum(top) / len(top) - bm
        lo.append(e)
        g = regime_of(P, t, PANELS['weekly']['regime_back'])
        if g:
            reg.setdefault(g, []).append(e)
    s = stat(lo)
    if not s:
        return None
    tr = (sum(turn) / len(turn)) if turn else 1.0
    return {'n': s['n'], 'gross': s['mean'], 't': s['t'], 'p': s['p'], 'turnover': tr,
            'net_full': round(s['mean'] - base_cost, 3),
            'net_turn': round(s['mean'] - base_cost * tr, 3),
            'reg': {g: round(stat(v)['mean'] - base_cost * tr, 2)
                    for g, v in reg.items() if stat(v)}}


def main():
    which = sys.argv[sys.argv.index('--panel') + 1] if '--panel' in sys.argv else 'weekly_krx'
    base = round_trip_cost()
    P = panel_io.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                   'data', 'panel_%s.csv' % which))
    mkt = market_series(P)

    print('저변동성 계열 강건성 — 패널 %s · %d주 · 전체 %d종목 · 월간(%d주) · 롱온리 상위 %.0f%%'
          % (which, P.T, len(P.stocks), HORIZON, FRAC * 100))
    print('격자: 측정 3종 x 창 %s주 x 유니버스 %s — 사전 지정' % (LOOKBACKS, UNIVERSES))
    print('회전율은 실측한다(직전 보유와 겹치지 않는 비율). 비용은 회전율만큼만 물린다.')
    print('')
    print('%-14s %4s %5s %5s %9s %6s %7s %10s %10s  %s'
          % ('측정', '창', '유니', 'n', '총초과%', 't', '회전율', '전량비용후', '회전율비용후', '국면별'))
    print('-' * 122)
    rows = []
    for mname, fn in MEASURES.items():
        for back in LOOKBACKS:
            for pit in UNIVERSES:
                r = run(P, mkt, fn, back, pit, FRAC, base)
                if not r:
                    continue
                r.update(measure=mname, back=back, pit=pit)
                rows.append(r)
                g = r['reg']
                print('%-14s %4d %5d %5d %9.3f %6.2f %6.0f%% %10.3f %10.3f  %s'
                      % (mname, back, pit, r['n'], r['gross'], r['t'], r['turnover'] * 100,
                         r['net_full'], r['net_turn'],
                         ' / '.join('%+.2f' % g[k] for k in ('강세', '횡보', '약세') if k in g)))
    print('-' * 122)

    pos_full = sum(1 for r in rows if r['net_full'] > 0)
    pos_turn = sum(1 for r in rows if r['net_turn'] > 0)
    allreg = sum(1 for r in rows if r['net_turn'] > 0 and len(r['reg']) >= 3
                 and all(v > 0 for v in r['reg'].values()))
    print('격자 %d칸 — 전량교체 비용 기준 양수 %d칸 · 실측 회전율 기준 양수 %d칸 · 세 국면 모두 양수 %d칸'
          % (len(rows), pos_full, pos_turn, allreg))
    print('평균 회전율 %.0f%% — 전량교체 가정은 비용을 %.1f배 과대 계상한다'
          % (sum(r['turnover'] for r in rows) / len(rows) * 100,
             1.0 / (sum(r['turnover'] for r in rows) / len(rows))))

    print('\n비용 가정 민감도 (측정=수익률표준편차 · 창 26주 · 유니버스 300 · 실측 회전율 적용)')
    ref = next((r for r in rows if r['measure'] == '수익률표준편차'
                and r['back'] == 26 and r['pit'] == 300), None)
    if ref:
        for c in COSTS:
            print('  왕복 %.2f%% → %+.3f%%/월' % (c, round(ref['gross'] - c * ref['turnover'], 3)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

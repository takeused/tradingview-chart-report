# 후보 매매 규칙을 비용·벤치마크 차감 후 기대손익으로 검정한다
#
# 왜 있나 (2026-08-21 신설): 이 프로젝트의 제1원칙은 "주식 투자로 돈을 버는 것"인데,
#   v6 까지의 채점 목표는 '도달 확률이 잘 보정됐나'(Brier)였다. **Brier 를 1% 개선해도 0원이다.**
#   잘 보정된 도달확률은 무드리프트 랜덤워크에서 정의상 기대값이 0이고, direction_prob 을
#   0.5 로 못 박아 둔 이상 파이프라인에는 매매 규칙이 아예 없었다.
#   이 스크립트는 목적함수를 '원화 기대손익'으로 옮긴다.
#
# 첫 실행에서 배운 것 — 벤치마크를 빼지 않으면 전부 착시다.
#   TS 모멘텀(전일 상승) 5일 보유의 원시 수익률은 +1.26%(t=6.16)로 훌륭해 보였지만,
#   같은 구간 전종목 동일가중 보유가 +0.86%(t=5.77)였다. 표본 300일 동안 시장이 79.1%
#   올랐기 때문이다. 벤치마크를 차감하니 초과수익 -0.02%(t=-0.09)로 사라졌다.
#   **롱온리 전략은 반드시 동일가중 보유 대비 초과로 본다.**
#
# 실행 가정 (룩어헤드 차단)
#   - 신호는 t일 종가까지의 정보만 쓴다
#   - 진입은 t+1일 **시가**, 청산은 t+1+h일 **시가**
#   - 표본은 겹치지 않게 h일 간격으로만 뽑는다(중첩 창은 t값을 부풀린다)
#
# 두 번째로 배운 것 — 단일 국면 표본은 결론이 못 된다 (2026-08-22)
#   일봉 패널은 TradingView 가 **300봉으로 캡**해서 317영업일(약 1.3년)밖에 안 되고,
#   그 구간이 시장 +79% 의 단일 강세장이었다. 주봉은 300개까지 나오므로
#   2020-10 ~ 2026-08 (약 5.8년, 2022 약세장 포함)을 덮는다. 저회전 전략은 주봉으로 본다.
#   규칙은 국면별(강세/횡보/약세)로도 쪼개서 본다 — **강세장에서만 사는 것은 팩터가 아니다.**
#
# 사용법
#   python scripts/backtest.py                    # 주봉 패널(기본)
#   python scripts/backtest.py --panel daily      # 일봉 패널
#   python scripts/backtest.py --cost 0.40        # 왕복 비용 가정 변경(%)
#   python scripts/backtest.py --json out.json

import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io

# ── 패널 규격 ────────────────────────────────────────────────────────────────
# 봉 단위가 달라도 같은 규칙을 돌린다. 되돌아보기 창은 '봉 수' 로 표현한다.
PANELS = {
    'daily':  {'file': 'panel_daily.csv',  'unit': '일', 'horizons': [1, 5, 20],
               'mom_back': 60, 'mom_skip': 5, 'rev_back': 5, 'warmup': 70, 'regime_back': 60},
    'weekly': {'file': 'panel_weekly.csv', 'unit': '주', 'horizons': [1, 4, 13],
               'mom_back': 52, 'mom_skip': 4, 'rev_back': 4, 'warmup': 60, 'regime_back': 13},
}
REGIME_BAND = 5.0   # 직전 창의 지수 수익률이 +-5% 밖이면 강세/약세, 안이면 횡보


# ── 비용 모델 ────────────────────────────────────────────────────────────────
# 기본값은 보수적 추정이며 **실제 요율은 반드시 본인 계좌 기준으로 확인**해야 한다.
#   매수: 위탁수수료 + 슬리피지
#   매도: 위탁수수료 + 슬리피지 + 거래세(코스피/코스닥)
COST = {
    'fee_pct': 0.015,        # 편도 위탁수수료
    'slip_pct': 0.050,       # 편도 슬리피지(유동성 좋은 종목 기준, 소형주는 더 크다)
    'tax_sell_pct': 0.150,   # 매도 시 거래세·농특세 합계
}


def round_trip_cost():
    return 2 * (COST['fee_pct'] + COST['slip_pct']) + COST['tax_sell_pct']


# ── 통계 ────────────────────────────────────────────────────────────────────
def stat(xs):
    n = len(xs)
    if n < 8:
        return None
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    t = m / (sd / math.sqrt(n)) if sd > 0 else 0.0
    p = math.erfc(abs(t) / math.sqrt(2))     # 양측, 정규근사(n>=30 에서 충분)
    return {'n': n, 'mean': round(m, 4), 't': round(t, 2), 'p': round(p, 4),
            'win': round(sum(1 for x in xs if x > 0) / n * 100, 1)}


def bh_reject(pvals, alpha=0.05):
    """Benjamini-Hochberg. 조합을 30개 보면 t=2 는 우연히 1.5개 나온다."""
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    out = [False] * m
    kmax = -1
    for rank, i in enumerate(idx, start=1):
        if pvals[i] <= alpha * rank / m:
            kmax = rank
    for rank, i in enumerate(idx, start=1):
        if rank <= kmax:
            out[i] = True
    return out


# ── 규칙 등록부 (사전등록) ───────────────────────────────────────────────────
# 새 아이디어는 **여기에 먼저 등록하고** 돌린다. 돌려 보고 좋은 것만 남기면 과최적화다.
def _ret1(P, c, t):
    cl = P.c[c]
    if t < 1 or cl[t] is None or cl[t - 1] is None:
        return None
    return (cl[t] / cl[t - 1] - 1) * 100


def _atrpct(P, c, t, n=14):
    h, l, cl = P.h[c], P.l[c], P.c[c]
    if t < n + 1 or cl[t] is None:
        return None
    trs = []
    for k in range(t - n + 1, t + 1):
        if None in (h[k], l[k], cl[k - 1]):
            return None
        trs.append(max(h[k] - l[k], abs(h[k] - cl[k - 1]), abs(l[k] - cl[k - 1])))
    return sum(trs) / n / cl[t] * 100


def _volx(P, c, t):
    v = P.v[c]
    if t < 21:
        return None
    hist = [v[k] for k in range(t - 20, t) if v[k]]
    if len(hist) < 15 or not v[t]:
        return None
    return v[t] / (sum(hist) / len(hist))


def _mom(P, c, t, back, skip=0):
    cl = P.c[c]
    a, b = t - back, t - skip
    if a < 0 or cl[a] is None or cl[b] is None or cl[a] <= 0:
        return None
    return cl[b] / cl[a] - 1


def regime_of(P, t, back):
    """직전 back 봉의 KOSPI 수익률로 국면을 라벨링한다.

    강세장에서만 사는 규칙은 팩터가 아니라 베타다. 국면을 안 쪼개면 그걸 구별할 수 없다.
    """
    cl = P.c.get('KOSPI')
    if cl is None or t - back < 0 or cl[t] is None or cl[t - back] is None:
        return None
    r = (cl[t] / cl[t - back] - 1) * 100
    return '강세' if r > REGIME_BAND else ('약세' if r < -REGIME_BAND else '횡보')


# 시계열 규칙: (code, t) -> bool
TS_RULES = {
    'TS 모멘텀(전일 상승)':     lambda P, c, t: (_ret1(P, c, t) or 0) > 0 and _ret1(P, c, t) is not None,
    'TS 반전(전일 하락)':       lambda P, c, t: _ret1(P, c, t) is not None and _ret1(P, c, t) < 0,
    '급락 반전(-1σ 이하)':      lambda P, c, t: (lambda r, a: r is not None and a is not None and r < -a)(_ret1(P, c, t), _atrpct(P, c, t)),
    '급등 추종(+1σ 이상)':      lambda P, c, t: (lambda r, a: r is not None and a is not None and r > a)(_ret1(P, c, t), _atrpct(P, c, t)),
    '거래량급증(1.5배)+상승':   lambda P, c, t: (lambda r, v: r is not None and v is not None and v > 1.5 and r > 0)(_ret1(P, c, t), _volx(P, c, t)),
    '거래량급증(1.5배)+하락':   lambda P, c, t: (lambda r, v: r is not None and v is not None and v > 1.5 and r < 0)(_ret1(P, c, t), _volx(P, c, t)),
}

# 횡단면 규칙: (code, t) -> 점수(높을수록 롱). 롱숏 동일가중.
def xs_rules(spec):
    """패널 스펙에 맞춘 횡단면 규칙. 창 길이가 봉 단위에 따라 달라진다."""
    mb, ms, rb, u = spec['mom_back'], spec['mom_skip'], spec['rev_back'], spec['unit']
    return {
        'XS 모멘텀 %d%s(%d%s 스킵)' % (mb, u, ms, u):
            lambda P, c, t: _mom(P, c, t, mb, ms),
        'XS 반전 %d%s' % (rb, u):
            lambda P, c, t: None if _mom(P, c, t, rb) is None else -_mom(P, c, t, rb),
        'XS 저변동성':
            lambda P, c, t: None if _atrpct(P, c, t) is None else -_atrpct(P, c, t),
        'XS 거래량배수':
            lambda P, c, t: _volx(P, c, t),
    }


XS_K = 10          # 롱/숏 각 분위 종목 수


def run(P, spec, cost=None, split=0.6):
    cost = round_trip_cost() if cost is None else cost
    rows = []
    cut = int(P.T * split)
    HORIZONS = spec['horizons']
    WARMUP = spec['warmup']
    RB = spec['regime_back']

    bench_cache = {}

    def bench(t, h):
        key = (t, h)
        if key not in bench_cache:
            rs = [P.ret_oo(c, t, h) for c in P.stocks]
            rs = [r for r in rs if r is not None]
            bench_cache[key] = (sum(rs) / len(rs)) if len(rs) >= 20 else None
        return bench_cache[key]

    def pack(name, kind, h, legs, ex, ex_a, ex_b, by_reg):
        st = stat(ex)
        if st is None:
            return None
        row = {'rule': name, 'kind': kind, 'h': h, 'legs': legs, 'excess': st,
               'net_mean': round(st['mean'] - legs * cost, 4),
               'front': stat(ex_a), 'back': stat(ex_b), 'regime': {}}
        for g, xs in by_reg.items():
            sg = stat(xs)
            if sg:
                row['regime'][g] = {'n': sg['n'], 'mean': sg['mean'], 't': sg['t'],
                                    'net': round(sg['mean'] - legs * cost, 4)}
        return row

    for name, fn in TS_RULES.items():
        for h in HORIZONS:
            ex, ex_a, ex_b = [], [], []
            by_reg = {}
            for t in range(WARMUP, P.T - h - 2, h):
                bm = bench(t, h)
                if bm is None:
                    continue
                g = regime_of(P, t, RB)
                for c in P.stocks:
                    try:
                        hit = fn(P, c, t)
                    except Exception:
                        hit = False
                    if not hit:
                        continue
                    r = P.ret_oo(c, t, h)
                    if r is None:
                        continue
                    e = r - bm
                    ex.append(e)
                    (ex_a if t < cut else ex_b).append(e)
                    if g:
                        by_reg.setdefault(g, []).append(e)
            row = pack(name, 'TS', h, 1, ex, ex_a, ex_b, by_reg)
            if row:
                rows.append(row)

    for name, fn in xs_rules(spec).items():
        for h in HORIZONS:
            ls, ls_a, ls_b = [], [], []
            by_reg = {}
            for t in range(WARMUP, P.T - h - 2, h):
                sc = []
                for c in P.stocks:
                    try:
                        s_ = fn(P, c, t)
                    except Exception:
                        s_ = None
                    if s_ is not None and math.isfinite(s_):
                        sc.append((c, s_))
                if len(sc) < 30:
                    continue
                sc.sort(key=lambda x: -x[1])
                top = [P.ret_oo(c, t, h) for c, _ in sc[:XS_K]]
                bot = [P.ret_oo(c, t, h) for c, _ in sc[-XS_K:]]
                top = [r for r in top if r is not None]
                bot = [r for r in bot if r is not None]
                if len(top) < XS_K * 0.8 or len(bot) < XS_K * 0.8:
                    continue
                v = sum(top) / len(top) - sum(bot) / len(bot)
                ls.append(v)
                (ls_a if t < cut else ls_b).append(v)
                g = regime_of(P, t, RB)
                if g:
                    by_reg.setdefault(g, []).append(v)
            row = pack(name, 'XS(롱숏)', h, 2, ls, ls_a, ls_b, by_reg)
            if row:
                rows.append(row)

    rej = bh_reject([r['excess']['p'] for r in rows])
    for r, ok in zip(rows, rej):
        r['bh_significant'] = bool(ok)
    return rows, cost


def market_summary(P):
    """표본 구간이 어떤 국면이었는지 — 이걸 안 보면 결론을 일반화한다."""
    first, last, n = 0.0, 0.0, 0
    for c in P.stocks:
        cl = P.c[c]
        a = next((x for x in cl if x), None)
        b = next((x for x in reversed(cl) if x), None)
        if a and b:
            first += 1.0
            last += b / a
            n += 1
    tot = (last / n - 1) * 100 if n else 0.0
    return {'days': P.T, 'stocks': n, 'cum_pct': round(tot, 1),
            'daily_pct': round(((1 + tot / 100) ** (1.0 / P.T) - 1) * 100, 3)}


def regime_table(P, spec):
    """국면별 시장 흐름 — 표본이 어떤 국면들로 이뤄졌는지 먼저 본다."""
    RB, out = spec['regime_back'], {}
    for t in range(spec['warmup'], P.T - 1):
        g = regime_of(P, t, RB)
        if not g:
            continue
        rs = [P.ret_oo(c, t, 1) for c in P.stocks]
        rs = [r for r in rs if r is not None]
        if rs:
            out.setdefault(g, []).append(sum(rs) / len(rs))
    return {g: {'bars': len(v), 'mean_pct': round(sum(v) / len(v), 3)} for g, v in out.items()}


def main():
    cost = None
    if '--cost' in sys.argv:
        cost = float(sys.argv[sys.argv.index('--cost') + 1])
    which = 'weekly'
    if '--panel' in sys.argv:
        which = sys.argv[sys.argv.index('--panel') + 1]
    spec = PANELS[which]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', spec['file'])
    P = panel_io.load(path)
    ms = market_summary(P)
    rows, cost = run(P, spec, cost=cost)
    rows.sort(key=lambda r: -r['net_mean'])
    reg = regime_table(P, spec)

    print('패널 %s · %d%s · 종목 %d · 구간 시장 %+.1f%% · 왕복비용 가정 %.2f%%'
          % (which, ms['days'], spec['unit'], ms['stocks'], ms['cum_pct'], cost))
    print('실행 가정 — 신호 t봉 종가, 진입 t+1 시가, 청산 t+1+h 시가, 비중첩 표본')
    print('국면 구성 — ' + ' · '.join(
        '%s %d%s(평균 %+.3f%%)' % (g, v['bars'], spec['unit'], v['mean_pct'])
        for g, v in sorted(reg.items())))
    print('')
    hdr = '%-24s %-8s %3s %6s %9s %7s %9s %5s  %s'
    print(hdr % ('규칙', '유형', 'h', 'n', '초과%', 't', '비용차감%', 'BH', '국면별 비용차감%(n)'))
    print('-' * 124)
    for r in rows:
        rg = ' · '.join('%s %+.2f(%d)' % (g, v['net'], v['n'])
                        for g, v in sorted(r['regime'].items()))
        print(hdr % (r['rule'], r['kind'], r['h'], r['excess']['n'], '%.3f' % r['excess']['mean'],
                     '%.2f' % r['excess']['t'], '%.3f' % r['net_mean'],
                     'O' if r['bh_significant'] else '-', rg))
    print('-' * 124)

    win = [r for r in rows if r['bh_significant'] and r['net_mean'] > 0]
    allreg = [r for r in rows
              if r['net_mean'] > 0 and r['regime'] and len(r['regime']) >= 2
              and all(v['net'] > 0 for v in r['regime'].values())]
    print('BH 보정 통과 + 비용 차감 후 양수: %d건 / %d조합' % (len(win), len(rows)))
    print('국면 2개 이상에서 모두 비용 차감 후 양수: %d건' % len(allreg))
    for r in allreg:
        print('  → %s (h=%d) 전체 %+.3f%% · %s' % (
            r['rule'], r['h'], r['net_mean'],
            ' · '.join('%s %+.2f' % (g, v['net']) for g, v in sorted(r['regime'].items()))))
    if not win and not allreg:
        print('  이 표본에서 비용·벤치마크·국면을 함께 넘는 규칙은 없다.')

    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        json.dump({'panel': which, 'market': ms, 'regimes': reg, 'cost_pct': cost, 'rows': rows},
                  open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('기록 —', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

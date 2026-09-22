# 순위표 「위쪽 여유」 항목이 돈이 되는지 검정한다 (사전등록 · 2026-09-21)
#
# 왜 있나: 순위 합산의 24점을 「위쪽 여유」(가까운 쪽 위 레벨까지의 거리 σ)가 쥐고 있는데,
#   이 항목은 **검정된 적이 없다.** 리포트 푸터에도 "합리적 가정"이라고만 적혀 있다.
#   2026-08-22 에 같은 이유로 「아래 지지 근접 15점」을 뺐고, 그 하나가 1위를 뒤집고 있었다.
#   2026-09-21 회차에서 배럴이 이 항목 하나로 3위에 올라와 다시 문제가 됐다.
#
# 가설 (사전에 못 박는다)
#   H1  위쪽 여유가 큰 종목은 다음 h세션 동안 **로스터 동일가중 보유보다 더 오른다.**
#   H0  차이가 없다. (기각 못 하면 24점은 근거 없는 가중치이므로 뺀다)
#
# 실행 가정 — backtest.py 와 동일하게 룩어헤드를 막는다
#   신호는 회차 t 종가까지의 정보뿐(레벨·ATR 이 그렇게 만들어졌다)
#   진입은 t+1 **시가**(= entry.next_session), 청산은 t+1+h **시가**
#   벤치마크는 그 회차 로스터 전체 동일가중 **보유**(비용 0) — 롱온리는 보유 대비로만 본다
#   전략에만 왕복 비용을 물린다(보수적)
#
# 표본의 한계 — 결과보다 먼저 읽어야 한다
#   ① 신호가 있는 회차가 25개(2026-08-14~2026-09-21)뿐이고, 만기 수익률까지 있는 것은
#      23개다(마지막 두 회차는 아직 청산일이 안 왔다). 종목도 로스터(20~36) 안이다. 60종목 패널 검정이
#      불가능하다 — room_up 은 차트 레벨에서 나오므로 패널로 계산할 수 없다.
#   ② 레벨 선정 규격이 구간 안에서 세 번 바뀌었다(9/4 라인 전 종목 수집 · 9/9 존 0.3σ 하한 ·
#      9/10 존·라인 분리). 그래서 **전체 창과 규격 고정 후 창을 따로** 낸다.
#   ③ h>1 이면 회차가 겹친다. 겹치는 표본은 t 를 부풀리므로 **h 간격 비중첩 표본**으로만
#      통계를 낸다(오프셋을 바꿔 가며 전부 보고한다).
#   이 표본으로는 "있다"를 증명할 수 없다. 증명할 수 있는 것은 **"없다고 볼 근거"** 쪽이다.
#
# 결과 (2026-09-21 최초 실행 · 회차 23 · 왕복 비용 0.280%)
#   h=1 상위 3분위 초과 **+0.152%/회차 · t 0.57 · p 0.568 · 승률 47.8%** — 기각 못 함.
#   하위 3분위 -0.328%(t -1.54)로 부호는 대칭이지만 두 다리 다 유의하지 않다.
#   h=3 · h=5 와 「규격 고정 후」 창은 **비중첩 표본이 8개 미만이라 검정 자체가 불가**했다.
#   음성 대조군(무작위 신호 200회)에서 관측값 이상이 5.0% — t검정과 어긋나는데,
#   대조군의 귀무는 "무작위 선택보다 나은가"이고 t검정의 귀무는 "보유보다 나은가"다.
#   **판정 기준은 제1원칙대로 후자**이므로 결론은 "통과 못 함"이다.
#
# 표본이 부족하다는 것을 숫자로 — 회차별 초과수익 표준편차가 **1.283%**다.
#   지금 n=23 으로 검출 가능한 최소 효과는 **0.535%/회차**이고, 관측된 0.152%를
#   t=2 로 확인하려면 **283회차(약 1.1년)** 가 필요하다.
#   즉 이 항목은 "효과가 없다"가 아니라 **"있는지 없는지 잴 수 없다"** 상태다.
#   그런데 순위 합산에서는 **24점**을 쥐고 있다 — 잴 수 없는 주장에 24점을 준 것이다.
#
# 진단(증명 아님) — room_up 백분위는 다른 항목과 거의 직교한다(730관측).
#   당일 등락 -0.054 · 종가위치 -0.050 · 배지 -0.029 · 거래량 -0.035.
#   2026-08-22 에 「아래 지지 근접」을 뺀 이유(단기반전의 위장)는 **여기서는 해당 없다.**
#
# 광역 결과 (2026-09-22 · 유니버스 시총 상위 300 · 유효 10회차 · 수집 계속 중)
#   h=1 상위 3분위 초과 **-0.356%/회차 · p 0.017** — 부호가 좁은 검정(+0.152%)과 반대다.
#   하위 3분위 -0.119%(스프레드 -0.238%p)로 대칭성도 반대 방향이다.
#
#   **그러나 이 p값을 "음의 신호를 찾았다"로 읽으면 안 된다.** stat() 의 귀무는 '평균 0'인데
#   전략만 왕복 비용 0.280% 를 물기 때문에, **아무 신호가 없어도 -0.28% 가 나온다.**
#   실제로 음성 대조군(무작위 신호 200회)의 중앙이 -0.283% 였다.
#   신호가 기여한 몫은 -0.356 - (-0.283) = **-0.073%p 뿐**이고, 무작위 200회 중
#   **82%가 관측값보다 나았다** — 무작위와 구별되지 않는다.
#
#   즉 광역에서의 결론은 "반대 신호"가 아니라 **"우위가 사라졌다"** 이다.
#   좁은 검정에서는 대조군 상위 5% 였던 것이 유니버스를 30 → 297 로 넓히자 82% 가 됐다.
#   24종목 모멘텀(t=2.07)이 60종목에서 사라진(t=0.16) 것과 같은 모양이다.
#
#   **미완이다** — 유효 10회차이고 전부 8월 중순~9월 초의 한 국면이다. 남은 14회차를
#   받아 24회차로 다시 낸다. h=3·h=5 와 「규격 고정 후」 창은 아직 표본 8 미만이다.
#
# 사용법
#   python scripts/study_room_up.py --ohlc <ohlc.json 경로> [--json out.json]
#   python scripts/study_room_up.py --ohlc data/room_up_wide/ohlc300.json \n#          --wide data/room_up_wide          # 광역 모드

import argparse, json, math, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import bh_reject, round_trip_cost, stat
import build_items as bi          # 레벨 선정 규칙은 적용기와 **같은 코드**를 쓴다

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

# ── 사전 지정 격자 (돌려 보고 고르지 않는다) ────────────────────────────────
HORIZONS = [1, 3, 5]
FRAC = 1.0 / 3.0                 # 상위/하위 3분위
SPLIT_FIXED_FROM = '2026-09-10'  # 존·라인 분리 적용일 — 규격이 고정된 구간
N_CONTROL = 200                  # 음성 대조군(무작위 신호) 반복 수
STALE_MAX = 0.10                 # 낡은 봉이 이 비율을 넘으면 그 회차는 버린다
SEED = 20260921


def ymd(t):
    import datetime
    z = datetime.datetime.utcfromtimestamp(t)
    return '%04d-%02d-%02d' % (z.year, z.month, z.day)


def load_bars(path):
    """{code: {date: (open, close)}} 와 {code: [date...]} 를 만든다."""
    raw = json.load(open(path, encoding='utf-8'))
    bars, order = {}, {}
    for code, rows in raw['data'].items():
        m, ds = {}, []
        for r in rows:
            d = ymd(r[0])
            m[d] = (r[1], r[4])      # open, close
            ds.append(d)
        bars[code], order[code] = m, ds
    return bars, order


def sessions(order):
    """전 종목 공통 거래일 목록 — 지수 계열에서 가져온다(가장 결측이 적다)."""
    best = max(order.values(), key=len)
    return best


def fwd_open_ret(bars, code, cal, entry_date, h):
    """진입일 시가 → h세션 뒤 시가. 둘 중 하나라도 없으면 None."""
    if entry_date not in cal:
        return None
    i = cal.index(entry_date)
    if i + h >= len(cal):
        return None
    d0, d1 = cal[i], cal[i + h]
    b = bars.get(code)
    if not b or d0 not in b or d1 not in b:
        return None
    o0, o1 = b[d0][0], b[d1][0]
    if not o0 or not o1:
        return None
    return (o1 - o0) / o0 * 100.0


def pct_rank(vals):
    """0~100 백분위. 순위표(report_enrich)와 같은 정의."""
    n = len(vals)
    if n < 2:
        return {v: 50.0 for v in vals}
    return {v: 100.0 * sum(1 for y in vals if y < v) / (n - 1) for v in set(vals)}


def rounds_with_signal(pred, signal):
    """[(asof, entry, {code: 점수}, [code...])] — 점수가 있는 회차만."""
    out = []
    for e in pred['entries']:
        sc = {}
        for it in e['items']:
            v = signal(it)
            if v is not None:
                sc[it['code']] = v
        if len(sc) >= 9:                      # 3분위가 3종목 미만이면 의미 없다
            out.append((e['asof'], e['next_session'], sc,
                        [it['code'] for it in e['items']]))
    return out


def rounds_wide(dirpath, pred):
    """광역 수집(room_<날짜>.json)에서 회차를 만든다 — 유니버스 300, 규칙은 오늘 규격 하나.

    좁은 검정과 다른 점이 둘이다.
      ① 유니버스가 로스터(20~36)가 아니라 시점별 시총 상위 300이다. 로스터의 선택편향이
         빠지고, 무엇보다 회차별 표준오차가 줄어 **검출력이 올라간다.**
      ② 레벨 선정 규칙을 **전 구간에 오늘 규격으로 통일**해서 다시 계산한다. 기록이 아니라
         재계산이므로 9/4·9/9·9/10 의 규격 단절이 여기서는 생기지 않는다.
         (대신 "그때 리포트가 인쇄한 값"과는 다를 수 있다 — 같은 것을 재는 것이 아니다.)
    """
    nxt = {e['asof']: e['next_session'] for e in pred['entries']}
    out = []
    for fn in sorted(os.listdir(dirpath)):
        if not fn.startswith('room_') or not fn.endswith('.json'):
            continue
        asof = fn[5:-5]
        if asof not in nxt:
            continue
        g = json.load(open(os.path.join(dirpath, fn), encoding='utf-8'))
        # 회차 도중 리플레이 시점이 되돌아가는 일이 있다(2026-08-27 회차에서 인덱스 198~299,
        # 101종목이 하루 전 봉이었다). 낡은 것만 빼면 **남는 유니버스가 시총 상위쪽으로
        # 치우쳐** 회차 간 비교가 깨지므로, 비율이 높으면 회차를 통째로 버린다.
        dated = [v for v in g.values() if v.get('t')]
        stale = sum(1 for v in dated if ymd(v['t']) != asof)
        if dated and stale / float(len(dated)) > STALE_MAX:
            print('  [건너뜀] %s — 낡은 봉 %d/%d (%.0f%%) · 리플레이가 회차 도중 되돌아갔다'
                  % (asof, stale, len(dated), 100.0 * stale / len(dated)))
            continue
        sc, roster = {}, []
        for code, v in g.items():
            if v.get('err') or not v.get('a'):
                continue
            if v.get('sym', '').split(':')[-1] != code:   # 심볼 대조는 버리는 검사다
                continue
            # 마지막 봉이 그 회차여야 한다 — 거래정지 종목은 옛 봉이 남아
            # 종가·ATR 이 그 시점 값이 아니다(2026-08-14 회차에 1종목 실제로 나왔다)
            if v.get('t') and ymd(v['t']) != asof:
                continue
            roster.append(code)
            pick = bi.pick_level(v['c'], v['a'], v.get('zones'), v.get('lines'), 'up')
            if pick:
                sc[code] = pick['dist_sigma']
        if len(sc) >= 9:
            out.append((asof, nxt[asof], sc, roster))
    return out


def one_run(rnds, bars, cal, h, offset, cost):
    """비중첩 표본으로 (전략초과, 하위3분위초과, 스프레드) 회차별 계열을 만든다."""
    top, bot, bench = [], [], []
    for k in range(offset, len(rnds), h):
        asof, entry, sc, roster = rnds[k]
        rets = {c: fwd_open_ret(bars, c, cal, entry, h) for c in roster}
        rets = {c: v for c, v in rets.items() if v is not None}
        have = [c for c in sc if c in rets]
        if len(have) < 9 or len(rets) < 9:
            continue
        have.sort(key=lambda c: -sc[c])
        m = max(1, int(round(len(have) * FRAC)))
        t_ = sum(rets[c] for c in have[:m]) / m
        b_ = sum(rets[c] for c in have[-m:]) / m
        bh = sum(rets.values()) / len(rets)
        top.append(t_ - cost - bh)            # 전략(비용차감) − 보유 벤치마크
        bot.append(b_ - cost - bh)
        bench.append(bh)
    return top, bot, bench


def evaluate(rnds, bars, cal, cost, label):
    """지평별로 오프셋을 모두 돌려 (최소/중앙/최대) 와 합산 통계를 낸다."""
    res = []
    for h in HORIZONS:
        runs = []
        for off in range(h):
            top, bot, bench = one_run(rnds, bars, cal, h, off, cost)
            st = stat(top)
            if st:
                runs.append({'offset': off, 'top': st, 'bot': stat(bot),
                             'bench_mean': round(sum(bench) / len(bench), 3)})
        if not runs:
            res.append({'label': label, 'h': h, 'skip': '표본 8 미만'})
            continue
        means = [r['top']['mean'] for r in runs]
        res.append({'label': label, 'h': h, 'n_offsets': len(runs),
                    'n_per_offset': runs[0]['top']['n'],
                    'mean_min': min(means), 'mean_med': sorted(means)[len(means) // 2],
                    'mean_max': max(means),
                    'runs': runs,
                    'p_min': min(r['top']['p'] for r in runs)})
    return res


def control(rnds, bars, cal, cost, h):
    """음성 대조군 — 신호를 무작위로 바꿔 같은 절차를 N번 돌린다."""
    rng = random.Random(SEED)
    means = []
    for _ in range(N_CONTROL):
        shuffled = []
        for asof, entry, sc, roster in rnds:
            ks = list(sc)
            vs = [sc[k] for k in ks]
            rng.shuffle(vs)
            shuffled.append((asof, entry, dict(zip(ks, vs)), roster))
        top, _, _ = one_run(shuffled, bars, cal, h, 0, cost)
        if len(top) >= 8:
            means.append(sum(top) / len(top))
    means.sort()
    return means


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ohlc', required=True)
    ap.add_argument('--wide', default=None,
                    help='광역 수집 디렉터리(room_<날짜>.json) — 주면 유니버스 300으로 검정한다')
    ap.add_argument('--cost', type=float, default=None, help='왕복 비용 %% (기본 비용모델)')
    ap.add_argument('--json', default=None)
    a = ap.parse_args()

    cost = a.cost if a.cost is not None else round_trip_cost()
    pred = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    bars, order = load_bars(a.ohlc)
    cal = sessions(order)

    def room_up(it):
        return ((it.get('p_touch') or {}).get('up') or {}).get('dist_sigma')

    def room_dn(it):
        return ((it.get('p_touch') or {}).get('dn') or {}).get('dist_sigma')

    if a.wide:
        allr = rounds_wide(a.wide, pred)
        print('광역 모드 — 유니버스 300 · 레벨 규칙은 전 구간 오늘 규격으로 재계산')
    else:
        allr = rounds_with_signal(pred, room_up)
    fixed = [r for r in allr if r[0] >= SPLIT_FIXED_FROM]
    print('왕복 비용 %.3f%% · 회차 전체 %d (%s~%s) · 규격 고정 후 %d (%s~)'
          % (cost, len(allr), allr[0][0], allr[-1][0], len(fixed), SPLIT_FIXED_FROM))
    print('관측 = 회차 × 로스터. 벤치마크는 그 회차 로스터 동일가중 **보유**(비용 0)')
    print()

    blocks = [('전체 창', allr), ('규격 고정 후', fixed)]
    rows, pvals = [], []
    for label, rr in blocks:
        for r in evaluate(rr, bars, cal, cost, label):
            rows.append(r)
            if 'skip' not in r:
                pvals.append(r['p_min'])

    rej = bh_reject(pvals, 0.05)
    print('%-12s %-4s %-8s %-9s %-9s %-9s %-7s %s'
          % ('창', 'h', '표본/오프', '평균초과', '최소', '최대', 'p(최소)', 'BH'))
    k = 0
    for r in rows:
        if 'skip' in r:
            print('%-12s %-4d %s' % (r['label'], r['h'], r['skip']))
            continue
        print('%-12s %-4d %2d회 ×%d  %+8.3f%% %+8.3f%% %+8.3f%%  %6.3f  %s'
              % (r['label'], r['h'], r['n_per_offset'], r['n_offsets'],
                 r['mean_med'], r['mean_min'], r['mean_max'], r['p_min'],
                 '기각' if rej[k] else '—'))
        k += 1
    print()

    # 하위 3분위(대칭성) — 신호가 진짜면 부호가 반대여야 한다
    print('하위 3분위(같은 절차, 부호가 반대여야 신호다)')
    for label, rr in blocks:
        for r in evaluate(rr, bars, cal, cost, label):
            if 'skip' in r:
                continue
            bots = [x['bot']['mean'] for x in r['runs']]
            print('  %-12s h=%d  상위 %+.3f%% vs 하위 %+.3f%%  (스프레드 %+.3f%%p)'
                  % (label, r['h'], r['mean_med'], sorted(bots)[len(bots) // 2],
                     r['mean_med'] - sorted(bots)[len(bots) // 2]))
    print()

    # 음성 대조군
    for h in (1, 5):
        ms = control(allr, bars, cal, cost, h)
        if not ms:
            continue
        obs = next((r['mean_med'] for r in rows
                    if r.get('label') == '전체 창' and r.get('h') == h and 'skip' not in r), None)
        if obs is None:
            continue
        worse = sum(1 for m in ms if m >= obs) / len(ms) * 100
        print('음성 대조군 h=%d — 무작위 %d회 중 관측값 이상 %.1f%% '
              '(중앙 %+.3f%% · 5%%~95%% %+.3f~%+.3f%%)'
              % (h, len(ms), worse, ms[len(ms) // 2],
                 ms[int(len(ms) * .05)], ms[int(len(ms) * .95)]))
    print()

    # 참고 — 아래 여유(대칭 항목)도 같이 본다. 순위표에는 없지만 같은 가정의 쌍이다
    dn = rounds_with_signal(pred, room_dn)
    print('참고 — 「아래 여유」(순위표에 없는 대칭 항목)')
    for r in evaluate(dn, bars, cal, cost, '아래여유 전체'):
        if 'skip' not in r:
            print('  h=%d  평균초과 %+.3f%% (p %.3f)' % (r['h'], r['mean_med'], r['p_min']))

    if a.json:
        json.dump({'cost': cost, 'rows': rows}, open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

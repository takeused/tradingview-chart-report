# 저PBR(상위300의 10%) 4주 롤링 전진 추적 — 2026-10-10 에 정한 규칙·신호일을 그 뒤 데이터에만 돌린다
#
# 왜 있나 (2026-10-10): 저PBR 원장은 원래 1회성(8/14 신호)이었다. 첫 구간 결과를 본 뒤
#   롤링을 정했으므로, **이미 지난 신호일(9/11)은 넣지 않는다** — 결과를 보고 고른 구간이 된다.
#   주기는 hi52 와 같은 4주(10/23·11/20 …)로 맞췄다. 8/14 기준 주기면 다음이 10/9(한글날 휴장)라
#   그날 시총이 없어 신호가 안 나오고, 같은 구간이어야 두 후보를 나란히 비교할 수 있다.
#   선정 코드는 원장을 처음 만든 study_value 와 같은 함수다 — 8/14 의 30종목을 재현하는지로 검증한다.
#
# 사용법
#   python scripts/forward_value.py --market data/krx_marketdata_full.csv --check 2026-08-14
#   python scripts/forward_value.py --market … --positions <out.json> --signal 2026-10-23

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from study_clean_universe import run, by_score
from study_value import value_score, COST
from study_factors import HORIZON
from universe_pit import load_market, pool_cap
from factors_fundamental import load_financials

# 10/10 에 정한 값 — 바꾸지 않는다
STRATEGY = '저PBR 상위10%(시총300)'
KEY, FRAC, UNI = 'equity', 0.10, 300
FIRST_SIGNAL = '2026-10-23'


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    P = panel_io.load(os.path.join(root, 'data', 'panel_weekly_krx15.csv'))
    M = load_market(os.path.join(root, sys.argv[sys.argv.index('--market') + 1]))
    fin = load_financials()
    pool_fn = lambda t: pool_cap(P, M, t, UNI)
    sel_fn = by_score(value_score(P, M, fin, KEY))

    def select(sig):
        ts = P.di[sig]
        pool = pool_fn(ts)
        K = max(5, int(round(len(pool) * FRAC)))
        return sel_fn(ts, pool, K), len(pool)

    if '--check' in sys.argv:
        sig = sys.argv[sys.argv.index('--check') + 1]
        sel, n = select(sig)
        led = json.load(open(os.path.join(root, 'data', 'paper_trades.json'), encoding='utf-8'))
        old = {t['code'] for t in led['trades'] if t['strategy'] == STRATEGY and t['signal_date'] == sig}
        print('재현 검사 %s — 유니버스 %d · 선정 %d · 원장 %d · 일치 %d · 원장에만 %s · 새로만 %s'
              % (sig, n, len(sel or []), len(old), len(old & set(sel or [])),
                 sorted(old - set(sel or [])), sorted(set(sel or []) - old)))
        return

    if FIRST_SIGNAL in P.di:
        rows = run(P, M, pool_fn, sel_fn, P.di[FIRST_SIGNAL], FRAC)
        for r in rows:
            print('  %s 전략 %+.2f%% · 벤치 %+.2f%% · 회전율 %.0f%% · 초과 %+.2f%%'
                  % (r['date'], r['port'], r['bm'], r['turn'] * 100, r['net']))
    else:
        print('첫 신호일 %s 이 아직 패널에 없다(마지막 %s)' % (FIRST_SIGNAL, P.dates[-1]))

    if '--positions' in sys.argv:
        out = sys.argv[sys.argv.index('--positions') + 1]
        sig = sys.argv[sys.argv.index('--signal') + 1]
        sel, n = select(sig)
        json.dump({'strategy': STRATEGY, 'horizon_days': HORIZON, 'codes': sel,
                   'note': '4주 롤링(2026-10-10 결정) · 상위%d 의 %.0f%% · 자본/시총 · 유니버스 %d종목 · 왕복 %.2f%%'
                           % (UNI, FRAC * 100, n, COST)},
                  open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('원장 입력 %s — 신호 %s · %d종목' % (out, sig, len(sel)))


if __name__ == '__main__':
    main()

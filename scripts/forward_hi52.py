# 52주신고가(hi52_104w_top20) 전진 추적 — 사전 등록(2026-08-24) 규칙을 그 뒤 데이터에만 돌린다
#
# 왜 있나 (2026-10-10): 사전 등록 문서는 "2026-08-28(금) 신호로 원장을 연다"고 박았지만
#   그날 원장을 열지 않았고 트랙 B 가 6주 멈췄다. 규칙과 날짜는 f0e1c19(8/24) 커밋으로
#   그 뒤 데이터가 존재하기 전에 고정됐으므로, 지금 기계적으로 실행해도 표본외다.
#   **규칙을 한 글자라도 바꾸면 이 논리가 깨진다** — 그래서 상수를 여기 박고 고치지 않는다.
#
# 평가 코드는 백테스트(study_clean_universe.run)와 **같은 함수**를 쓴다. 전진 결과를
#   백테스트와 다른 자로 재면 비교가 무의미하다.
#
# 사용법
#   python scripts/forward_hi52.py --market data/krx_marketdata_full.csv
#   python scripts/forward_hi52.py --market … --positions <out.json>   # 마지막 신호의 종목을 원장 입력 형식으로

import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from study_clean_universe import run, by_score
from study_hi52 import hi_score, COST
from study_factors import HORIZON
from universe_pit import load_market, pool_cap

# 사전 등록에 박힌 값 — 바꾸지 않는다
STRATEGY = 'hi52_104w_top20'
WIN, FRAC, UNI = 104, 0.20, 1000
FIRST_SIGNAL = '2026-08-28'
PREREG_COMMIT = 'f0e1c19'


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    mpath = sys.argv[sys.argv.index('--market') + 1]
    P = panel_io.load(os.path.join(root, 'data', 'panel_weekly_krx15.csv'))
    M = load_market(os.path.join(root, mpath))
    assert FIRST_SIGNAL in P.di, '패널에 %s 주가 없다(마지막 %s)' % (FIRST_SIGNAL, P.dates[-1])
    t0 = P.di[FIRST_SIGNAL]
    pool_fn = lambda t: pool_cap(P, M, t, UNI)
    sel_fn = by_score(hi_score(P, WIN))

    print('%s 전진 추적 — 규칙 고정 %s(2026-08-24) · 첫 신호 %s · 패널 마지막 %s'
          % (STRATEGY, PREREG_COMMIT, FIRST_SIGNAL, P.dates[-1]))
    print('창 %d주 · 상위 %d 의 %.0f%% · %d주 보유 · 다음 주 시가 진입 · 왕복비용 %.2f%%'
          % (WIN, UNI, FRAC * 100, HORIZON, COST))
    rows = run(P, M, pool_fn, sel_fn, t0, FRAC)
    print('\n완료 사이클 %d개' % len(rows))
    print('  %-10s %6s %9s %9s %7s %9s %9s' % ('신호일', '유니', '전략%', '벤치%', '회전율', '초과%', '로그초과%'))
    for r in rows:
        lg = 100 * (math.log(1 + (r['port'] - COST * r['turn']) / 100) - math.log(1 + r['bm'] / 100))
        print('  %-10s %6d %+9.2f %+9.2f %6.0f%% %+9.2f %+9.2f'
              % (r['date'], r['n'], r['port'], r['bm'], r['turn'] * 100, r['net'], lg))

    # 아직 만기 전인 신호 — 다음 사이클 신호일과 그 종목
    last_complete = [r['date'] for r in rows]
    pending = [P.dates[k] for k in range(t0, P.T, HORIZON) if P.dates[k] not in last_complete]
    print('\n만기 전 신호일: %s' % (', '.join(pending) or '없음'))

    if '--positions' in sys.argv:
        out = sys.argv[sys.argv.index('--positions') + 1]
        sig = sys.argv[sys.argv.index('--signal') + 1] if '--signal' in sys.argv else FIRST_SIGNAL
        ts = P.di[sig]
        pool = pool_fn(ts)
        K = max(5, int(round(len(pool) * FRAC)))
        sel = sel_fn(ts, pool, K)
        json.dump({'strategy': STRATEGY, 'horizon_days': HORIZON, 'codes': sel,
                   'note': '사전 등록 %s(2026-08-24) 규칙 그대로 · 창 %d주 · 상위%d 의 %.0f%% · 유니버스 %d종목'
                           % (PREREG_COMMIT, WIN, UNI, FRAC * 100, len(pool))},
                  open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('원장 입력 %s — 신호 %s · %d종목' % (out, sig, len(sel)))


if __name__ == '__main__':
    main()

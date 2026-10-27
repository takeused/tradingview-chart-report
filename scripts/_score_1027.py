# 2026-10-27 회차 채점 — 10/26 을 건너뛰어 10/23 entry 를 10/26 고저로 정식 채점하고, 10/27 은 원장만 한 칸 진행시킨다
import json, os, subprocess, sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import score_touch as st
from json_io import dump_predictions

bars = json.load(open(os.path.join(S, 'bars_daily.json')))
a26 = json.load(open(os.path.join(S, 'actuals_1026.json'), encoding='utf-8'))
a27 = json.load(open(os.path.join(S, 'actuals.json'), encoding='utf-8'))
# 10/26 종가가 bars_daily 의 어제 종가와 일치해야 한다
for c, v in a26.items():
    assert abs(bars[c][-2][1] - v['close']) < 1e-6, c
    assert abs(bars[c][-1][1] - a27[c]['close']) < 1e-6, c
print('actuals ok', len(a26), len(a27))

if '--run' in sys.argv:
    sys.argv = ['score_touch.py', os.path.join(S, 'actuals_1026.json'), '--session', '2026-10-26', '--write']
    st.main()
    d = json.load(open(st.PRED, encoding='utf-8'))
    e = d['entries'][-1]
    assert e['asof'] == '2026-10-23' and e['scored'] is not None
    ex = st.close_open_calls(d['open_calls'], a27, '2026-10-27')
    ex.pop('rows', None)
    ex['session'] = '2026-10-27'
    e['scored'].setdefault('open_calls_extra_sessions', []).append(ex)
    dump_predictions(d, st.PRED)
    print(json.dumps({k: v for k, v in ex.items() if k != 'shift_null'}, ensure_ascii=False, indent=1))

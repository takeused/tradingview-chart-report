# 2026-11-04 회차 채점 — 11/2·11/3 을 건너뛰어 10/30 entry 를 11/2 고저로 정식 채점하고, 11/3·11/4 는 원장만 한 칸씩 진행시킨다
import json, os, sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import score_touch as st
from json_io import dump_predictions

bars = json.load(open(os.path.join(S, 'bars_daily.json')))
a1 = json.load(open(os.path.join(S, 'actuals_1102.json'), encoding='utf-8'))
a2 = json.load(open(os.path.join(S, 'actuals_1103.json'), encoding='utf-8'))
a3 = json.load(open(os.path.join(S, 'actuals.json'), encoding='utf-8'))
for c, v in a1.items():
    assert abs(bars[c][-3][1] - v['close']) < 1e-6, c
    assert abs(bars[c][-2][1] - a2[c]['close']) < 1e-6, c
    assert abs(bars[c][-1][1] - a3[c]['close']) < 1e-6, c
print('actuals ok', len(a1), len(a2), len(a3))

if '--run' in sys.argv:
    sys.argv = ['score_touch.py', os.path.join(S, 'actuals_1102.json'), '--session', '2026-11-02', '--write']
    st.main()
    d = json.load(open(st.PRED, encoding='utf-8'))
    e = d['entries'][-1]
    assert e['asof'] == '2026-10-30' and e['scored'] is not None
    for a, ses in ((a2, '2026-11-03'), (a3, '2026-11-04')):
        ex = st.close_open_calls(d['open_calls'], a, ses)
        ex.pop('rows', None)
        ex['session'] = ses
        e['scored'].setdefault('open_calls_extra_sessions', []).append(ex)
        print(json.dumps({k: v for k, v in ex.items() if k != 'shift_null'}, ensure_ascii=False, indent=1))
    dump_predictions(d, st.PRED)

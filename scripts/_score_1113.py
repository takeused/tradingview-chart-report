# 2026-11-13 회차 채점 — 11/9~11/12 를 건너뛰어 11/6 entry 를 11/9 고저로 정식 채점하고, 11/10~11/13 은 원장만 한 칸씩 진행시킨다
import json, os, sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import score_touch as st
from json_io import dump_predictions

bars = json.load(open(os.path.join(S, 'bars_daily.json')))
A = [json.load(open(os.path.join(S, n), encoding='utf-8')) for n in
     ('actuals_1109.json', 'actuals_1110.json', 'actuals_1111.json', 'actuals_1112.json', 'actuals.json')]
SES = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13']
for k, a in enumerate(A):
    for c, v in a.items():
        assert abs(bars[c][-5 + k][1] - v['close']) < 1e-6, (c, k)
print('actuals ok', [len(a) for a in A])

if '--run' in sys.argv:
    sys.argv = ['score_touch.py', os.path.join(S, 'actuals_1109.json'), '--session', SES[0], '--write']
    st.main()
    d = json.load(open(st.PRED, encoding='utf-8'))
    e = d['entries'][-1]
    assert e['asof'] == '2026-11-06' and e['scored'] is not None
    for a, ses in zip(A[1:], SES[1:]):
        ex = st.close_open_calls(d['open_calls'], a, ses)
        ex.pop('rows', None)
        ex['session'] = ses
        e['scored'].setdefault('open_calls_extra_sessions', []).append(ex)
        print(json.dumps({k: v for k, v in ex.items() if k != 'shift_null'}, ensure_ascii=False))
    dump_predictions(d, st.PRED)

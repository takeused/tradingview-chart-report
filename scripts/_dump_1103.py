# 건너뛴 11/2·11/3 봉 고저를 차트 페이지 메모리(window.__D.data)에서 꺼내 actuals_1102.json·actuals_1103.json 으로 저장한다
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp_fetch
S = os.path.dirname(os.path.abspath(__file__))
r = asyncio.run(cdp_fetch.evaluate("""(()=>{const o={};const D=window.__D.data;for(const k in D){const a=D[k];if(a&&a.length>3){const n=a.length;o[k.replace('KRX:','')]=[n-3,n-2].map(i=>({hi:a[i][2],lo:a[i][3],close:a[i][4],time:a[i][0]}))}}return JSON.stringify(o)})()"""))
d = json.loads(r); d.pop('KOSPI'); d.pop('KOSDAQ')
for k, name in ((0, 'actuals_1102.json'), (1, 'actuals_1103.json')):
    json.dump({c: v[k] for c, v in d.items()}, open(os.path.join(S, name), 'w'))
    print(name, len(d), {v[k]['time'] for v in d.values()})
bars = json.load(open(os.path.join(S, 'bars_daily.json')))
for c, v in d.items():
    assert abs(bars[c][-3][1] - v[0]['close']) < 1e-6 and abs(bars[c][-2][1] - v[1]['close']) < 1e-6, c
print('종가 대조 통과', len(d))

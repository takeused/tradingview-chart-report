# 10/26 봉 고저를 차트 페이지 메모리에서 꺼내 actuals_1029.json 으로 저장한다
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp_fetch
r = asyncio.run(cdp_fetch.evaluate("""(()=>{const o={};const D=window.__D.data;for(const k in D){const a=D[k];if(a&&a.length>1){const b=a[a.length-2];o[k.replace('KRX:','')]={hi:b[2],lo:b[3],close:b[4],time:b[0]}}}return JSON.stringify(o)})()"""))
d = json.loads(r); d.pop('KOSPI'); d.pop('KOSDAQ')
json.dump(d, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'actuals_1029.json'), 'w'))
print(len(d), {v['time'] for v in d.values()})

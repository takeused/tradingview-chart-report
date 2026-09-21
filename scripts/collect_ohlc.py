# room_up 검정용 일봉 OHLC 수집 — predictions.json 에 등장한 전 종목(43)
#
# 왜 따로 받나: collect.py 의 BARS 는 [time, close] 만 남긴다(베타용). 검정은
#   **익일 시가 진입 · 만기 시가 청산**이라 open 이 반드시 필요하다.
import asyncio, json, os, sys, time

ROOT = r'D:\01 WORK\260705 Trading View'
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cdp_fetch

# --universe 를 주면 그 목록으로, 아니면 리포트 로스터 전체로 받는다
if '--universe' in sys.argv:
    U = json.load(open(sys.argv[sys.argv.index('--universe') + 1], encoding='utf-8'))
    CODES = sorted({u['code'] for u in U})
else:
    pred = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    CODES = sorted({i['code'] for e in pred['entries'] for i in e['items']})
OUT = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'ohlc.json'
SYMS = ['KRX:' + c for c in CODES] + ['KRX:KOSPI', 'KRX:KOSDAQ']


def ev(expr):
    return asyncio.run(cdp_fetch.evaluate(expr))


LOADER = """
(() => {
  const SYMS = %s;
  window.__R = { state:'run', i:0, data:{}, sym:{}, err:[] };
  const R = window.__R;
  const chart = window.TradingViewApi.activeChart();
  const grab = () => {
    const bars = chart.getSeries().data().bars();
    const arr=[];
    bars.each((idx,v)=>{ arr.push([v[0], v[1], v[2], v[3], v[4]]); return false; });
    return arr.slice(-200);
  };
  // 감시 타이머 — 콜백이 영영 안 오는 심볼이 있다(동양생명 082640 · 미래에셋생명 085620).
  // 하나가 막으면 수집이 통째로 선다. 2026-09-21 밤에 167/300 에서 실제로 섰다.
  const step = (k) => {
    R.i = k;
    if (k >= SYMS.length) { R.state='done'; return; }
    let settled = false;
    const finish = (okFlag) => {
      if (settled) return; settled = true;
      if (okFlag) {
        try { const r = grab(); R.data[SYMS[k].replace('KRX:','')] = r;
              R.sym[SYMS[k].replace('KRX:','')] = chart.symbol(); }
        catch(e){ R.err.push(SYMS[k]+':'+e.message); }
      } else { R.err.push(SYMS[k]+':timeout'); }
      step(k+1);
    };
    const guard = setTimeout(() => finish(false), 14000);
    chart.setSymbol(SYMS[k], () => setTimeout(() => {
      clearTimeout(guard); finish(true);
    }, 2200));
  };
  step(0);
  return 'started '+SYMS.length;
})()
"""
POLL = "JSON.stringify({state:window.__R.state, i:window.__R.i, got:Object.keys(window.__R.data).length, err:window.__R.err})"
DUMP = "JSON.stringify({data:window.__R.data, sym:window.__R.sym})"

if __name__ == '__main__':
    print(ev(LOADER % json.dumps(SYMS)))
    t0 = time.time()
    while True:
        st = json.loads(ev(POLL))
        if st['state'] == 'done':
            print('done got=%d err=%s (%.0fs)' % (st['got'], st['err'], time.time() - t0))
            break
        if time.time() - t0 > 3600:
            raise SystemExit('타임아웃 %s' % st)
        print('  %d/%d' % (st['i'], len(SYMS)))
        time.sleep(20)
    txt = ev(DUMP)
    open(os.path.join(S, OUT), 'w', encoding='utf-8').write(txt)
    g = json.loads(txt)
    bad = [(c, s) for c, s in g['sym'].items() if s.split(':')[-1] != c]
    print('wrote %s (%d bytes) / sym mismatch %s' % (OUT, len(txt), bad))

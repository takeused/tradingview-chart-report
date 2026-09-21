# 광역 room_up 수집 — 시점별 상위 300종목 × 회차 날짜, 바 리플레이로 소급
#
# 왜: room_up 은 차트의 SMC 존·스윙 라인에서 나와서 패널로 계산할 수 없다. 종목마다
#   차트를 띄워 읽어야 하고, 과거 날짜는 replay 로 마지막 봉을 고정해야 그 시점의
#   존·라인이 나온다(소진된 존은 오늘 읽으면 이미 사라지고 없다).
#
# 회차마다 파일을 따로 쓴다 — 6시간짜리 수집이라 **중단되면 이어서** 돌릴 수 있어야 한다.
#
# 사용법
#   python collect_wide.py --dates <json> --universe <json> --out <dir> [--only 2026-09-18]

import argparse, asyncio, json, os, sys, time

ROOT = r'D:\01 WORK\260705 Trading View'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cdp_fetch

SETTLE = 2500
NEAR = 3.5          # 종가 +-3.5 ATR 밖은 버린다(레벨 선정 상한이 3σ)


def ev(expr):
    return asyncio.run(cdp_fetch.evaluate(expr))


LOADER = """
(() => {
  const SYMS = %s, SETTLE = %d, NEAR = %s, START = %d;  // SETTLE 은 더 안 쓴다
  if (START === 0 || !window.__X) window.__X = { state:'run', i:0, data:{}, err:[] };
  window.__X.state = 'run';
  const X = window.__X;
  const chart = window.TradingViewApi.activeChart();
  const readGfx = (collectionName, mapKey) => {
    const cw = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
    const sources = cw.model().model().dataSources();
    const res = {};
    for (let si=0; si<sources.length; si++) {
      const s = sources[si];
      if (!s.metaInfo) continue;
      try {
        const meta = s.metaInfo();
        const name = meta.description || meta.shortDescription || '';
        if (!name) continue;
        const g = s._graphics;
        if (!g || !g._primitivesCollection) continue;
        const outer = g._primitivesCollection[collectionName];
        if (!outer) continue;
        const inner = outer.get(mapKey);
        if (!inner) continue;
        const coll = inner.get(false);
        if (!coll || !coll._primitivesDataById || coll._primitivesDataById.size === 0) continue;
        const items = [];
        coll._primitivesDataById.forEach((v,id)=>{ items.push(v); });
        res[name] = items;
      } catch(e) {}
    }
    return res;
  };
  const BOX = 'Smart Money Concepts [LuxAlgo]';
  const LINE = 'Swing Structure (HH/HL/LH/LL) + S/R';
  // 지표가 다 그려졌는지 — 직전 심볼의 서명과 달라지고, 박스·라인이 모두 채워졌을 때.
  // 2500ms 고정 대기는 **SMC 박스가 아직 안 그려진 상태를 읽고 있었다**(2026-09-21 확인:
  // KB금융 9/18 존 2개가 2500ms 에서는 0개, 5000ms 에서 정확히 나왔다). 게다가 그 사이
  // chart.symbol() 은 이미 새 심볼이라 심볼 대조로는 못 잡는다 — 조용히 틀리는 구조였다.
  const sigOf = () => {
    const bx = readGfx('dwgboxes','boxes')[BOX] || [];
    const ln = readGfx('dwglines','lines')[LINE] || [];
    let h = bx.length*1e6 + ln.length;
    for (let i=0;i<bx.length && i<5;i++) h += (bx[i].y1||0);
    for (let i=0;i<ln.length && i<5;i++) h += (ln[i].y1||0);
    return {sig: Math.round(h*100)/100, nb: bx.length, nl: ln.length};
  };
  const grab = () => {
    const bars = chart.getSeries().data().bars();
    const b=[];
    bars.each((idx,v)=>{ b.push([v[0], v[1], v[2], v[3], v[4]]); return false; });
    const a = b.slice(-200), n = a.length;
    if (n < 100) return {err:'short'+n};
    const C = a[n-1][4];
    const TR=[]; for(let k=1;k<n;k++) TR.push(Math.max(a[k][2]-a[k][3],
        Math.abs(a[k][2]-a[k-1][4]), Math.abs(a[k][3]-a[k-1][4])));
    let atr=0; for(let k=0;k<14;k++) atr+=TR[k]; atr/=14;
    for(let k=14;k<TR.length;k++) atr=(atr*13+TR[k])/14;
    const lim = NEAR*atr;
    const bx = readGfx('dwgboxes','boxes')[BOX] || [];
    const ln = readGfx('dwglines','lines')[LINE] || [];
    const seen={}, zones=[];
    bx.forEach(v=>{ if(v.y1==null||v.y2==null) return;
      const hi=Math.round(Math.max(v.y1,v.y2)*100)/100, lo=Math.round(Math.min(v.y1,v.y2)*100)/100;
      if (lo > C+lim || hi < C-lim) return;
      const k=hi+':'+lo; if(!seen[k]){seen[k]=1; zones.push([hi,lo]);} });
    const s2={}, lines=[];
    ln.forEach(v=>{ if(v.y1==null||v.y1!==v.y2) return;
      const y=Math.round(v.y1*100)/100;
      if (y > C+lim || y < C-lim) return;
      if(!s2[y]){s2[y]=1; lines.push(y);} });
    zones.sort((p,q)=>q[0]-p[0]); lines.sort((p,q)=>q-p);
    return {c:C, a:atr, n:n, t:a[n-1][0], zones:zones, lines:lines, sym:chart.symbol()};
  };
  // 감시 타이머 — setSymbol 콜백이 영영 안 오는 심볼이 있다(2026-09-21 동양생명 082640).
  // 하나가 막으면 6시간짜리 수집이 통째로 선다. 시간이 지나면 err 로 적고 다음으로 간다.
  const MINW = 1200, MAXW = 9000, TICK = 300;
  const step = (k) => {
    X.i = k;
    if (k >= SYMS.length) { X.state='done'; return; }
    const want = SYMS[k].replace('KRX:','');
    const before = sigOf().sig;
    let settled = false;
    const finish = (okFlag, why) => {
      if (settled) return; settled = true;
      if (okFlag) {
        try {
          const r = grab();
          if ((r.sym||'').split(':').pop() !== want) X.err.push(SYMS[k]+':symmismatch');
          else { r.w = why; X.data[want] = r; }
        } catch(e){ X.err.push(SYMS[k]+':'+e.message); }
      } else { X.err.push(SYMS[k]+':'+why); }
      step(k+1);
    };
    const guard = setTimeout(() => finish(false, 'timeout'), MAXW + 8000);
    chart.setSymbol(SYMS[k], () => {
      const t0 = Date.now();
      const tick = () => {
        if (settled) return;
        const el = Date.now() - t0;
        const s2 = sigOf();
        const ready = (s2.sig !== before) && s2.nb > 0 && s2.nl > 0;
        if (el >= MINW && ready) { clearTimeout(guard); finish(true, el); return; }
        if (el >= MAXW) { clearTimeout(guard); finish(true, 'max'+el); return; }
        setTimeout(tick, TICK);
      };
      setTimeout(tick, MINW);
    });
  };
  step(START);
  return 'started '+SYMS.length;
})()
"""
POLL = "JSON.stringify({state:window.__X.state, i:window.__X.i, got:Object.keys(window.__X.data).length, nerr:window.__X.err.length})"
DUMP = "JSON.stringify(window.__X.data)"


RP = 'window.TradingViewApi._replayApi'


def replay_to(date_next):
    """리플레이 시점을 date_next 로 옮긴다 — 마지막 봉이 그 직전 거래일로 고정된다.

    MCP replay_start 가 하는 일과 같다(src/core/replay.js). 25회차를 무인으로 돌리려고
    같은 JS 를 직접 부른다. 툴바는 이미 떠 있다고 본다(첫 회차만 MCP 로 연다).
    """
    ev("%s.selectDate(new Date('%s'))" % (RP, date_next))
    time.sleep(2.0)
    bad = ev("""(function(){
      var t = document.querySelectorAll('[class*="toast"],[class*="notification"]');
      for (var i=0;i<t.length;i++){ var x=t[i].textContent||'';
        if (/data point unavailable|not available for playback/i.test(x)) return x.trim().slice(0,120); }
      return null; })()""")
    if bad:
        raise SystemExit('리플레이 날짜 불가 %s — %s' % (date_next, bad))


def progress(path, line):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line + chr(10))
    print(line, flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dates', required=True)
    ap.add_argument('--universe', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', default=None)
    ap.add_argument('--settle', type=int, default=SETTLE)
    ap.add_argument('--replay', action='store_true',
                    help='회차마다 리플레이 시점을 직접 옮긴다(무인 실행)')
    ap.add_argument('--progress', default=None, help='진행상황을 덧붙여 쓸 파일')
    ap.add_argument('--start', type=int, default=0,
                    help='이어받기 — 이 인덱스부터. window.__X 를 유지한다')
    a = ap.parse_args()

    dates = json.load(open(a.dates, encoding='utf-8'))
    if a.only:
        dates = [d for d in dates if d == a.only]
    uni = json.load(open(a.universe, encoding='utf-8'))
    pred = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    nxt = {e['asof']: e['next_session'] for e in pred['entries']}
    syms = ['KRX:' + u['code'] for u in uni]
    os.makedirs(a.out, exist_ok=True)

    for d in dates:
        p = os.path.join(a.out, 'room_%s.json' % d)
        if os.path.exists(p):
            print('%s — 이미 있음, 건너뜀' % d)
            continue
        prog = a.progress or os.path.join(a.out, 'progress.log')
        progress(prog, '%s  %s 시작 (%d종목)'
                 % (time.strftime('%H:%M:%S'), d, len(syms)))
        t0 = time.time()
        if a.replay:
            replay_to(nxt[d])
        print(' ', ev(LOADER % (json.dumps(syms), a.settle, NEAR, a.start)), flush=True)
        while True:
            st = json.loads(ev(POLL))
            if st['state'] == 'done':
                break
            if time.time() - t0 > 7200:
                raise SystemExit('타임아웃 %s' % st)
            print('   %d/%d (%.0f초)' % (st['i'], len(syms), time.time() - t0), flush=True)
            time.sleep(30)
        txt = ev(DUMP)
        open(p, 'w', encoding='utf-8').write(txt)
        g = json.loads(txt)
        bad = [c for c, v in g.items() if v.get('sym', '').split(':')[-1] != c]
        short = [c for c, v in g.items() if v.get('err')]
        # 리플레이가 제대로 걸렸는지 — 마지막 봉 날짜가 그 회차여야 한다
        import datetime
        days = {}
        for v in g.values():
            if v.get('t'):
                z = datetime.datetime.utcfromtimestamp(v['t'])
                k = '%04d-%02d-%02d' % (z.year, z.month, z.day)
                days[k] = days.get(k, 0) + 1
        top = sorted(days.items(), key=lambda x: -x[1])[:2]
        progress(prog, '  %s 완료 — %d종목 · %.1f분 · 심볼불일치 %d · 봉부족 %d · 마지막봉 %s'
                 % (d, len(g), (time.time() - t0) / 60, len(bad), len(short), top))
        if top and top[0][0] != d:
            progress(prog, '  [경고] %s 회차인데 마지막 봉이 %s 다 — 리플레이 확인 필요' % (d, top[0][0]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

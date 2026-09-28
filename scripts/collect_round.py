# 회차 수집 드라이버 — 봉·지표·실제값·그래픽(존/라인)을 CDP 직결로 받아 파일에 쓴다
import asyncio, json, os, sys, time

ROOT = r'D:\01 WORK\260705 Trading View'
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cdp_fetch

TF = sys.argv[1] if len(sys.argv) > 1 else 'daily'
PRE = 'W' if TF == 'weekly' else 'D'

# 2026-09-21: 로스터가 바뀐 회차라 roster.json 에서 읽는다.
# extra_for_actuals 는 직전 회차에만 있던 코드 — 채점용 고저가 필요해 봉만 받는다
# (선택편향 방지). 그래픽(존/라인)은 오늘 로스터에만 받는다.
_R = json.load(open(os.path.join(S, 'roster.json'), encoding='utf-8'))
ROSTER = [(c, m) for c, n, m in _R['roster']]
EXTRA = _R.get('extra_for_actuals', []) if TF == 'daily' else []   # 채점용 고저는 일봉만 필요
SYMS = ['KRX:' + c for c, _ in ROSTER] + ['KRX:' + c for c in EXTRA] + ['KRX:KOSPI', 'KRX:KOSDAQ']
KQ = [c for c, m in ROSTER if m == 'KOSDAQ']


def ev(expr):
    return asyncio.run(cdp_fetch.evaluate(expr))


LOADER = """
(() => {
  const SYMS = %s;
  window.__%s = { state:'run', i:0, total:SYMS.length, data:{}, sym:{}, err:[] };
  const W = window.__%s;
  const chart = window.TradingViewApi.activeChart();
  const grab = () => {
    const bars = chart.getSeries().data().bars();
    const arr=[];
    bars.each((idx,v)=>{ arr.push([v[0], v[1], v[2], v[3], v[4], v[5]]); return false; });
    return arr.slice(-200);
  };
  const step = (k) => {
    W.i = k;
    if (k >= SYMS.length) { W.state='done'; return; }
    chart.setSymbol(SYMS[k], () => setTimeout(() => {
      try { const r = grab();
            if (r.length < 100) W.err.push(SYMS[k]+':short'+r.length);
            W.data[SYMS[k]] = r; W.sym[SYMS[k]] = chart.symbol(); }
      catch(e){ W.err.push(SYMS[k]+':'+e.message); }
      step(k+1);
    }, 2200));
  };
  step(0);
  return 'started '+SYMS.length;
})()
"""

POLL = "JSON.stringify({state:window.__%s.state, i:window.__%s.i, got:Object.keys(window.__%s.data).length, err:window.__%s.err})"

METRICS = """
(() => {
  const D = window.__%s.data, SY = window.__%s.sym;
  const KQ = new Set(%s);
  const out = {};
  const ymd = t => { const z=new Date(t*1000); return z.getUTCFullYear()*10000+(z.getUTCMonth()+1)*100+z.getUTCDate(); };
  Object.keys(D).forEach(sym => {
    const code = sym.replace('KRX:',''), b = D[sym], n = b.length;
    if (n < 100) { out[code]={err:'short'+n}; return; }
    const i = n-1, C=b[i][4], PC=b[i-1][4], H=b[i][2], L=b[i][3], V=b[i][5];
    const TR=[]; for(let k=1;k<n;k++) TR.push(Math.max(b[k][2]-b[k][3], Math.abs(b[k][2]-b[k-1][4]), Math.abs(b[k][3]-b[k-1][4])));
    let atr=0; for(let k=0;k<14;k++) atr+=TR[k]; atr/=14;
    for(let k=14;k<TR.length;k++) atr=(atr*13+TR[k])/14;
    let v20=0; for(let k=i-20;k<i;k++) v20+=b[k][5]; v20/=20;
    let st=0; for(let k=i;k>0;k--){ const up=b[k][4]>b[k-1][4];
      if(st===0) st=up?1:-1; else if((st>0)===up) st+=up?1:-1; else break; if(Math.abs(st)>20) break; }
    const c4=b[i-4]?b[i-4][4]:null, c12=b[i-12]?b[i-12][4]:null;
    let hi12=-1e18, lo12=1e18;
    for(let k=Math.max(0,i-12);k<i;k++){ if(b[k][2]>hi12)hi12=b[k][2]; if(b[k][3]<lo12)lo12=b[k][3]; }
    const pos12 = hi12>lo12 ? Math.round((C-lo12)/(hi12-lo12)*100) : 50;
    out[code] = { mkt: KQ.has(code)?'Q':'P', date: ymd(b[i][0]), sym_actual: SY[sym]||'',
      bars: n,
      close:Math.round(C), prevC:Math.round(PC), chg:+(((C-PC)/PC)*100).toFixed(2),
      hi:Math.round(H), lo:Math.round(L), vol:Math.round(V), v20:Math.round(v20),
      volx:+(V/v20).toFixed(2), atr:Math.round(atr), atrpct:+(atr/C*100).toFixed(2),
      rng:Math.round(H-L), rngatr:+((H-L)/atr).toFixed(2),
      clsloc: H>L ? +((C-L)/(H-L)).toFixed(2) : 0.5, streak: st,
      mom4: c4? +(((C-c4)/c4)*100).toFixed(2) : null,
      mom12: c12? +(((C-c12)/c12)*100).toFixed(2) : null, pos12: pos12 };
  });
  return JSON.stringify(out);
})()
"""

ACTUALS = """
JSON.stringify(Object.fromEntries(Object.entries(window.__%s.data).map(([s,b])=>{
  const i=b.length-1; return [s.replace('KRX:',''), {hi:b[i][2], lo:b[i][3], close:b[i][4]}];
})))
"""

# 원봉 전체를 파일로 (베타 계산용)
BARS = """
JSON.stringify(Object.fromEntries(Object.entries(window.__%s.data).map(([s,b])=>[s.replace('KRX:',''), b.map(r=>[r[0],r[4]])])))
"""

GRAPHICS = """
(() => {
  const SYMS = %s;
  window.__G = { state:'run', i:0, total:SYMS.length, data:{}, err:[] };
  const G = window.__G;
  const chart = window.TradingViewApi.activeChart();
  const read = (collectionName, mapKey) => {
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
        const pc = g._primitivesCollection;
        const outer = pc[collectionName];
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
  const BOXN = 'Smart Money Concepts [LuxAlgo]';
  const LINEN = 'Swing Structure (HH/HL/LH/LL) + S/R';
  // 지표가 다 그려졌는지 — 직전 심볼의 서명과 달라지고 박스·라인이 모두 찼을 때.
  // 고정 대기 2500ms 는 **아직 안 그려진 상태를 읽는다**(2026-09-22 회차에서 27종목 중
  // 22종목이 빈 채로 수집됐다. 페이지를 새로 띄운 직후라 계산이 느렸다).
  // 그 사이 chart.symbol() 은 이미 새 심볼이라 심볼 대조로는 절대 못 잡는다.
  const sigOf = () => {
    const bx = read('dwgboxes','boxes')[BOXN] || [];
    const ln = read('dwglines','lines')[LINEN] || [];
    let h = bx.length*1e6 + ln.length;
    for (let i=0;i<bx.length && i<5;i++) h += (bx[i].y1||0);
    for (let i=0;i<ln.length && i<5;i++) h += (ln[i].y1||0);
    return {sig: Math.round(h*100)/100, nb: bx.length, nl: ln.length};
  };
  const grab = () => {
    const boxesRaw = read('dwgboxes','boxes'), linesRaw = read('dwglines','lines');
    const boxes = {}, lines = {};
    Object.keys(boxesRaw).forEach(n => {
      const seen={}, z=[];
      boxesRaw[n].forEach(v=>{ if(v.y1==null||v.y2==null) return;
        const hi=Math.round(Math.max(v.y1,v.y2)*100)/100, lo=Math.round(Math.min(v.y1,v.y2)*100)/100;
        const k=hi+':'+lo; if(!seen[k]){seen[k]=1; z.push([hi,lo]);} });
      z.sort((a,b)=>b[0]-a[0]); boxes[n]=z;
    });
    Object.keys(linesRaw).forEach(n => {
      const seen={}, h=[];
      linesRaw[n].forEach(v=>{ if(v.y1==null||v.y1!==v.y2) return;
        const y=Math.round(v.y1*100)/100; if(!seen[y]){seen[y]=1; h.push(y);} });
      h.sort((a,b)=>b-a); lines[n]=h;
    });
    return {boxes, lines, sym_actual: chart.symbol()};
  };
  // 박스·라인이 빈 채로 MAXW 를 넘기면 **저장하지 않고 심볼을 다시 건다** (2026-09-28).
  // 그날 에스티팜·티엘비·배럴·넥스틴 4종목이 박스 0개인 채 'max' 로 저장됐고,
  // build_items 가 그걸 "존 없음"으로 받아 배럴·넥스틴은 레벨이 양쪽 다 사라졌다.
  // 실측: 에스티팜은 처음 불러오면 **60초를 기다려도** 박스가 0개였는데, 다시 불러오니
  // 1초 만에 5개가 찼다. 오래 기다리는 것으로는 안 되고 다시 걸어야 한다.
  // 다른 심볼(BOUNCE)을 한 번 거쳐 오는 이유는 같은 심볼을 다시 set 하면 무시될 수 있어서다.
  // RETRY 번 다시 걸어도 비면 G.err 로 보내고 data 에 넣지 않는다 — 없는 것과 못 읽은 것을
  // 구별할 수 없으니, 조용히 '없음'으로 저장하지 않는다.
  const MINW = 1200, MAXW = 12000, TICK = 300, RETRY = 2, BOUNCE = 'KRX:KOSPI';
  const step = (k) => {
    G.i = k;
    if (k >= SYMS.length) { G.state='done'; return; }
    attempt(k, 0);
  };
  const attempt = (k, n) => {
    const before = sigOf().sig;
    let settled = false;
    const finish = (okFlag, why) => {
      if (settled) return; settled = true;
      if (okFlag) {
        try { const r = grab(); r.w = why; r.tries = n + 1; G.data[SYMS[k].replace('KRX:','')] = r; }
        catch(e){ G.err.push(SYMS[k]+':'+e.message); }
      } else if (n < RETRY) {
        chart.setSymbol(BOUNCE, () => setTimeout(() => attempt(k, n + 1), 800));
        return;
      } else { G.err.push(SYMS[k]+':'+why); }
      step(k+1);
    };
    const guard = setTimeout(() => finish(false, 'timeout'), MAXW + 8000);
    chart.setSymbol(SYMS[k], () => {
      const t0 = Date.now();
      const tick = () => {
        if (settled) return;
        const el = Date.now() - t0, s2 = sigOf();
        if (el >= MINW && s2.sig !== before && s2.nb > 0 && s2.nl > 0) {
          clearTimeout(guard); finish(true, el); return;
        }
        if (el >= MAXW) {
          // 찼는데 서명이 그대로면 **직전 심볼의 그림**일 수 있다 — 이것도 저장하지 않는다.
          clearTimeout(guard);
          finish(false, (s2.sig === before ? 'stale' : 'empty') + '(box ' + s2.nb + ' · line ' + s2.nl + ')');
          return;
        }
        setTimeout(tick, TICK);
      };
      setTimeout(tick, MINW);
    });
  };
  step(0);
  return 'started '+SYMS.length;
})()
"""

GPOLL = "JSON.stringify({state:window.__G.state, i:window.__G.i, got:Object.keys(window.__G.data).length, err:window.__G.err})"


def wait(poll_expr, total):
    t0 = time.time()
    while True:
        st = json.loads(ev(poll_expr))
        if st['state'] == 'done':
            print('  done got=%d err=%s (%.0fs)' % (st['got'], st['err'], time.time() - t0))
            return st
        if time.time() - t0 > 600:
            raise SystemExit('타임아웃: %s' % st)
        print('  %d/%d ...' % (st['i'], total))
        time.sleep(12)


def write(name, text):
    p = os.path.join(S, name)
    open(p, 'w', encoding='utf-8').write(text)
    print('  wrote %s (%d bytes)' % (name, len(text)))


if __name__ == '__main__':
    print('1) 봉 적재 (%s, %d심볼)' % (TF, len(SYMS)))
    print(' ', ev(LOADER % (json.dumps(SYMS), PRE, PRE)))
    wait(POLL % (PRE, PRE, PRE, PRE), len(SYMS))

    print('2) 지표 계산')
    write('metrics_%s.json' % TF, ev(METRICS % (PRE, PRE, json.dumps(KQ))))
    write('bars_%s.json' % TF, ev(BARS % PRE))
    if TF == 'daily':
        write('actuals.json', ev(ACTUALS % PRE))

    print('3) 그래픽(존·라인)')
    gsyms = ['KRX:' + c for c, _ in ROSTER]
    print(' ', ev(GRAPHICS % json.dumps(gsyms)))
    st = wait(GPOLL, len(gsyms))
    gdata = json.loads(ev("JSON.stringify(window.__G.data)"))
    # 실패한 종목만 **새 패스로** 다시 받는다(최대 2패스). 같은 루프 안의 재시도만으로는
    # 모자랐다 — 2026-09-28 실측에서 KOSPI 로 바꾼 직후 차트가 알테오젠의 그림(라인 505)을
    # 5초 넘게 보여 줬다. 앞 심볼의 잔상과 엉키지 않게 순서를 바꿔 따로 돈다.
    for p in range(2):
        if not st['err']:
            break
        retry = [s for s in gsyms if any(e.startswith(s + ':') for e in st['err'])]
        print('  재수집 패스 %d — %s' % (p + 1, retry))
        print(' ', ev(GRAPHICS % json.dumps(retry)))
        st = wait(GPOLL, len(retry))
        gdata.update(json.loads(ev("JSON.stringify(window.__G.data)")))
    write('graphics_%s.json' % TF, json.dumps({'data': gdata}))
    if st['err']:
        # 읽은 것은 파일에 남기되 **성공으로 끝내지 않는다**. 빠진 종목은 split_graphics 가
        # 멈춰 세운다 — 조용히 '존 없음'으로 흘러가면 레벨이 통째로 사라진다(2026-09-28).
        print('실패 %d종목 — %s' % (len(st['err']), st['err']))
        print('  이 종목들만 다시 받거나(MCP data_get_pine_boxes 로 확인) 전체를 다시 돌릴 것')
        sys.exit(1)
    print('완료')

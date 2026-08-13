// TradingView 페이지 안에서 300봉을 수집·분석해 집계만 반환하는 스크립트 (컨텍스트 절약용)
//
// 배경: data_get_ohlcv 로 300봉을 받으면 종목당 ~30k 토큰이 든다.
//       TradingViewApi.activeChart().getSeries().data().bars() 로 페이지 안에서 직접 읽으면
//       26심볼 × 300봉을 ~80초에 수집하고 컨텍스트는 거의 안 쓴다.
//
// 사용법: mcp__tradingview__ui_evaluate 로 STEP1 → (80초 대기) → STEP2 → STEP3 순서로 실행.
//
// ─────────────────────────────────────────────────────────────
// STEP 1 — 전 심볼 봉 수집 (window.__B 에 적재)
// ─────────────────────────────────────────────────────────────
function STEP1(syms) {
  window.__B = { state:'run', i:0, total:syms.length, data:{}, times:null, err:[] };
  const chart = window.TradingViewApi.activeChart();
  const grab = () => {
    const bars = chart.getSeries().data().bars();
    const t=[], px=[];
    bars.each((idx,v) => { t.push(v[0]); px.push(v.slice(1,6).map(x => x==null?'':Math.round(x)).join(',')); return false; });
    return {t, px};
  };
  const step = (k) => {
    window.__B.i = k;
    if (k >= syms.length) { window.__B.state='done'; return; }
    chart.setSymbol(syms[k], () => setTimeout(() => {
      try {
        const r = grab();
        if (r.px.length < 50) window.__B.err.push(syms[k]+':short');
        if (!window.__B.times || r.t.length > window.__B.times.length) window.__B.times = r.t;
        window.__B.data[syms[k]] = r.px;
      } catch(e) { window.__B.err.push(syms[k]+':'+e.message); }
      step(k+1);
    }, 2200));
  };
  step(0);
  return 'started ' + syms.length;
}

// ─────────────────────────────────────────────────────────────
// STEP 2 — 패널 생성 (5일 간격 비중첩 표본, window.__PANEL)
//   컬럼: date,code,mkt,close,atr,atrpct,vol_ratio,ret1,ret5,ret20,
//         clsloc,rngr,streak,ma_dist,f1,f5,f20,f1x,f5x,f20x
//   f* = ATR 정규화 선행수익률, f*x = 소속 지수 대비 초과분
// ─────────────────────────────────────────────────────────────
function STEP2(kosdaqCodes) {
  const D = window.__B.data, T = window.__B.times;
  const KQ = new Set(kosdaqCodes);
  const parse = s => D[s].map(r => r.split(',').map(Number));
  const KP = parse('KRX:KOSPI').map(b => b[3]), KD = parse('KRX:KOSDAQ').map(b => b[3]);
  const dt = T.map(x => { const z = new Date(x*1000);
    return z.getUTCFullYear()*10000+(z.getUTCMonth()+1)*100+z.getUTCDate(); });
  const atr = (b,i) => { let s=0,n=0; for(let k=i-13;k<=i;k++){ if(k<1) continue;
    s += Math.max(b[k][1]-b[k][2], Math.abs(b[k][1]-b[k-1][3]), Math.abs(b[k][2]-b[k-1][3])); n++; }
    return n ? s/n : 0; };
  const out = [];
  Object.keys(D).forEach(sym => {
    const code = sym.replace('KRX:','');
    if (code === 'KOSPI' || code === 'KOSDAQ') return;
    const b = parse(sym), idx = KQ.has(code) ? KD : KP;
    for (let i = 25; i <= b.length - 21; i += 5) {
      const a = atr(b,i); if (!a) continue;
      const C=b[i][3], H=b[i][1], L=b[i][2], V=b[i][4];
      let v20=0; for (let k=i-20;k<i;k++) v20 += b[k][4]; v20 /= 20;
      let ma=0;  for (let k=i-19;k<=i;k++) ma += b[k][3]; ma /= 20;
      let st=0;  for (let k=i;k>0;k--){ const up=b[k][3]>b[k-1][3];
        if (st===0) st = up?1:-1; else if ((st>0)===up) st += up?1:-1; else break;
        if (Math.abs(st)>15) break; }
      const r  = h => (b[i+h][3]-C)/a;
      const rx = h => ((b[i+h][3]-C)/C - (idx[i+h]-idx[i])/idx[i]) * C / a;
      out.push([dt[i], code, KQ.has(code)?'Q':'P', C, Math.round(a),
        (a/C*100).toFixed(2), (V/v20).toFixed(2),
        ((C-b[i-1][3])/a).toFixed(3), ((C-b[i-5][3])/a).toFixed(3), ((C-b[i-20][3])/a).toFixed(3),
        (H>L?(C-L)/(H-L):0.5).toFixed(3), ((H-L)/a).toFixed(2), st, ((C-ma)/a).toFixed(3),
        r(1).toFixed(3), r(5).toFixed(3), r(20).toFixed(3),
        rx(1).toFixed(3), rx(5).toFixed(3), rx(20).toFixed(3)].join(','));
    }
  });
  window.__PANEL = out;
  return JSON.stringify({rows: out.length, sample: out[0]});
}

// ─────────────────────────────────────────────────────────────
// STEP 3 — 횡단면 검정 (같은 날짜 안에서 종목 간 편차만 남김)
//   이게 순수 '종목 선택' 신호다. 원자료 상관은 강세장 국면에 오염된다.
// ─────────────────────────────────────────────────────────────
function STEP3() {
  const R = window.__PANEL.map(r => r.split(','));
  const F = {atrpct:5, vol_ratio:6, ret1:7, ret5:8, ret20:9, clsloc:10, rngr:11, streak:12, ma_dist:13};
  const Y = {f1:14, f5:15, f20:16};
  const byDate = {}; R.forEach(r => (byDate[r[0]] = byDate[r[0]] || []).push(r));
  const dm = [];
  Object.values(byDate).forEach(g => {
    if (g.length < 5) return;
    const mean = {};
    [...Object.values(F), ...Object.values(Y)].forEach(i => {
      const v = g.map(r => parseFloat(r[i])).filter(isFinite);
      mean[i] = v.reduce((s,x)=>s+x,0)/v.length;
    });
    g.forEach(r => { const o={};
      [...Object.values(F), ...Object.values(Y)].forEach(i => o[i] = parseFloat(r[i]) - mean[i]);
      dm.push(o); });
  });
  const pear = (xi,yi) => {
    const p = dm.map(o=>[o[xi],o[yi]]).filter(([a,b])=>isFinite(a)&&isFinite(b));
    const n = p.length; if (n<30) return null;
    const mx=p.reduce((s,v)=>s+v[0],0)/n, my=p.reduce((s,v)=>s+v[1],0)/n;
    let sxy=0,sxx=0,syy=0;
    p.forEach(([a,b])=>{ sxy+=(a-mx)*(b-my); sxx+=(a-mx)**2; syy+=(b-my)**2; });
    return +(sxy/Math.sqrt(sxx*syy)).toFixed(3);
  };
  const out = {_n: dm.length, _dates: Object.keys(byDate).length, _se: +(2/Math.sqrt(dm.length)).toFixed(3)};
  Object.keys(F).forEach(f => { out[f]={}; Object.keys(Y).forEach(y => out[f][y]=pear(F[f],Y[y])); });
  return JSON.stringify(out);
}

// TradingView 페이지 안에서 300봉을 수집·분석해 집계만 반환하는 스크립트 (컨텍스트 절약용)
//
// 배경: data_get_ohlcv 로 300봉을 받으면 종목당 ~30k 토큰이 든다.
//       TradingViewApi.activeChart().getSeries().data().bars() 로 페이지 안에서 직접 읽으면
//       62심볼 × 300봉을 ~3분에 수집하고 컨텍스트는 거의 안 쓴다.
//
// ⚠️ 유니버스 프로토콜 (2026-08-13, 뼈아픈 경험에서 나옴)
//    검정은 반드시 아래 UNIVERSE(60종목)로 한다. 리포트 로스터(22종목)로만 검정하면
//    선택편향 때문에 없는 신호가 보인다. 실제로 24종목에서 t=2.07로 나온 20일 모멘텀이
//    60종목으로 넓히자 t=0.16으로 사라졌다. 부분집합을 바꿔 흔들리면 신호가 아니다.
//
// 사용법: mcp__tradingview__ui_evaluate 로 STEP1 → (3분 대기) → STEP2 → STEP3 순서로 실행.

// ─────────────────────────────────────────────────────────────
// 유니버스 (60종목 · 16섹터) — 리포트 로스터와 분리해서 유지할 것
// ─────────────────────────────────────────────────────────────
const SECTORS = {
  '005930':'반도체','000660':'반도체','348210':'반도체','042700':'반도체','000990':'반도체','240810':'반도체',
  '035420':'인터넷','018260':'인터넷','093320':'인터넷','035720':'인터넷',
  '251270':'게임','036570':'게임','259960':'게임',
  '402340':'지주','034730':'지주','003550':'지주',
  '017670':'통신','030200':'통신','032640':'통신',
  '105560':'금융','055550':'금융','086790':'금융','316140':'금융','138040':'금융','000810':'금융',
  '086520':'2차전지','006400':'2차전지','373220':'2차전지','247540':'2차전지',
  '456040':'화학','051910':'화학',
  '010140':'조선','009540':'조선','042660':'조선',
  '012330':'자동차','005380':'자동차','000270':'자동차',
  '237690':'제약','200670':'제약','207940':'제약','068270':'제약','128940':'제약','302440':'제약',
  '214150':'화장품','278470':'화장품','483650':'화장품','090430':'화장품','161890':'화장품',
  '289930':'방산','012450':'방산','047810':'방산','064350':'방산',
  '005490':'철강','010130':'철강',
  '267790':'소비재','097950':'소비재','271560':'소비재','352820':'소비재',
  '119850':'전력','015760':'전력'
};
const KOSDAQ = ['348210','093320','086520','214150','237690','200670','289930','267790','119850','247540','240810'];
const SYMBOLS = Object.keys(SECTORS).map(c => 'KRX:' + c).concat(['KRX:KOSPI','KRX:KOSDAQ']);

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

// ─────────────────────────────────────────────────────────────
// STEP 2b — RSI(14)·MACD(12,26,9) 를 종가에서 직접 계산해 패널에 붙인다
//
//   ⚠️ chart_manage_indicator 로 지표를 붙이는 건 이 환경에서 실패한다
//      (add 하면 new_study_count: 0). ATR 때도 같았다.
//      어차피 RSI·MACD는 종가만의 함수라 직접 계산하는 편이 낫다 —
//      차트는 한 번에 한 종목만 보여주지만 이 방식은 60종목을 한꺼번에 처리한다.
//
//   MACD는 종목별 가격 스케일이 다르므로 반드시 ATR로 정규화할 것.
//   RSI는 0~100이라 스케일 프리지만 (rsi-50)/10 으로 중심화해 쓴다.
// ─────────────────────────────────────────────────────────────
function rsi14(cl) {
  const out = new Array(cl.length).fill(null);
  let ag = 0, al = 0;
  for (let i = 1; i <= 14; i++) { const d = cl[i] - cl[i-1]; ag += Math.max(d,0); al += Math.max(-d,0); }
  ag /= 14; al /= 14;
  out[14] = al === 0 ? 100 : 100 - 100/(1 + ag/al);
  for (let i = 15; i < cl.length; i++) {
    const d = cl[i] - cl[i-1];
    ag = (ag*13 + Math.max(d,0))/14;
    al = (al*13 + Math.max(-d,0))/14;
    out[i] = al === 0 ? 100 : 100 - 100/(1 + ag/al);
  }
  return out;
}
function ema(cl, n) {
  const k = 2/(n+1), out = new Array(cl.length).fill(null);
  let s = 0; for (let i = 0; i < n; i++) s += cl[i];
  out[n-1] = s/n;
  for (let i = n; i < cl.length; i++) out[i] = cl[i]*k + out[i-1]*(1-k);
  return out;
}
function macd(cl) {                       // 12,26,9
  const e12 = ema(cl,12), e26 = ema(cl,26);
  const m = cl.map((_,i) => (e12[i]!=null && e26[i]!=null) ? e12[i]-e26[i] : null);
  const sig = ema(m.map(x => x==null?0:x), 9);
  return { macd: m, signal: sig, hist: m.map((x,i) => (x!=null && sig[i]!=null) ? x-sig[i] : null) };
}

// 검정 결과 (2026-08-13, 60종목·3,060관측·2xSE=0.036) — 전부 예측력 없음
//   rsi (50중심)    다음날 0.009 / 5일 -0.004 / 20일  0.000
//   macd/ATR        다음날 0.004 / 5일  0.000 / 20일  0.033
//   히스토그램/ATR   다음날 -0.029 / 5일 -0.029 / 20일 -0.063*
//   * 20일은 선행구간 4배 중첩이라 실질 2xSE가 ~0.072 → 미달
//   RSI 구간별 다음날 초과: <30 +0.015 / 30-45 -0.020 / 45-55 +0.005
//                          55-70 +0.019 / >=70 -0.028  (전부 노이즈 범위)

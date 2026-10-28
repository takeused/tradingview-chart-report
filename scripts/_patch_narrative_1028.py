# 2026-10-28 회차(수) 서술부를 표 값에 맞춰 갈아끼우는 패치 — 숫자는 전부 predictions.json·수집물에서 읽는다
# 10/27 패치(_patch_narrative_1027.py)에서 "이틀치/건너뛴 세션" 문장을 걷어낸 정상 회차용이다.
import json, os, shutil, statistics as st
from collections import Counter
ROOT = r'D:\01 WORK\260705 Trading View'
S = os.path.join(ROOT, 'scripts')
REP = os.path.join(ROOT, 'report')
DATE = '2026-10-28'
f = os.path.join(REP, 'stock_comparison_report_%s.html' % DATE)
t = open(f, encoding='utf-8').read()

d = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
E, P = d['entries'][-1], d['entries'][-2]
WE = d['weekly_entries'][-1]
assert E['asof'] == DATE and P['asof'] == '2026-10-27' and WE['asof'] == '2026-10-23'
ITEMS = E['items']
PC = {i['code']: i for i in P['items']}
PR, OC = P['scored']['probe'], P['scored']['open_calls']
_m = json.load(open(os.path.join(S, 'metrics_daily.json'), encoding='utf-8'))
mw = json.load(open(os.path.join(S, 'metrics_weekly.json'), encoding='utf-8'))
names = {c: n for c, n, _ in json.load(open(os.path.join(S, 'roster.json'), encoding='utf-8'))['roster']}
kp, kq = _m['KOSPI']['chg'], _m['KOSDAQ']['chg']
k14, q14 = P['index']['KOSPI'], P['index']['KOSDAQ']
assert abs((E['index']['KOSPI'] / k14 - 1) * 100 - kp) < 0.05

f2 = lambda x: '%+.2f%%' % x
fmt = lambda n: format(n, ',')
sk = lambda o: (o['brier_distance_only'] - o['brier_conditional']) / o['brier_distance_only'] * 100
cls = lambda v: 'up' if v > 0 else 'down'
win = lambda v: '앞섰' if v > 0 else '밀렸'

up = [i for i in ITEMS if i['chg'] > 0]
flat = [i for i in ITEMS if i['chg'] == 0]
down = [i for i in ITEMS if i['chg'] < 0]
bad = {b: [i['name'] for i in ITEMS if i['badge'] == b] for b in ('강세', '중립', '약세')}
volmed = st.median(i['volx'] for i in ITEMS); pvolmed = st.median(i['volx'] for i in P['items'])
over1 = sorted([i for i in ITEMS if i['volx'] > 1], key=lambda i: -i['volx'])
srt = sorted(ITEMS, key=lambda i: i['chg'])
near = [(i['name'], k, v) for i in ITEMS for k, v in i['p_touch'].items()]
nalt = sum(len(i.get('p_alt') or {}) for i in ITEMS)
nzone = sum(1 for _, _, v in near if v['src'] == 'zone')
pzone = sum(1 for i in P['items'] for v in i['p_touch'].values() if v['src'] == 'zone')
pnear = sum(len(i['p_touch']) for i in P['items'])
noalt = len(near) - nalt
zsrc = [(n, k, v) for n, k, v in near if v['src'] == 'zone']
srtp = sorted(near, key=lambda x: -x[2]['p']); ds = sorted(near, key=lambda x: x[2]['dist_sigma'])
inside, nz, nl = [], 0, 0
for i in ITEMS:
    z = json.load(open(os.path.join(S, '%s.json' % i['code']), encoding='utf-8'))
    nz += len(z['zones']); nl += len(z['lines'])
    if any(lo <= i['close'] <= hi for hi, lo in z['zones']):
        inside.append(i['name'])
nl_avg = round(nl / len(ITEMS))
rows = OC['rows']
dn_t = sum(1 for r in rows if r['dir'] == 'dn' and r['status'] == 'touched'); dn_n = sum(1 for r in rows if r['dir'] == 'dn')
up_t = sum(1 for r in rows if r['dir'] == 'up' and r['status'] == 'touched'); up_n = sum(1 for r in rows if r['dir'] == 'up')
print('up', len(up), 'flat', len(flat), 'down', len(down), 'badges', {k: len(v) for k, v in bad.items()},
      'inside', inside, 'zone', nzone, 'near', len(near), 'alt', nalt, 'closed', OC['closed'])


def sub(t, start, end, new, inclusive_end=False):
    i = t.index(start)
    j = t.index(end, i + len(start))
    if inclusive_end:
        j += len(end)
    return t[:i] + new + t[j:]


# ---- A. 오늘 시장
bigdn = [i for i in srt if i['chg'] < 0]
market = '''<h3>📊 오늘 시장</h3>
<p style="margin:0 0 8px;font-size:13px;"><b>KOSPI %(kp)s</b>(%(k14)s → %(k1)s) · <b>KOSDAQ %(kq)s</b>(%(q14)s → %(q1)s)로 10/27에 이어 이틀 연속 올랐고, 코스피는 하루에 6%%대 오른 날입니다. 진행 중인 이번 주 주봉은 월~수 사흘간 코스피 %(wkp)s입니다.</p>
<p style="margin:0 0 8px;font-size:13px;"><b>로스터는 %(nup)d종목 상승 · %(nfl)d종목 보합 · %(ndn)d종목 하락</b>입니다. 상승 폭은 <b>%(up3)s</b> 순으로 컸고, 하락한 종목은 <b>%(dn5)s</b>입니다.
배지는 <b>강세 %(nb)d(%(strong)s) · 중립 %(nn)d · 약세 %(ns)d</b>입니다. 배지는 지수를 걷어낸 초과수익이라 <b>지수가 %(kp)s·%(kq)s 오른 날에는 지수만큼 오른 종목이 중립에 머물고, 지수를 따라가지 못한 종목이 약세로 잡힙니다</b> — 오른 종목이 대부분이어도 약세 배지가 %(ns)d개인 이유입니다.
거래량 배수 중앙값은 <b>%(volmed).2f배</b>(직전 회차 %(pvolmed).2f배)이고, 1배를 넘긴 종목은 <b>%(nover)d개</b>(%(over)s)입니다.</p>
  ''' % dict(kp=f2(kp), kq=f2(kq), k14=fmt(k14), q14=fmt(q14), k1=fmt(E['index']['KOSPI']), q1=fmt(E['index']['KOSDAQ']),
             wkp=f2(mw['KOSPI']['wchg']),
             nup=len(up), nfl=len(flat), ndn=len(down),
             dn5=' · '.join('%s %s' % (i['name'], f2(i['chg'])) for i in srt[:len(down)]),
             up3=' · '.join('%s %s' % (i['name'], f2(i['chg'])) for i in srt[::-1][:3]),
             nb=len(bad['강세']), strong=' · '.join(bad['강세']), nn=len(bad['중립']), ns=len(bad['약세']),
             volmed=volmed, pvolmed=pvolmed, nover=len(over1),
             over=(' · '.join('%s %.2f배' % (i['name'], i['volx']) for i in over1[:4]) + (' 등' if len(over1) > 4 else '')) if over1 else '없음')
t = sub(t, '<h3>📊 오늘 시장</h3>', '</div>', market)

# ---- B. 지난 회차 채점 (수요일 — 일봉 한 세션, 주봉 채점 없음)
relp = ' · '.join('%s(%d건) 예측 %.1f%%→실제 %.1f%%' % (r['bin'], r['n'], r['pred'], r['actual']) for r in PR['reliability'] if not r.get('noisy'))
score = '''<div class="secsum" style="border-color:rgba(0,200,120,.45);">
    <h3>🧮 지난 회차 채점 — <span class="flip">10/27 회차를 오늘 고저로 채점했습니다</span></h3>
<p style="margin:0 0 10px;font-size:13px;">채점 대상은 "레벨을 맞혔나"가 아니라 <b>"도달 확률이 잘 보정됐나"</b>입니다. 주봉 콜은 일봉과 분리된 원장이라 <b>금요일(10/30)에만 채점</b>합니다.</p>
    <table style="margin:0 0 10px;">
      <thead><tr><th>구분</th><th>건수</th><th>조건부</th><th>비교 대상</th><th>판정</th></tr></thead>
      <tbody>
        <tr><td>일봉 도달확률 Brier — <code>p_probe</code></td><td>%(pn)d건</td><td>%(pbc).5f</td><td>거리단독 %(pbd).5f</td><td class="%(c1)s">기준선 대비 %(psk)+.2f%%</td></tr>
        <tr><td>└ 일괄이동 귀무모형과 비교</td><td>%(pn)d건</td><td>%(pbc).5f</td><td>귀무 %(pbu).5f</td><td class="%(c2)s">귀무모형 대비 %(psu)+.2f%%</td></tr>
        <tr><td>일봉 레벨 콜 원장 — 만기 종결</td><td>%(on)d건</td><td>%(obc).5f</td><td>거리단독 %(obd).5f</td><td class="%(c3)s">기준선 대비 %(osk)+.2f%%</td></tr>
        <tr><td>└ 일괄이동 귀무모형과 비교</td><td>%(on)d건</td><td>%(obc).5f</td><td>귀무 %(obu).5f</td><td class="%(c4)s">귀무모형 대비 %(osu)+.2f%%</td></tr>
        <tr><td>도달 / 미도달 (원장)</td><td>%(on)d건</td><td>도달 %(ot)d건 · 만기 미도달 %(oe)d건</td><td>실제 도달률 %(orate).1f%%</td><td>—</td></tr>
      </tbody>
    </table>
<p style="margin:0 0 10px;font-size:13px;">① <b>일봉 프로브는 기준선에 %(psk)+.2f%%로 %(pw)s고, 귀무모형에는 %(psu)+.2f%%로 %(puw)s습니다.</b> 한 회차 결과라 우위로 읽지 않습니다. 보정표는 %(relp)s입니다.</p>
<p style="margin:0 0 10px;font-size:13px;">② <b>일봉 원장은 기준선 %(osk)+.2f%% · 귀무모형 %(osu)+.2f%%로 %(ow)s습니다.</b> 종결 %(on)d건 중 <b>아래쪽 레벨은 %(dn_n)d건 중 %(dn_t)d건이 닿았고 위쪽 레벨은 %(up_n)d건 중 %(up_t)d건</b>이 닿았습니다. 같은 날·같은 시장의 관측이라 독립이 아닙니다.</p>
    <p style="margin:0;font-size:12px;color:var(--muted);">※ 원장 도달률과 프로브 도달률을 <b>나란히 비교하면 안 됩니다</b> — 원장은 종목마다 거리가 다른 차트 레벨이고 프로브는 고정거리입니다.
※ 오늘 신규로 <b>일봉 %(newc)d건</b>(가까운 쪽 %(nnear)d · 대체 %(nalt)d)을 등록해 진행 중인 콜이 <b>일봉 %(act)d건 · 주봉 %(wact)d건</b>이 됐습니다(주봉은 금요일에만 신규 등록).
※ 회차 내 관측은 서로 독립이 아닙니다(같은 날·같은 시장).</p>
  </div>''' % dict(
    pn=PR['n'], pbc=PR['brier_conditional'], pbd=PR['brier_distance_only'], psk=PR['skill_vs_baseline_pct'],
    pbu=PR['shift_null']['brier_uniform_shift'], psu=PR['skill_vs_uniform_shift_pct'],
    on=OC['closed'], obc=OC['brier_conditional'], obd=OC['brier_distance_only'], osk=sk(OC),
    obu=OC['shift_null']['brier_uniform_shift'], osu=OC['skill_vs_uniform_shift_pct'],
    ot=OC['touched'], oe=OC['expired'], orate=OC['shift_null']['actual_rate_pct'],
    c1=cls(PR['skill_vs_baseline_pct']), c2=cls(PR['skill_vs_uniform_shift_pct']), c3=cls(sk(OC)), c4=cls(OC['skill_vs_uniform_shift_pct']),
    pw=win(PR['skill_vs_baseline_pct']), puw=win(PR['skill_vs_uniform_shift_pct']),
    ow=win(min(sk(OC), OC['skill_vs_uniform_shift_pct'])),
    dn_n=dn_n, dn_t=dn_t, up_n=up_n, up_t=up_t, relp=relp,
    newc=len(near) + nalt, nnear=len(near), nalt=nalt,
    act=len(d['open_calls']['active']), wact=len(d['weekly_calls']['active']))
t = sub(t, '<div class="secsum" style="border-color:rgba(0,200,120,.45);">', '\n\n  <table>', score)

# ---- C. 표 아래 각주
note = '''<div class="note">※ 등락률은 직전 거래일(10/27) 종가 대비 <b>10/28 종가</b> 기준이며, 초과수익은 <b>β<sub>adj</sub> = 1 + 0.7 × (β<sub>120일</sub> − 1)</b>로 지수를 걷어낸 값입니다(코스피 종목은 KOSPI, 코스닥 종목은 KOSDAQ에 대고 잽니다). β는 <b>매 회차 다시</b> 계산합니다. σ·존/라인·배지·도달확률을 읽는 법은 맨 위 <a href="#howto">「표 읽는 법」</a>에 있습니다.<br>
  ※ 표에 실린 것은 <b>"가까운 쪽" %(near)d개</b>입니다. 같은 방향의 <b>다른 출처 레벨(대체 %(alt)d개)</b>도 원장에 함께 올리지만, <b>표·관전 포인트가 쓰는 값은 가까운 쪽</b>입니다. <b>레벨이 아예 없는 방향은 오늘 %(nolv)d개</b>입니다.<br>
  ※ 존은 매 회차 새로 읽습니다. 오늘 잡힌 존은 <b>%(nz)d개</b>이고, 종가가 <b>존 안</b>인 종목은 %(inside)s입니다. 대체 레벨이 없는 방향은 <b>%(noalt)d개</b>입니다.<br>
  ※ 라인도 24종목 전부 새로 읽었습니다(<b>종목당 평균 %(nl)d개</b>). 오늘 가까운 쪽 %(near)d개의 출처는 <b>라인 %(nline)d · 존 %(nzone)d</b>으로, 직전 회차(라인 %(pline)d · 존 %(pzone)d)와 비교됩니다.<br>
  ※ 다음 회차는 <b>10/29(목)</b>이고, 주봉 확률 분석은 <b>10/30(금)</b>입니다.</div>''' % dict(
    near=len(near), alt=nalt, nz=nz, noalt=noalt, nl=nl_avg, nline=len(near) - nzone, nzone=nzone,
    pline=pnear - pzone, pzone=pzone, nolv=sum(1 for i in ITEMS for k in ('up', 'dn') if k not in i['p_touch']),
    inside=('<b>%d개</b>' % len(inside)) if not inside else ' · '.join(inside))
t = sub(t, '<div class="note">※ 등락률은', '</div>', note, inclusive_end=True)

# ---- D. 섹터별 한 줄 요약 — 표에서 읽히지 않는 것만
zl = ' · '.join('%s %s %s(%.2fσ)' % (n, '위' if k == 'up' else '아래', fmt(v['level']), v['dist_sigma']) for n, k, v in zsrc)
sector = '''<h3>섹터별 한 줄 요약 (일봉)</h3>
    <p style="margin:0 0 8px;font-size:12px;color:var(--muted);">종목별 숫자는 위 표에 있습니다. 여기에는 <b>표에서 읽히지 않는 것</b>(존 출처·종가가 존 안인 종목·가까운 자리와 먼 자리)만 적습니다. 오늘은 24종목 중 %(nup)d종목이 올라 섹터별로 가를 이야기가 없습니다.</p>
<p style="margin:0 0 8px;font-size:13px;"><b>가까운 쪽이 존인 자리 %(nzone)d개</b> — %(zl)s. 직전 회차에는 %(pzone)d개였습니다.</p>
<p style="margin:0 0 8px;font-size:13px;"><b>종가가 존 안인 종목</b> — %(inside)s. 존 안에 있으면 존의 위·아래 경계가 각각 0.3σ 하한을 넘는지에 따라 레벨이 정해집니다.</p>
<p style="margin:0 0 8px;font-size:13px;"><b>약세 배지</b>는 <b>%(weak)s</b>입니다. 강세 배지는 %(nb)d종목(%(strong)s)입니다.</p>
<p style="margin:0;font-size:13px;"><b>가까운 자리와 먼 자리</b> — 가장 가까운 자리는 <b>%(nearest)s</b>이고 가장 먼 자리는 <b>%(farthest)s</b>입니다.</p></div>
''' % dict(pzone=pzone, nzone=nzone, zl=zl if zl else '없음', inside=' · '.join(inside) if inside else '없음', nup=len(up),
           nb=len(bad['강세']), strong=' · '.join(bad['강세']), weak=' · '.join(bad['약세']),
           nearest='%.3fσ(%s %s %s)' % (ds[0][2]['dist_sigma'], ds[0][0], '위' if ds[0][1] == 'up' else '아래', fmt(ds[0][2]['level'])),
           farthest='%.3fσ(%s %s %s)' % (ds[-1][2]['dist_sigma'], ds[-1][0], '위' if ds[-1][1] == 'up' else '아래', fmt(ds[-1][2]['level'])))
t = sub(t, '<h3>섹터별 한 줄 요약 (일봉)</h3>', '\n\n  <div class="secsum">\n    <h3>오늘의 시장 관전 포인트', sector)

# ---- E. 관전 포인트
top = ' · '.join('%s %s %s(%.3fσ · %s · %.1f%%)' % (n, '위' if k == 'up' else '아래', fmt(x['level']), x['dist_sigma'],
                 '라인' if x['src'] == 'line' else '존', x['p']) for n, k, x in srtp[:3])
watch = '''<h3>오늘의 시장 관전 포인트</h3>
<p style="margin:0 0 10px;font-size:13px;"><b>지수가 하루에 코스피 %(kp)s·코스닥 %(kq)s 오른 날, 로스터 24종목 중 %(nup)d종목이 올랐고 내린 종목은 %(ndn)d개였습니다.</b> 배지는 강세 %(nb)d · 중립 %(nn)d · 약세 %(ns)d입니다 — 지수가 크게 오른 날 배지는 <b>지수 대비 얼마나 더 올랐는가</b>를 보여 줍니다.</p>
<p style="margin:0 0 10px;font-size:13px;"><b>방향 확률은 0.5로 둡니다.</b> 급등 다음 날의 방향은 이 리포트가 검정으로 확인한 신호가 아닙니다. 다음 회차 채점이 보는 것은 방향이 아니라 <b>레벨 도달 확률이 보정됐는가</b>입니다. 변동성이 커진 날 뒤라 ATR 기준 σ가 평소보다 넓게 잡힌 점을 감안해 읽으십시오.</p>
<p style="margin:0;font-size:13px;">가까운 쪽 %(near)d개의 출처는 <b>라인 %(nline)d · 존 %(nzone)d</b>이고, 확률 상위는 <b>%(top)s</b>입니다. 가장 가까운 자리는 <b>%(nearest)s</b>이고 가장 먼 자리는 <b>%(farthest)s</b>입니다. 확률이 높은 자리는 방향을 맞힌 것이 아니라 가까운 거리의 확률이 구조적으로 높게 나오는 것입니다.</p>
  ''' % dict(kp=f2(kp), kq=f2(kq), ndn=len(down), nup=len(up), nn=len(bad['중립']), ns=len(bad['약세']), nb=len(bad['강세']),
             near=len(near), nline=len(near) - nzone, nzone=nzone, top=top,
             nearest='%.3fσ(%s %s %s)' % (ds[0][2]['dist_sigma'], ds[0][0], '위' if ds[0][1] == 'up' else '아래', fmt(ds[0][2]['level'])),
             farthest='%.3fσ(%s %s %s)' % (ds[-1][2]['dist_sigma'], ds[-1][0], '위' if ds[-1][1] == 'up' else '아래', fmt(ds[-1][2]['level'])))
t = sub(t, '<h3>오늘의 시장 관전 포인트</h3>', '</div>', watch)

# ---- F. 주봉 서술 머리말 (수요일: 진행 중인 봉, 사흘치)
rowsw = [(cd, v) for cd, v in mw.items() if cd in names]
pos = sum(1 for cd, v in rowsw if v['wchg'] > 0)
top12p = sorted(rowsw, key=lambda x: -x[1]['pos12'])
tm12 = sorted(rowsw, key=lambda x: -x[1]['m12'])
tatr = sorted(rowsw, key=lambda x: -x[1]['watrpct'])
wk = '''<div class="wkhead"></div>
  <div class="toolbar" style="margin-bottom:12px;">
    <div class="tfbadge wk">주봉</div>
    <span class="note" style="margin:0;">진행 중인 주봉(10/26 시작 주)의 <b>사흘치</b> — 아래 서술 표는 이 주, 도달확률 표는 10/23(금) 회차 기준입니다</span>
  </div>
  <div class="secsum" style="border-color:rgba(120,200,255,.45);">
    <h3>📆 주봉으로 보면 — <span class="flip">이번 주 봉은 아직 사흘치입니다</span></h3>
<p style="margin:0 0 10px;font-size:13px;"><b>이번 주(10/26~)는 월~수 사흘만 거래된 봉</b>이고 사흘 동안 코스피 %(wk_kp)s·코스닥 %(wk_kq)s입니다. 아래 서술 표의 "주간 등락"·연속 주·12주 위치·모멘텀은 모두 이 사흘치가 얹힌 값입니다. <b>주봉 도달확률 표는 10/23(금) 회차 기준으로 그대로 둡니다</b> — 다음 주봉 분석과 채점은 <b>10/30(금)</b>입니다.</p>
<p style="margin:0;font-size:13px;">진행 중인 봉으로 <b>24종목 중 %(pos)d종목이 플러스</b>입니다. 12주 위치는 <b>%(p12u)s</b>가 상단권, <b>%(p12d)s</b>가 하단권입니다. 12주 모멘텀은 <b>%(mu)s</b>가 상위, <b>%(md)s</b>가 하위입니다. 주간 ATR%%가 가장 큰 종목은 <b>%(atr)s</b>입니다 — 같은 1σ라도 종목마다 폭이 이만큼 다릅니다.</p></div>
''' % dict(wk_kp=f2(mw['KOSPI']['wchg']), wk_kq=f2(mw['KOSDAQ']['wchg']), pos=pos,
           p12u=' · '.join('%s %d%%' % (names[cd], v['pos12']) for cd, v in top12p[:4]),
           p12d=' · '.join('%s %d%%' % (names[cd], v['pos12']) for cd, v in top12p[::-1][:4]),
           mu=' · '.join('%s %+.1f%%' % (names[cd], v['m12']) for cd, v in tm12[:3]),
           md=' · '.join('%s %+.1f%%' % (names[cd], v['m12']) for cd, v in tm12[::-1][:4]),
           atr=' · '.join('%s %.1f%%' % (names[cd], v['watrpct']) for cd, v in tatr[:3]))
t = sub(t, '<div class="wkhead"></div>', '\n  <table>', wk)

# ---- G. 주봉 도달확률 안내 박스 — 10/27 것과 동일(금요일 기준 표 유지), 이미 템플릿에 있다
assert '10/23(금) 종가 기준' in t

for stale in ('오늘 종가로 완성된 봉', '닷새가 모두 열린 주', '10/23 세션', '이틀치', '10/26(월) 회차', '10/27 세션', '10/27(화)'):
    assert stale not in t, stale
open(f, 'w', encoding='utf-8').write(t)
for n in ('index.html', 'stock_comparison_report.html'):
    shutil.copyfile(f, os.path.join(REP, n))
print('patched', len(t))

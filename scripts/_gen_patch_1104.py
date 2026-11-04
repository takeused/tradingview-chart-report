# 10/28 회차(수) 서술 패치를 11/4 회차(수, 11/2·11/3 건너뜀)용으로 바꿔 _patch_narrative_1104.py 를 만드는 일회성 생성기
import os
S = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(S, '_patch_narrative_1028.py'), encoding='utf-8').read()


def rep(a, b):
    global src
    assert src.count(a) >= 1, a[:70]
    src = src.replace(a, b, 1)


rep("# 2026-10-28 회차(수) 서술부를 표 값에 맞춰 갈아끼우는 패치 — 숫자는 전부 predictions.json·수집물에서 읽는다\n# 10/27 패치(_patch_narrative_1027.py)에서 \"이틀치/건너뛴 세션\" 문장을 걷어낸 정상 회차용이다.",
    "# 2026-11-04 회차(수, 11/2·11/3 을 건너뜀) 서술부를 표 값에 맞춰 갈아끼우는 패치 — 숫자는 전부 predictions.json·수집물에서 읽는다")
rep("DATE = '2026-10-28'", "DATE = '2026-11-04'")
rep("WE = d['weekly_entries'][-1]\nassert E['asof'] == DATE and P['asof'] == '2026-10-27' and WE['asof'] == '2026-10-23'",
    "WE = d['weekly_entries'][-1]\nassert E['asof'] == DATE and P['asof'] == '2026-10-30' and WE['asof'] == '2026-10-30'")
rep("PR, OC = P['scored']['probe'], P['scored']['open_calls']",
    "PR, OC = P['scored']['probe'], P['scored']['open_calls']\n"
    "EX3, EX4 = P['scored']['open_calls_extra_sessions']\n"
    "assert (EX3['session'], EX4['session']) == ('2026-11-03', '2026-11-04')\n"
    "bars = json.load(open(os.path.join(S, 'bars_daily.json')))")
rep("k14, q14 = P['index']['KOSPI'], P['index']['KOSDAQ']\nassert abs((E['index']['KOSPI'] / k14 - 1) * 100 - kp) < 0.05",
    "k30, q30 = P['index']['KOSPI'], P['index']['KOSDAQ']\n"
    "k2, q2 = round(bars['KOSPI'][-3][1]), round(bars['KOSDAQ'][-3][1])\n"
    "k3, q3 = round(bars['KOSPI'][-2][1]), round(bars['KOSDAQ'][-2][1])\n"
    "assert E['index']['KOSPI'] == round(bars['KOSPI'][-1][1]) and abs((E['index']['KOSPI'] / k3 - 1) * 100 - kp) < 0.05\n"
    "pc = lambda a, b: (b / a - 1) * 100")
rep("print('up', len(up)",
    "NAMES_P = {i['code']: i['name'] for i in P['items']}\n"
    "DROP = [c for c in PC if c not in {i['code'] for i in ITEMS}]\n"
    "assert sorted(DROP) == ['035420', '086520'] and len(ITEMS) == 24\n"
    "drop_ret = {NAMES_P[c]: pc(bars[c][-4][1], bars[c][-1][1]) for c in DROP}\n"
    "assert abs(bars['KOSPI'][-4][1] - k30) < 1\n"
    "two_dn = sum(1 for i in ITEMS if i['close'] < PC[i['code']]['close'])\n"
    "print('up', len(up)")

# A. 시장
a0 = src.index("market = '''")
a1 = src.index("t = sub(t, '<h3>📊 오늘 시장</h3>'")
market_new = """market = '''<h3>📊 오늘 시장</h3>
<p style="margin:0 0 8px;font-size:13px;"><b>표는 하루치(11/4), 지수는 사흘치입니다.</b> 11/2(월)·11/3(화) 회차를 만들지 않아 그 두 세션은 채점에만 반영했습니다. 10/30 종가 기준 <b>코스피 %(k30)s → %(k2)s(11/2 %(p2)s) → %(k3)s(11/3 %(p3)s) → %(k1)s(오늘 %(kp)s)</b>, <b>코스닥 %(q30)s → %(q2)s(11/2 %(r2)s) → %(q3)s(11/3 %(r3)s) → %(q1)s(오늘 %(kq)s)</b>입니다. 사흘을 합치면 코스피 %(kt)s · 코스닥 %(qt)s입니다. 진행 중인 이번 주 주봉은 월~수 사흘간 <b>코스피 %(wkp)s · 코스닥 %(wkq)s</b>입니다.</p>
<p style="margin:0 0 8px;font-size:13px;"><b>로스터는 %(nup)d종목 상승 · %(nfl)d종목 보합 · %(ndn)d종목 하락</b>입니다. 상승 폭은 <b>%(up3)s</b> 순으로 컸고, 하락한 종목은 <b>%(dn5)s</b>입니다. 10/30 종가 대비 사흘치로 보면 <b>%(ntd)d종목이 마이너스</b>입니다.
배지는 <b>강세 %(nb)d(%(strong)s) · 중립 %(nn)d · 약세 %(ns)d</b>입니다. 배지는 지수를 걷어낸 초과수익이라 <b>지수를 따라가지 못한 종목은 약세로 잡히고, 지수만큼 움직인 종목은 중립에 머뭅니다</b>.
거래량 배수 중앙값은 <b>%(volmed).2f배</b>(직전 회차 %(pvolmed).2f배)이고, 1배를 넘긴 종목은 <b>%(nover)d개</b>(%(over)s)입니다.</p>
  ''' % dict(kp=f2(kp), kq=f2(kq), k30=fmt(k30), q30=fmt(q30), k2=fmt(k2), q2=fmt(q2), k3=fmt(k3), q3=fmt(q3),
             k1=fmt(E['index']['KOSPI']), q1=fmt(E['index']['KOSDAQ']),
             p2=f2(pc(k30, k2)), p3=f2(pc(k2, k3)), r2=f2(pc(q30, q2)), r3=f2(pc(q2, q3)),
             kt=f2(pc(k30, E['index']['KOSPI'])), qt=f2(pc(q30, E['index']['KOSDAQ'])),
             wkp=f2(mw['KOSPI']['wchg']), wkq=f2(mw['KOSDAQ']['wchg']), ntd=two_dn,
             nup=len(up), nfl=len(flat), ndn=len(down),
             dn5=' · '.join('%s %s' % (i['name'], f2(i['chg'])) for i in srt[:min(len(down), 5)]),
             up3=' · '.join('%s %s' % (i['name'], f2(i['chg'])) for i in srt[::-1][:3]),
             nb=len(bad['강세']), strong=' · '.join(bad['강세']), nn=len(bad['중립']), ns=len(bad['약세']),
             volmed=volmed, pvolmed=pvolmed, nover=len(over1),
             over=(' · '.join('%s %.2f배' % (i['name'], i['volx']) for i in over1[:4]) + (' 등' if len(over1) > 4 else '')) if over1 else '없음')
"""
src = src[:a0] + market_new + src[a1:]

# 로스터 변경 박스 — 시장 요약 치환 직후에 직전 회차의 편입 박스를 갈아끼운다
rep("t = sub(t, '<h3>📊 오늘 시장</h3>', '</div>', market)\n", """t = sub(t, '<h3>📊 오늘 시장</h3>', '</div>', market)
notice = '''<div class="secsum" style="border-color:rgba(255,180,60,.5);">
    <h3>📌 로스터 변경 — <span class="flip">NAVER·에코프로 2종목을 제외하고 24종목으로 줄였습니다</span></h3>
    <p style="margin:0;font-size:13px;">사용자 요청으로 <b>NAVER · 에코프로</b>를 10/30 증설 직후 제외했고, 11/2·11/3 회차를 만들지 않아 오늘 회차부터 적용됐습니다. 두 종목의 10/30 종가 대비 오늘까지 등락은 <b>%(dr)s</b>입니다. 제외는 성과를 보고 고른 것이 아니라 사용자 요청이지만, 빠진 종목의 이후 성과가 표에서 사라지므로 <b>건수는 직전 회차와 비교하지 않고 비율로만 비교</b>합니다. 두 종목의 10/30 일봉·주봉 콜은 채점에 그대로 포함했습니다(선택편향 방지).</p>
  </div>
  ''' % dict(dr=' · '.join('%s %s' % (n, f2(v)) for n, v in drop_ret.items()))
j0 = t.rindex('<div', 0, t.index('📌 로스터 변경 —'))
j1 = t.index('</div>', j0) + len('</div>')
t = t[:j0] + notice.rstrip() + t[j1:]
""")

# B. 채점
b0 = src.index("score = '''")
b1 = src.index("t = sub(t, '<div class=\"secsum\" style=\"border-color:rgba(0,200,120,.45);\">'")
score_new = """score = '''<div class="secsum" style="border-color:rgba(0,200,120,.45);">
    <h3>🧮 지난 회차 채점 — <span class="flip">10/30 회차를 11/2 고저로 채점하고 원장은 두 세션 더 진행시켰습니다</span></h3>
<p style="margin:0 0 10px;font-size:13px;">채점 대상은 "레벨을 맞혔나"가 아니라 <b>"도달 확률이 잘 보정됐나"</b>입니다. 10/30 회차는 예고한 세션인 <b>11/2의 고가·저가</b>로 정식 채점하고, 건너뛴 11/3·11/4 세션은 원장만 한 칸씩 더 진행시켜 따로 적었습니다(오늘 고저로만 채점하면 11/2에 닿은 콜이 미도달로 잘못 기록됩니다). 주봉 콜은 일봉과 분리된 원장이라 <b>금요일(11/6)에만 채점</b>합니다.</p>
    <table style="margin:0 0 10px;">
      <thead><tr><th>구분</th><th>건수</th><th>조건부</th><th>비교 대상</th><th>판정</th></tr></thead>
      <tbody>
        <tr><td>일봉 도달확률 Brier — <code>p_probe</code> (11/2 세션)</td><td>%(pn)d건</td><td>%(pbc).5f</td><td>거리단독 %(pbd).5f</td><td class="%(c1)s">기준선 대비 %(psk)+.2f%%</td></tr>
        <tr><td>└ 일괄이동 귀무모형과 비교</td><td>%(pn)d건</td><td>%(pbc).5f</td><td>귀무 %(pbu).5f</td><td class="%(c2)s">귀무모형 대비 %(psu)+.2f%%</td></tr>
        <tr><td>일봉 레벨 콜 원장 — 11/2 세션 만기 종결</td><td>%(on)d건</td><td>%(obc).5f</td><td>거리단독 %(obd).5f</td><td class="%(c3)s">기준선 대비 %(osk)+.2f%%</td></tr>
        <tr><td>└ 일괄이동 귀무모형과 비교</td><td>%(on)d건</td><td>%(obc).5f</td><td>귀무 %(obu).5f</td><td class="%(c4)s">귀무모형 대비 %(osu)+.2f%%</td></tr>
        <tr><td>도달 / 미도달 (11/2 세션 원장)</td><td>%(on)d건</td><td>도달 %(ot)d건 · 만기 미도달 %(oe)d건</td><td>실제 도달률 %(orate).1f%%</td><td>—</td></tr>
        <tr><td>일봉 레벨 콜 원장 — 11/3 세션 만기 종결</td><td>%(x3n)d건</td><td>%(x3bc).5f</td><td>거리단독 %(x3bd).5f</td><td class="%(c5)s">기준선 대비 %(x3sk)+.2f%%</td></tr>
        <tr><td>└ 일괄이동 귀무모형과 비교</td><td>%(x3n)d건</td><td>%(x3bc).5f</td><td>귀무 %(x3bu).5f</td><td class="%(c6)s">귀무모형 대비 %(x3su)+.2f%%</td></tr>
        <tr><td>일봉 레벨 콜 원장 — 11/4 세션 만기 종결</td><td>%(x4n)d건</td><td>%(x4bc).5f</td><td>거리단독 %(x4bd).5f</td><td class="%(c7)s">기준선 대비 %(x4sk)+.2f%%</td></tr>
        <tr><td>└ 일괄이동 귀무모형과 비교</td><td>%(x4n)d건</td><td>%(x4bc).5f</td><td>귀무 %(x4bu).5f</td><td class="%(c8)s">귀무모형 대비 %(x4su)+.2f%%</td></tr>
      </tbody>
    </table>
<p style="margin:0 0 10px;font-size:13px;">① <b>일봉 프로브는 기준선을 %(psk)+.2f%%로 %(pw)s고, 귀무모형은 %(psu)+.2f%%로 %(puw)s습니다.</b> 한 회차 결과라 결론을 내리지 않습니다. 보정표는 %(relp)s입니다.</p>
<p style="margin:0 0 10px;font-size:13px;">② <b>일봉 원장(11/2 세션)은 기준선을 %(osk)+.2f%%로, 귀무모형은 %(osu)+.2f%%로 %(ow)s습니다.</b> 종결 %(on)d건 중 도달 %(ot)d건이며, <b>아래쪽 레벨은 %(dn_n)d건 중 %(dn_t)d건이 닿았고 위쪽 레벨은 %(up_n)d건 중 %(up_t)d건</b>이 닿았습니다. 같은 날·같은 시장의 관측이라 독립이 아닙니다. 11/3 세션은 %(x3n)d건(도달 %(x3t)d), 11/4 세션은 %(x4n)d건(도달 %(x4t)d)이 닫혀 <b>10/30 이전에 열린 일봉 콜은 모두 종결</b>됐고, 두 세션은 건수가 적어 참고로만 봅니다.</p>
    <p style="margin:0;font-size:12px;color:var(--muted);">※ 원장 도달률과 프로브 도달률을 <b>나란히 비교하면 안 됩니다</b> — 원장은 종목마다 거리가 다른 차트 레벨이고 프로브는 고정거리입니다.
※ 오늘 신규로 <b>일봉 %(newc)d건</b>(가까운 쪽 %(nnear)d · 대체 %(nalt)d)을 등록해 진행 중인 콜이 <b>일봉 %(act)d건 · 주봉 %(wact)d건</b>이 됐습니다(주봉은 금요일에만 신규 등록).
※ 회차 내 관측은 서로 독립이 아닙니다(같은 날·같은 시장).</p>
  </div>''' % dict(
    pn=PR['n'], pbc=PR['brier_conditional'], pbd=PR['brier_distance_only'], psk=PR['skill_vs_baseline_pct'],
    pbu=PR['shift_null']['brier_uniform_shift'], psu=PR['skill_vs_uniform_shift_pct'],
    on=OC['closed'], obc=OC['brier_conditional'], obd=OC['brier_distance_only'], osk=sk(OC),
    obu=OC['shift_null']['brier_uniform_shift'], osu=OC['skill_vs_uniform_shift_pct'],
    ot=OC['touched'], oe=OC['expired'], orate=OC['shift_null']['actual_rate_pct'],
    x3n=EX3['closed'], x3bc=EX3['brier_conditional'], x3bd=EX3['brier_distance_only'], x3sk=sk(EX3),
    x3bu=EX3['shift_null']['brier_uniform_shift'], x3su=EX3['skill_vs_uniform_shift_pct'], x3t=EX3['touched'],
    x4n=EX4['closed'], x4bc=EX4['brier_conditional'], x4bd=EX4['brier_distance_only'], x4sk=sk(EX4),
    x4bu=EX4['shift_null']['brier_uniform_shift'], x4su=EX4['skill_vs_uniform_shift_pct'], x4t=EX4['touched'],
    c1=cls(PR['skill_vs_baseline_pct']), c2=cls(PR['skill_vs_uniform_shift_pct']), c3=cls(sk(OC)), c4=cls(OC['skill_vs_uniform_shift_pct']),
    c5=cls(sk(EX3)), c6=cls(EX3['skill_vs_uniform_shift_pct']), c7=cls(sk(EX4)), c8=cls(EX4['skill_vs_uniform_shift_pct']),
    pw=win(PR['skill_vs_baseline_pct']), puw=win(PR['skill_vs_uniform_shift_pct']),
    ow=win(min(sk(OC), OC['skill_vs_uniform_shift_pct'])),
    dn_n=dn_n, dn_t=dn_t, up_n=up_n, up_t=up_t, relp=relp,
    newc=len(near) + nalt, nnear=len(near), nalt=nalt,
    act=len(d['open_calls']['active']), wact=len(d['weekly_calls']['active']))
"""
src = src[:b0] + score_new + src[b1:]

# C. 각주
rep("※ 등락률은 직전 거래일(10/27) 종가 대비 <b>10/28 종가</b> 기준", "※ 등락률은 직전 거래일(11/3) 종가 대비 <b>11/4 종가</b> 기준")
rep("※ 다음 회차는 <b>10/29(목)</b>이고, 주봉 확률 분석은 <b>10/30(금)</b>입니다.",
    "※ 11/2(월)·11/3(화) 회차는 만들지 않았습니다. 표의 등락은 하루치이고 지수 수치는 사흘치를 반영합니다. 다음 회차는 <b>11/5(목)</b>이고, 주봉 확률 분석은 <b>11/6(금)</b>입니다.")
# D. 섹터
rep("오늘은 24종목 중 %(nup)d종목이 올라 섹터별로 가를 이야기가 없습니다.",
    "오늘은 24종목 중 %(nup)d종목이 올랐고 %(ndn)d종목이 내려 섹터별로 가를 이야기가 없습니다.")
rep("zl=zl if zl else '없음', inside=", "zl=zl if zl else '없음', ndn=len(down), inside=")

# E. 관전 포인트
e0 = src.index("watch = '''")
e1 = src.index("t = sub(t, '<h3>오늘의 시장 관전 포인트</h3>'")
watch_new = """watch = '''<h3>오늘의 시장 관전 포인트</h3>
<p style="margin:0 0 10px;font-size:13px;"><b>오늘 코스피 %(kp)s·코스닥 %(kq)s로, 로스터 24종목 중 %(nup)d종목이 올랐고 %(ndn)d종목이 내렸습니다.</b> 배지는 강세 %(nb)d · 중립 %(nn)d · 약세 %(ns)d입니다 — 배지는 상승 종목 수가 아니라 <b>지수 대비 얼마나 달랐는가</b>를 보여 줍니다.</p>
<p style="margin:0 0 10px;font-size:13px;"><b>방향 확률은 0.5로 둡니다.</b> 다음 날 방향은 이 리포트가 검정으로 확인한 신호가 아닙니다. 다음 회차 채점이 보는 것은 방향이 아니라 <b>레벨 도달 확률이 보정됐는가</b>입니다. 최근 변동성이 매우 커서 지수의 주간 ATR%%가 %(watr)s%%에 이릅니다 — 주봉 σ와 일봉 σ를 섞어 읽지 마십시오.</p>
<p style="margin:0;font-size:13px;">가까운 쪽 %(near)d개의 출처는 <b>라인 %(nline)d · 존 %(nzone)d</b>이고, 확률 상위는 <b>%(top)s</b>입니다. 가장 가까운 자리는 <b>%(nearest)s</b>이고 가장 먼 자리는 <b>%(farthest)s</b>입니다. 확률이 높은 자리는 방향을 맞힌 것이 아니라 가까운 거리의 확률이 구조적으로 높게 나오는 것입니다.</p>
  ''' % dict(kp=f2(kp), kq=f2(kq), ndn=len(down), nup=len(up), nn=len(bad['중립']), ns=len(bad['약세']), nb=len(bad['강세']),
             watr=mw['KOSPI']['watrpct'],
             near=len(near), nline=len(near) - nzone, nzone=nzone, top=top,
             nearest='%.3fσ(%s %s %s)' % (ds[0][2]['dist_sigma'], ds[0][0], '위' if ds[0][1] == 'up' else '아래', fmt(ds[0][2]['level'])),
             farthest='%.3fσ(%s %s %s)' % (ds[-1][2]['dist_sigma'], ds[-1][0], '위' if ds[-1][1] == 'up' else '아래', fmt(ds[-1][2]['level'])))
"""
src = src[:e0] + watch_new + src[e1:]

# F. 주봉 서술 머리말
rep("진행 중인 주봉(10/26 시작 주)의 <b>사흘치</b> — 아래 서술 표는 이 주, 도달확률 표는 10/23(금) 회차 기준입니다",
    "진행 중인 주봉(11/2 시작 주)의 <b>사흘치</b> — 아래 서술 표는 이 주, 도달확률 표는 10/30(금) 회차 기준입니다")
rep("<b>이번 주(10/26~)는 월~수 사흘만 거래된 봉</b>", "<b>이번 주(11/2~)는 월~수 사흘만 거래된 봉</b>")
rep("<b>주봉 도달확률 표는 10/23(금) 회차 기준으로 그대로 둡니다</b> — 다음 주봉 분석과 채점은 <b>10/30(금)</b>입니다.",
    "<b>주봉 도달확률 표는 10/30(금) 회차 기준으로 그대로 둡니다</b> — 다음 주봉 분석과 채점은 <b>11/6(금)</b>입니다.")

# G. 주봉 확률 안내 박스
g0 = src.index("# ---- G.")
g1 = src.index("for stale in")
g_new = """# ---- G. 주봉 도달확률 안내 박스 — 수요일: 10/30(금) 표를 그대로 쓴다
g_old_h = '<h3>📌 주봉 도달확률 — <span class="flip">10/30(금) 종가 기준으로 갱신했습니다</span></h3>'
assert g_old_h in t
gi = t.rindex('<div class="secsum"', 0, t.index(g_old_h))
gj = t.index('</div>', gi) + len('</div>')
box = '''<div class="secsum" style="border-color:rgba(255,180,60,.5);">
    <h3>📌 주봉 도달확률 — <span class="flip">10/30(금) 종가 기준 표를 그대로 씁니다</span></h3>
    <p style="margin:0;">아래 주봉 레벨·확률 표는 <b>2026-10-30(금) 종가 기준</b>이고 오늘 갱신하지 않았습니다. <b>주봉은 금요일에만 분석합니다</b> — 주봉이 완성된 봉이 되는 시점이 금요일 종가이고, 주봉 확률표가 <b>완성된 봉으로 보정</b>돼 있기 때문입니다. 진행 중인 봉으로 확률을 내면 <b>자를 바꿔 놓고 표를 그대로 쓰는</b> 꼴이 됩니다.</p>
    <p style="margin:12px 0 0;">10/30에 연 주봉 콜 <b>41건</b>은 일봉과 분리된 원장(weekly_calls)에서 <b>주 단위로</b> 만기를 세며, 이번 주 봉이 완성되는 <b>11/6(금)</b>에 채점됩니다. 이 표에는 오늘 로스터에서 빠진 <b>NAVER·에코프로</b>가 남아 있습니다 — 두 종목의 주봉 콜이 열려 있어 채점까지 지우지 않습니다.</p>
  </div>'''
t = t[:gi] + box + t[gj:]

"""
src = src[:g0] + g_new + src[g1:]
rep("for stale in ('오늘 종가로 완성된 봉', '닷새가 모두 열린 주', '10/23 세션', '이틀치', '10/26(월) 회차', '10/27 세션', '10/27(화)'):",
    "for stale in ('오늘 종가로 완성된 봉', '닷새가 모두 열린 주', '신세계·루닛 2종목을', '표는 하루치(10/30)', '이번 주(10/26', '10/29(목)'):")
open(os.path.join(S, '_patch_narrative_1104.py'), 'w', encoding='utf-8').write(src)
print('generated', len(src))

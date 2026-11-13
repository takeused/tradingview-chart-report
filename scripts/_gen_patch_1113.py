# 11/6 회차(금, 11/5 건너뜀) 서술 패치를 11/13 회차(금, 11/9~11/12 나흘 건너뜀)용으로 바꿔 _patch_narrative_1113.py 를 만드는 일회성 생성기
import os
S = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(S, '_patch_narrative_1106.py'), encoding='utf-8').read()

# 날짜 치환 — 모두 동시에(자리표시자 경유). 긴 것부터.
PAIRS = [("2026-11-06", "2026-11-13"), ("2026-11-04", "2026-11-06"), ("2026-10-30", "2026-11-06"),
         ("11/13", "11/20"), ("11/9(월)", "11/16(월)"), ("11/6", "11/13"), ("11/5", "11/9"), ("11/4", "11/6"),
         ("11/2", "11/9"), ("10/30", "11/6"), ("10/26", "11/2")]


def M(s):
    for k, (a, b) in enumerate(PAIRS):
        s = s.replace(a, '\x00%d\x00' % k)
    for k, (a, b) in enumerate(PAIRS):
        s = s.replace('\x00%d\x00' % k, b)
    return s


src = M(src)


def rep(a, b, count=1):
    """a 는 1106 판 원문 — 치환 규칙을 적용해 찾고, b 는 새 문장 그대로 넣는다."""
    global src
    a = M(a)
    assert src.count(a) >= 1, a[:80]
    src = src.replace(a, b, count)


# 1) 전제
rep("EX = P['scored']['open_calls_extra_sessions'][0]\nassert EX['session'] == DATE",
    "EXS = P['scored']['open_calls_extra_sessions']\n"
    "assert [x['session'] for x in EXS] == ['2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13']\n"
    "EX, EY = EXS[0], EXS[1]\nassert EXS[2]['closed'] == 0 and EXS[3]['closed'] == 0")
rep("kp29, kq29 = (k29 / k22 - 1) * 100, (q29 / q22 - 1) * 100",
    "kp29, kq29 = (k29 / k22 - 1) * 100, (q29 / q22 - 1) * 100\n"
    "Kc = [round(bars['KOSPI'][-k][1]) for k in (5, 4, 3, 2)]\n"
    "Qc = [round(bars['KOSDAQ'][-k][1]) for k in (5, 4, 3, 2)]\n"
    "assert Kc[-1] == k29 and Qc[-1] == q29\n"
    "kp9, kq9 = (Kc[0] / k22 - 1) * 100, (Qc[0] / q22 - 1) * 100\n"
    "kpath = ' → '.join(format(x, ',') for x in [k22] + Kc + [E['index']['KOSPI']])\n"
    "qpath = ' → '.join(format(x, ',') for x in [q22] + Qc + [E['index']['KOSDAQ']])\n"
    "assert kp < 0 < kq")
rep("assert (len(up), len(flat), len(down)) == (2, 0, 22) and len(ITEMS) == 24\nassert wcalls == 40 and len(near) + nalt == 73",
    "assert (len(up), len(flat), len(down)) == (12, 0, 12) and len(ITEMS) == 24\nassert wcalls == 42 and len(near) + nalt == 69")

# 2) 시장 요약 첫 문단
a0 = src.index('<p style="margin:0 0 8px;font-size:13px;"><b>표는 하루치')
a1 = src.index('</p>', a0) + 4
src = src[:a0] + ('<p style="margin:0 0 8px;font-size:13px;"><b>표는 하루치(11/13), 지수는 한 주치입니다.</b> 11/9(월)~11/12(목) 회차를 만들지 않아 그 나흘은 채점에만 반영했습니다. '
                  '지수는 <b>코스피 %(kpath)s · 코스닥 %(qpath)s</b>로 움직였습니다(11/9 코스피 %(kp9)s · 코스닥 %(kq9)s). '
                  '오늘은 <b>KOSPI %(kp)s</b> · <b>KOSDAQ %(kq)s</b>이고, 이번 주(11/9~11/13) 주간 등락은 <b>코스피 %(wkp)s · 코스닥 %(wkq)s</b>입니다.</p>') + src[a1:]
rep("% dict(kp=f2(kp), kq=f2(kq), kp29=f2(kp29),",
    "% dict(kpath=kpath, qpath=qpath, kp9=f2(kp9), kq9=f2(kq9), kp=f2(kp), kq=f2(kq), kp29=f2(kp29),")
rep("종가 대비 이틀치로 보면", "종가 대비 한 주치로 보면")
rep("배지는 지수를 걷어낸 초과수익이라 <b>지수가 %(kp)s·%(kq)s 내린 날에는 지수만큼 내린 종목이 중립에 머물고, 지수보다 덜 내리거나 오른 종목이 강세로 잡힙니다</b>.",
    "배지는 지수를 걷어낸 초과수익이라 <b>지수와 같이 움직인 종목은 중립에 머뭅니다</b>(오늘 코스피 %(kp)s · 코스닥 %(kq)s).")

# 3) 채점 박스
rep("건너뛴 11/6 세션은 원장만 한 칸 더 진행시켜 따로 적었습니다", "건너뛴 11/10~11/13 세션은 원장만 한 칸씩 더 진행시켜 따로 적었습니다")
rep("아직 만기가 안 된 일봉 콜은 %(still)d건 남았습니다. 11/6 세션은 %(xn)d건뿐이라 기준선 %(xsk)+.2f%% · 귀무모형 %(xsu)+.2f%%를 참고로만 봅니다.",
    "11/9 세션을 마치고 만기 전이던 일봉 콜 %(still)d건은 11/10 세션 %(xn)d건(기준선 %(xsk)+.2f%% · 귀무모형 %(xsu)+.2f%%)과 11/11 세션 %(yn)d건(기준선 %(ysk)+.2f%% · 귀무모형 %(ysu)+.2f%%)으로 모두 종결됐고, 11/12·11/13 세션에는 열린 콜이 없었습니다. 이 둘은 참고로만 봅니다.")

src = src.replace("11/13 세션", "11/10 세션")          # 연장 세션 표 행 라벨(11/6 세션 → 11/10 세션)
rep("        <tr><td><b>주봉</b> 도달확률 Brier",
    "        <tr><td>일봉 레벨 콜 원장 — 11/11 세션 만기 종결</td><td>%(yn)d건</td><td>%(ybc).5f</td><td>거리단독 %(ybd).5f</td><td class=\"%(c11)s\">기준선 대비 %(ysk)+.2f%%</td></tr>\n"
    "        <tr><td>└ 일괄이동 귀무모형과 비교</td><td>%(yn)d건</td><td>%(ybc).5f</td><td>귀무 %(ybu).5f</td><td class=\"%(c12)s\">귀무모형 대비 %(ysu)+.2f%%</td></tr>\n"
    "        <tr><td>도달 / 미도달 (11/11 세션 원장)</td><td>%(yn)d건</td><td>도달 %(yt)d건 · 만기 미도달 %(ye)d건</td><td>실제 도달률 %(yrate).1f%%</td><td>—</td></tr>\n"
    "        <tr><td><b>주봉</b> 도달확률 Brier")
rep("    xn=EX['closed'],",
    "    yn=EY['closed'], ybc=EY['brier_conditional'], ybd=EY['brier_distance_only'], ysk=sk(EY),\n"
    "    ybu=EY['shift_null']['brier_uniform_shift'], ysu=EY['skill_vs_uniform_shift_pct'],\n"
    "    yt=EY['touched'], ye=EY['expired'], yrate=EY['shift_null']['actual_rate_pct'],\n"
    "    c11=cls(sk(EY)), c12=cls(EY['skill_vs_uniform_shift_pct']),\n"
    "    xn=EX['closed'],")
# 4) 각주·섹터·관전·주봉 머리말
rep("※ 11/5(목) 회차는 만들지 않았습니다. 표의 등락은 하루치이고 지수 수치는 이틀치를 반영합니다.",
    "※ 11/9(월)~11/12(목) 회차는 만들지 않았습니다. 표의 등락은 하루치이고 지수 수치는 11/6 종가 대비 한 주치를 반영합니다.")
rep("오늘은 %(nall)d종목 중 %(ndn)d종목이 내려 섹터별로 가를 이야기가 없습니다.", "오늘은 %(nall)d종목 중 %(ndn)d종목이 내렸습니다.")
rep("<b>코스피·코스닥이 이틀 연속 내린 날, 로스터 %(nall)d종목 중 %(nup)d종목만 올랐고 %(ndn)d종목이 내렸습니다.</b>",
    "<b>코스피는 내리고 코스닥은 오른 날, 로스터 %(nall)d종목 중 %(nup)d종목이 올랐고 %(ndn)d종목이 내렸습니다.</b>")
rep("주간 낙폭이 큰 종목은", "주간 등락이 가장 낮은 종목은")

open(os.path.join(S, '_patch_narrative_1113.py'), 'w', encoding='utf-8').write(src)
print('generated', len(src))

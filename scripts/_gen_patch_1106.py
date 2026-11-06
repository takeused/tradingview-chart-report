# 10/30 회차(금, 10/29 건너뜀) 서술 패치를 11/6 회차(금, 11/5 건너뜀)용으로 바꿔 _patch_narrative_1106.py 를 만드는 일회성 생성기
import os, re
S = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(S, '_patch_narrative_1030.py'), encoding='utf-8').read()


def rep(a, b):
    global src
    assert src.count(a) >= 1, a[:70]
    src = src.replace(a, b, 1)


# 1) 로스터 증설 전제·공지를 걷어낸다 (이번 회차는 로스터 불변)
rep("assert (len(up), len(flat), len(down)) == (4, 1, 21) and len(ITEMS) == 26\nassert wcalls == 45 and len(near) + nalt == 74\nNEW = [i for i in ITEMS if i['code'] not in PC]\nassert [i['name'] for i in NEW] == ['신세계', '루닛']\n",
    "assert (len(up), len(flat), len(down)) == (2, 0, 22) and len(ITEMS) == 24\nassert wcalls == 40 and len(near) + nalt == 73\nassert all(i['code'] in PC for i in ITEMS)\n")
a0 = src.index("nw = {i['name']: i for i in NEW}")
a1 = src.index("# ---- B. 지난 회차 채점")
src = src[:a0] + """# 직전 회차(11/4)의 로스터 변경 공지는 이번 회차에 해당하지 않으므로 걷어낸다
if '📌 로스터 변경 —' in t:
    j0 = t.rindex('<div', 0, t.index('📌 로스터 변경 —'))
    j1 = t.index('</div>', j0) + len('</div>')
    t = t[:j0] + t[j1:].lstrip('\\n ')
assert '📌 로스터 변경 —' not in t

""" + src[a1:]

# 2) 날짜 치환 — 긴 것부터, 미래 날짜를 먼저
pairs = [("2026-10-30", "2026-11-06"), ("2026-10-28", "2026-11-04"), ("2026-10-23", "2026-10-30"),
         ("11/6", "11/13"), ("11/2(월)", "11/9(월)"),
         ("10/30", "11/6"), ("10/29", "11/5"), ("10/28", "11/4"), ("10/26", "11/2"),
         ("10/23", "10/30"), ("10/19", "10/26")]
# 이미 11/6·11/2 로 바뀐 것이 다시 치환되지 않도록 자리표시자를 거친다
for k, (a, b) in enumerate(pairs):
    src = src.replace(a, '\x00%d\x00' % k)
for k, (a, b) in enumerate(pairs):
    src = src.replace('\x00%d\x00' % k, b)

# 3) 머리 주석
src = src.replace("# 2026-11-06 회차(금, 11/5 을 건너뜀)", "# 2026-11-06 회차(금, 11/5 를 건너뜀)")
open(os.path.join(S, '_patch_narrative_1106.py'), 'w', encoding='utf-8').write(src)
print('generated', len(src))

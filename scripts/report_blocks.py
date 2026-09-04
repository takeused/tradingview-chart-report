# 리포트 해석 블록 생성 — 표만 있고 읽는 법·맥락이 없던 부분을 채운다
#
# 왜 있나 (2026-08-22): 증설로 표는 30행이 됐는데 **서술이 22종목 시절 그대로**였다.
#   신규 8종목은 섹터 요약·관전 포인트·베스트3 어디에도 나오지 않았고, 표의 σ·존/라인·
#   도달확률을 처음 보는 사람이 해석할 근거가 본문에 흩어져 있었다.
#
#   숫자는 전부 predictions.json / report_rank_*.json 에서 읽는다. 문장 안에 숫자를
#   손으로 적으면 다음 회차에 조용히 어긋난다 — 이번에 실제로 그렇게 어긋났다.
#
# 넣는 블록 둘 (2026-09-01에 셋 → 둘로 줄였다)
#   1) 읽는 법(범례) — σ·거리·존/라인·배지·도달확률을 한 자리에서 설명
#   2) 순위 — 로스터 전체 순위 + 상위 3종목 한 줄, 산식 공개, 동점 구간 명시
#
# 「🆕 신규 편입」 블록을 없앤 이유 (2026-09-01)
#   ① 표에 있는 값(종가·등락·초과·배지·거래량·레벨)을 문장으로 다시 읽어 줬을 뿐이다.
#   ② 머리말 250자가 블록마다 **글자 하나 안 틀리고** 반복됐다(3블록 = 750자).
#   ③ 로스터가 늘 때마다 블록이 하나씩 늘어 **무한히 자라는 구조**였다.
#   편입 시점은 일봉 표의 섹터 라벨(「신규 편입(2026-08-27 증설)」)이 그대로 밝혀 준다 —
#   원래 이 블록의 목적이 그것이었으므로 목적은 보존된다.
#
# 「⭐ 베스트3」를 순위 블록에 합친 이유 (2026-09-01)
#   같은 산식을 베스트3 머리말·순위 머리말·순위 각주에서 **세 번** 설명하고 있었고,
#   상위 3종목이 두 블록에 두 번 나왔다. 게다가 순위 제목은 「36종목 전체 순위」인데
#   표는 **5행**이었다 — 제목이 거짓말을 하고 있었다.
#
# 사용법
#   python scripts/report_blocks.py --date 2026-08-21

import json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def f(n):
    return '{:,}'.format(int(round(n)))


def ib(w):
    """받침에 맞춰 '은/는'을 붙인다 — '배럴는'처럼 찍히면 사람이 쓴 글로 안 읽힌다."""
    c = w[-1]
    if '가' <= c <= '힣':
        return w + ('은' if (ord(c) - 0xAC00) % 28 else '는')
    return w + '는'          # 영문·숫자로 끝나면 관행대로 '는'


def legend_block(items):
    """범례. σ·거리 예시는 **이 회차 로스터에서 계산**한다.

    2026-08-28에 발각: 예시가 "삼성전자 0.23σ · 배럴 1.6σ"로 상수로 박혀 있었는데,
    0.23σ는 ATR이 21,364이던 옛 회차 값이고 배럴 1.6σ는 아예 맞지 않았다
    (3,485원짜리 종목에 5,000원 위는 28σ다). **예시 숫자도 데이터에서 낸다.**
    """
    AMT = 5000                                   # 두 종목에 똑같이 대 보는 금액
    real = [i for i in items if i.get('atr')]
    hi = max(real, key=lambda i: i['atr'])       # ATR 가장 큰 종목
    lo = min(real, key=lambda i: i['atr'])       # ATR 가장 작은 종목
    # 거리 예시는 위 레벨이 있는 종목 중 1σ에 가장 가까운 것 — 읽는 사람이 감을 잡기 쉽다
    ups = [i for i in items if (i.get('p_touch') or {}).get('up')]
    ex = min(ups, key=lambda i: abs(i['p_touch']['up']['dist_sigma'] - 1.0))
    exu = ex['p_touch']['up']

    dist_row = """      <tr><td style="width:120px;"><b>거리</b></td>
          <td><b>오늘 종가에서 그 레벨(저항·지지)까지의 간격</b>입니다. 목표가도 예상가도
              아니고 <b>지금 자리에서 걸릴 자리까지 몇 원 남았나</b>일 뿐입니다.
              위쪽은 저항까지, 아래쪽은 지지까지를 재며 방향과 무관하게 <b>절댓값</b>으로 씁니다.
              예를 들어 %s 종가 %s원에 위 레벨이 %s원이니 거리는 <b>%s원</b>이고,
              이걸 ATR(%s원)로 나눈 <b>%.2fσ</b>가 표에 찍힙니다.
              도달확률도 이 거리에서 나옵니다 — <b>멀수록 낮고 가까울수록 높습니다.</b></td></tr>
""" % (ib(ex['name']), f(ex['close']), f(exu['level']),
       f(abs(exu['level'] - ex['close'])), f(ex['atr']), exu['dist_sigma'])

    sigma_row = """      <tr><td><b>σ (시그마)</b></td>
          <td>거리를 <b>그 종목의 하루 변동폭(ATR)</b>으로 나눈 값입니다. 1σ = 평소 하루치.
              1σ가 %s <b>%s원</b>인데 %s <b>%s원</b>이라, 같은 "%s원 위"라도
              %s <b>%.2fσ</b>이고 %s <b>%.1fσ</b>입니다 — 앞은 반나절이면 닿는 거리이고
              뒤는 몇 달치입니다. <b>종목 간 비교는 원이 아니라 σ로 합니다.</b></td></tr>
""" % (ib(hi['name']), f(hi['atr']), ib(lo['name']), f(lo['atr']), f(AMT),
       ib(hi['name']), AMT / float(hi['atr']), ib(lo['name']), AMT / float(lo['atr']))

    return '''
  <div class="secsum" id="howto" style="border-color:rgba(120,140,255,.45);">
    <h3>📖 표 읽는 법 — 숫자 넷만 알면 됩니다</h3>
    <p style="margin:0 0 10px;font-size:13px;color:var(--muted);">
      아래 표들은 "오를까 내릴까"를 맞히는 표가 아닙니다. <b>얼마나 움직일 여지가 있고,
      어디에 걸릴 자리가 있는지</b>를 재는 표입니다.</p>
    <table class="score" style="width:100%;">
''' + dist_row + sigma_row + '''      <tr><td><b>존 / 라인</b></td>
          <td><b>존</b>은 매물이 쌓인 <b>구간</b>(SMC 박스), <b>라인</b>은 과거 고·저점이 만든
              <b>한 점</b>입니다. 존이 기본이고 라인은 보조인데, <b>둘 중 가까운 쪽</b>을 씁니다.
              라인은 0.5σ보다 가까우면 노이즈로 보고 버립니다 —
              그래서 "유효 레벨 없음"이 나옵니다.</td></tr>
      <tr><td><b>배지</b></td>
          <td>절대 등락이 아니라 <b>지수 대비 초과수익 ÷ 그 종목 변동성</b>입니다.
              ±0.5σ를 넘으면 강세·약세입니다. 코스닥이 −4.63%인 날 −3.7% 하락도
              "덜 빠진 것"이라 초과는 플러스가 됩니다 —
              <b>계좌 손익과 배지는 다른 이야기입니다.</b></td></tr>
      <tr><td><b>도달확률</b></td>
          <td>그 레벨을 <b>지평 안에 한 번이라도 건드릴</b> 확률입니다. 종가가 거기서
              끝난다는 뜻이 아닙니다. 옆의 <b>기준선</b>은 거리만 보고 낸 값이고,
              둘의 차이가 <b>거래량·레인지로 보정한 몫</b>입니다.
              보정이 기준선을 이기는지가 이 리포트의 채점 대상입니다.</td></tr>
    </table>
  </div>
'''


def rank_block(items, rows, date):
    """순위 블록 — 상위 3종목 한 줄 + 로스터 전체 표.

    2026-09-01에 「⭐ 베스트3」를 여기로 합쳤다. 상위 3종목이 두 블록에 두 번 나왔고,
    같은 산식을 세 번 설명하고 있었다. 상위 3종목 코멘트도 **손으로 쓰지 않고 생성**한다 —
    손으로 쓰면 다음 회차에 낡고, 지금까지 실제로 매번 낡았다.

    표는 **로스터 전체**를 싣는다. 5행만 실으면서 제목에 「N종목 전체 순위」라고 쓰면
    제목이 거짓말을 한다(2026-09-01 이전까지 그랬다).
    """
    by = {i['code']: i for i in items}
    n_all = len(rows)
    MISS = {'room_up': '위쪽 여유', 'volx': '거래량', 'sig': '초과'}

    def sg(v):
        return '%.2fσ' % v if v is not None else '<span class="na">없음</span>'

    body = []
    for k, r in enumerate(rows, 1):
        body.append(
            '      <tr><td><b>%d</b></td><td class="name">%s <span class="code">(%s)</span></td>'
            '<td><b>%.1f</b></td><td>%+.2fσ</td><td>%.2f배</td><td>%s</td><td>%s</td></tr>'
            % (k, r['name'], r['code'], r['score'], r['sig'], r['volx'],
               sg(r['room_up']), sg(r['near_dn'])))

    tops = []
    for k, r in enumerate(rows[:3], 1):
        it = by[r['code']]
        pt = it.get('p_touch') or {}
        lv = []
        for d, lab in (('up', '위'), ('dn', '아래')):
            v = pt.get(d)
            if v:
                lv.append('%s %s(%s %.2fσ · %.1f%%)'
                          % (lab, f(v['level']), '존' if v['src'] == 'zone' else '라인',
                             v['dist_sigma'], v['p']))
            else:
                # 없는 쪽을 적지 않으면 독자가 "아래는?" 하고 표를 뒤진다.
                # 걸릴 자리가 없다는 사실 자체가 정보다.
                lv.append('<b>%s 유효 레벨 없음</b>' % lab)
        tail = ' · '.join(lv)
        # 결측이 있으면 그 사실을 밝힌다 — 없는 것을 좋은 것으로 읽으면 안 된다.
        note = ('<b>「%s」가 결측</b>이라 남은 가중치로 재정규화한 점수입니다.'
                % '」·「'.join(MISS.get(m, m) for m in r['missing'])) if r['missing'] else                '세 항목이 <b>모두 채워진</b> 점수입니다.'
        tops.append(
            '    <p style="margin:0 0 8px;font-size:13px;"><b>%d. %s (%s)</b> — 종가 %s · '
            '<b class="%s">%+.2f%%</b> · β조정 초과 <b class="%s">%+.2f%%p</b>(%s %+.2fσ) · '
            '거래량 %.2f배 · <b>합산 %.1f점</b><br><span class="vr">%s</span> %s</p>'
            % (k, it['name'], r['code'], f(it['close']),
               'up' if it['chg'] > 0 else 'down' if it['chg'] < 0 else '', it['chg'],
               'up' if it['excess'] > 0 else 'down', it['excess'],
               it['badge'], it['badge_sigma'], r['volx'], r['score'], tail, note))

    s3 = rows[0]['score'] - rows[2]['score']
    s47 = rows[3]['score'] - rows[6]['score'] if len(rows) > 6 else 0.0
    return '''
  <div class="secsum" style="border-color:rgba(255,215,0,.5);">
    <h3>🔁 순위 — %d종목 전체 <span class="muted">(%s 종가 기준 · v6.2 · β조정)</span></h3>
    <p style="margin:0 0 10px;font-size:13px;color:var(--muted);">
      <b>위험조정 초과수익 47 · 거래량 배수 29 · 위쪽 여유 24</b>를 각각 %d종목 안 백분위로
      환산해 합산합니다. <b>레벨이 없으면 그 항목은 결측으로 빼고 남은 가중치로 재정규화</b>합니다 —
      없는 것은 "여유가 최대"가 아니라 <b>정보가 없는</b> 것입니다.</p>
%s
    <table class="score" style="width:100%%;">
      <thead><tr><th>#</th><th>종목</th><th>합산</th><th>초과(배지)</th><th>거래량</th>
        <th>위 여유<br><span class="vr">멀수록 가점</span></th>
        <th>아래 지지<br><span class="vr">참고용 · 점수 미반영</span></th></tr></thead>
      <tbody>
%s
      </tbody>
    </table>
    <p style="margin:12px 0 0;font-size:13px;color:var(--muted);">
      ※ 상위 3종목은 <b>%.1f점</b>, 4~7위는 <b>%.1f점</b> 안에 몰려 있어 <b>서열이 아니라
      "상위 그룹"</b>으로만 읽어야 합니다. 「아래 지지 근접」 항목은 <b>2026-08-22에
      제거</b>했습니다 — 단기반전이 우리 검정에서 −0.79~−0.98%%/월(t −2.1~−2.3)로 음수였고,
      결측을 3.0σ로 메우던 처리가 1위를 뒤집고 있었습니다. 위쪽 여유도 검정된 것이 아니라
      <b>합리적 가정</b>입니다. 기계적 종합이며 <b>투자 추천이 아닙니다</b>.</p>
  </div>
''' % (n_all, date, n_all, chr(10).join(tops), chr(10).join(body), s3, s47)


def main():
    date = sys.argv[sys.argv.index('--date') + 1]
    d = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    ent = next(e for e in d['entries'] if e['asof'] == date)
    rk = json.load(open(os.path.join(ROOT, 'data', 'report_rank_%s.json' % date), encoding='utf-8'))
    rows = rk['rows']

    p = os.path.join(ROOT, 'report', 'index.html')
    html = open(p, encoding='utf-8').read()
    # 재실행 가능하게: 이미 있는 보완 블록을 지우고 다시 넣는다.
    # '🆕'·'투자유망 종목 베스트3' 은 2026-09-01에 없앤 블록이라, 옛 회차 스냅샷을
    # 템플릿으로 쓸 때 남아 있으면 여기서 걷어낸다.
    for mark in ('📖 표 읽는 법', '🆕', '🔁 순위', '투자유망 종목 베스트3'):
        while mark in html:
            h = html.index(mark)
            st = html.rindex('<div class="secsum"', 0, h)
            depth, k = 0, st
            while True:
                nx = min([x for x in (html.find('<div', k + 1), html.find('</div>', k + 1))
                          if x != -1])
                if html.startswith('<div', nx):
                    depth += 1
                else:
                    if depth == 0:
                        en = nx + 6
                        break
                    depth -= 1
                k = nx
            html = html[:st] + html[en:].lstrip('\n ')

    anchor = '<div class="secsum"'
    i = html.index(anchor)                      # 시장 요약 박스 앞
    html = html[:i] + legend_block(ent['items']).strip() + '\n\n  ' + html[i:]

    # 순위 블록은 「관전 포인트」 뒤, 주봉 구획(wkhead) 앞에 넣는다.
    # 예전에는 주봉 툴바 **뒤**에 있어 일봉 순위가 「주봉」 배지 아래에 걸려 있었다.
    k = html.index('<div class="wkhead">')
    html = html[:k] + rank_block(ent['items'], rows, date).strip() + '\n\n  ' + html[k:]

    for q in ('index.html', 'stock_comparison_report_%s.html' % date,
              'stock_comparison_report.html'):
        open(os.path.join(ROOT, 'report', q), 'w', encoding='utf-8').write(html)
    print('블록 2종 삽입 — 범례 · 순위 (%d자)' % len(html))
    return 0


if __name__ == '__main__':
    sys.exit(main())

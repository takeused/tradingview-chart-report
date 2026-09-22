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
              <b>한 점</b>입니다. 표의 <b>저·지</b>는 <b>둘 중 가까운 쪽</b>이고, 그 아래
              <b>대체</b>는 같은 방향의 <b>다른 출처</b> 레벨입니다 — 둘 다 예측으로 기록해
              따로 채점합니다(<b>2026-09-10 회차부터</b>). 그전에는 가까운 쪽만 기록했는데,
              라인이 종목당 400개 가까이 되다 보니 <b>존이 거의 매번 라인에 덮여</b>
              존 레벨이 회차당 넷밖에 안 남았습니다.
              <b>종가에 너무 붙은 자리는 버립니다</b> — 라인은 <b>0.5σ</b>, 존은 <b>0.3σ</b>보다
              가까우면 쓰지 않습니다. 종가와 몇백 원 떨어진 자리는 확률이 90%대로 나오지만
              <b>맞혀도 배울 것이 없기</b> 때문입니다(2026-09-09 회차부터 존에도 하한을 적용).
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


def compare_block(items, rows, date):
    """지표 비교 블록 — 세 항목을 나란히 싣는다. **합산도 등수도 없다.**

    2026-09-22에 순위 합산을 폐지하면서 바꿨다. 예전에는 47·29·24 가중치로 100점을
    만들어 1위부터 줄을 세웠는데, **그 세 항목 중 검정을 통과한 것이 하나도 없다**
    (경위는 report_enrich.py 머리말). 근거 없는 가중치로 만든 서열은 **없는 정보를
    준 것**이고, 실제로 2026-09-21 회차에서 배럴이 「위쪽 여유」 한 항목으로 3위에 올랐다.

    행 순서는 일봉 표와 같다(섹터 순). 독자가 열 제목을 눌러 원하는 기준으로 정렬한다.
    """
    by = {i['code']: i for i in items}
    n_all = len(rows)

    def sg(v, p):
        if v is None:
            return '<span class="na">없음</span>'
        return '%.2fσ<br><span class="vr">상위 %.0f%%</span>' % (v, 100.0 - p)

    body = []
    for r in rows:
        it = by[r['code']]
        body.append(
            '      <tr data-market="%s" data-badge="%s" data-q="%s %s">'
            '<td class="name">%s <span class="code">(%s)</span></td>'
            '<td>%+.2fσ<br><span class="vr">상위 %.0f%%</span></td>'
            '<td>%.2f배<br><span class="vr">상위 %.0f%%</span></td>'
            '<td>%s</td><td>%s</td></tr>'
            % (it['market'], it['badge'], r['name'], r['code'],
               r['name'], r['code'],
               r['sig'], 100.0 - r['p_sig'],
               r['volx'], 100.0 - r['p_volx'],
               sg(r['room_up'], r['p_room_up']),
               '%.2fσ' % r['near_dn'] if r['near_dn'] is not None
               else '<span class="na">없음</span>'))

    nmiss = sum(1 for r in rows if r['room_up'] is None)
    return '''
  <div class="secsum" style="border-color:rgba(255,215,0,.5);">
    <h3>📊 지표 비교 — %d종목 전체 <span class="muted">(%s 종가 기준 · v6.2 · β조정)</span></h3>
    <p style="margin:0 0 10px;font-size:13px;color:var(--muted);">
      <b>2026-09-22부터 합산 점수와 등수를 인쇄하지 않습니다.</b> 예전에는 아래 세 항목을
      <b>47 · 29 · 24</b>로 합산해 1위부터 줄을 세웠는데, <b>그 세 항목 중 검정을 통과한 것이
      하나도 없습니다</b>. 근거 없는 가중치로 만든 서열은 <b>없는 정보를 드리는 것</b>이라
      판단해 <b>세 항목을 나란히</b>만 싣습니다. 보고 싶은 기준이 있으면 <b>열 제목을 눌러
      정렬</b>하십시오.</p>
    <div class="rkfilter">
      <input type="search" id="rk-q" placeholder="종목명 · 코드 검색" aria-label="종목 검색">
      <select id="rk-mkt"><option value="">시장 전체</option><option value="KOSPI">코스피</option><option value="KOSDAQ">코스닥</option></select>
      <select id="rk-badge"><option value="">배지 전체</option><option value="강세">강세</option><option value="중립">중립</option><option value="약세">약세</option></select>
      <select id="rk-vol"><option value="0">거래량 전체</option><option value="1">1배 이상</option><option value="2">2배 이상</option></select>
      <button type="button" id="rk-reset">초기화</button>
      <span class="rkcount" id="rk-count"></span>
    </div>
    <table class="score" id="rank-table" style="width:100%%;">
      <thead><tr><th>종목</th>
        <th>위험조정 초과<br><span class="vr">배지 σ</span></th>
        <th>거래량 배수</th>
        <th>위 여유<br><span class="vr">저항까지 거리</span></th>
        <th>아래 지지<br><span class="vr">참고용</span></th></tr></thead>
      <tbody>
%s
      </tbody>
    </table>
    <p style="margin:12px 0 0;font-size:13px;color:var(--muted);">
      ※ <b>「상위 N%%」는 오늘 %d종목 안에서의 백분위</b>일 뿐 좋고 나쁨의 판정이 아닙니다.
      기본 순서는 <b>위 일봉 표와 같습니다</b>(섹터 순). 열 제목을 누르면 그 열로 정렬되고
      (오름 → 내림 → 원래 순서), 필터를 건 상태에서 정렬하면 <b>남은 종목 안에서만</b> 줄을 세웁니다.<br>
      ※ <b>세 항목의 검정 상태를 그대로 적습니다.</b>
      <b>「위쪽 여유」</b> — 2026-09-22 판정, 유니버스 300·유효 23회차에서 신호 기여
      <b>+0.066%%p(단측 p 0.125)</b>로 왕복 비용 0.280%%의 <b>24%%</b>에 그쳤습니다.
      <b>「거래량 배수」</b> — 2026-08-21 검정에서 거래량급증 계열은 <b>음수</b>였습니다
      (승률 35.7%%에 −2.37%%). <b>「위험조정 초과」</b> — 단기 모멘텀 계열로 같은 검정에서
      통과하지 못했습니다. <b>셋 다 "오늘 상태를 재는 자"일 뿐 수익을 예측하는 신호가 아닙니다.</b><br>
      ※ 「위쪽 여유」가 <b>없음</b>인 종목이 %d개입니다. 레벨이 없으면 <b>3.0σ로 채우지 않고
      빈칸으로</b> 둡니다 — 없는 것은 "여유가 최대"가 아니라 <b>정보가 없는</b> 것입니다.
      기계적 집계이며 <b>투자 추천이 아닙니다</b>.</p>
  </div>
''' % (n_all, date, chr(10).join(body), n_all, nmiss)


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
    for mark in ('📖 표 읽는 법', '🆕', '🔁 순위', '📊 지표 비교', '투자유망 종목 베스트3'):
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
    html = html[:k] + compare_block(ent['items'], rows, date).strip() + '\n\n  ' + html[k:]

    for q in ('index.html', 'stock_comparison_report_%s.html' % date,
              'stock_comparison_report.html'):
        open(os.path.join(ROOT, 'report', q), 'w', encoding='utf-8').write(html)
    print('블록 2종 삽입 — 범례 · 지표 비교 (%d자)' % len(html))
    return 0


if __name__ == '__main__':
    sys.exit(main())

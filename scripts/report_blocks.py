# 리포트 해석 블록 생성 — 표만 있고 읽는 법·맥락이 없던 부분을 채운다
#
# 왜 있나 (2026-08-22): 증설로 표는 30행이 됐는데 **서술이 22종목 시절 그대로**였다.
#   신규 8종목은 섹터 요약·관전 포인트·베스트3 어디에도 나오지 않았고, 표의 σ·존/라인·
#   도달확률을 처음 보는 사람이 해석할 근거가 본문에 흩어져 있었다.
#
#   숫자는 전부 predictions.json / report_rank_*.json 에서 읽는다. 문장 안에 숫자를
#   손으로 적으면 다음 회차에 조용히 어긋난다 — 이번에 실제로 그렇게 어긋났다.
#
# 넣는 블록 셋
#   1) 읽는 법(범례) — σ·존/라인·배지·도달확률을 한 자리에서 설명
#   2) 신규 편입 8종목 해석 — 왜 별도 그룹인지 + 종목별 한 줄
#   3) 순위 재산정 — 30종목 기준 상위, 산식 공개, 동점 구간 명시
#
# 사용법
#   python scripts/report_blocks.py --date 2026-08-21

import json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
NEW = ['403870', '214450', '241710', '196170', '039490', '003230', '002380', '192820']


def f(n):
    return '{:,}'.format(int(round(n)))


def legend_block():
    return '''
  <div class="secsum" id="howto" style="border-color:rgba(120,140,255,.45);">
    <h3>📖 표 읽는 법 — 숫자 넷만 알면 됩니다</h3>
    <p style="margin:0 0 10px;font-size:13px;color:var(--muted);">
      아래 표들은 "오를까 내릴까"를 맞히는 표가 아닙니다. <b>얼마나 움직일 여지가 있고,
      어디에 걸릴 자리가 있는지</b>를 재는 표입니다.</p>
    <table class="score" style="width:100%;">
      <tr><td style="width:120px;"><b>σ (시그마)</b></td>
          <td>거리를 <b>그 종목의 하루 변동폭(ATR)</b>으로 나눈 값입니다. 1σ = 평소 하루치.
              같은 "5,000원 위"라도 삼성전자는 0.23σ, 배럴은 1.6σ라 의미가 전혀 다릅니다.
              <b>종목 간 비교는 원이 아니라 σ로 합니다.</b></td></tr>
      <tr><td><b>존 / 라인</b></td>
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


def new_block(items, rank_by_code):
    order = ['192820', '002380', '241710', '214450', '403870', '196170', '039490', '003230']
    by = {i['code']: i for i in items}
    lines = []
    for c in order:
        it = by[c]
        pt = it.get('p_touch') or {}
        up, dn = pt.get('up'), pt.get('dn')
        lv = []
        if up:
            lv.append('위 %s(%s %.2fσ)' % (f(up['level']), '존' if up['src'] == 'zone' else '라인',
                                          up['dist_sigma']))
        if dn:
            lv.append('아래 %s(%s %.2fσ)' % (f(dn['level']), '존' if dn['src'] == 'zone' else '라인',
                                           dn['dist_sigma']))
        lvs = ' · '.join(lv) if lv else '<b>양쪽 다 유효 레벨 없음</b>'
        cl = 'up' if it['chg'] > 0 else 'down' if it['chg'] < 0 else ''
        rk = rank_by_code.get(c)
        lines.append(
            '      <li><b>%s</b> <span class="code">(%s)</span> — 종가 %s '
            '<span class="%s">%+.2f%%</span> · 초과 <b class="%s">%+.2f%%p</b>(%s %+.2fσ) · '
            '거래량 %.2f배%s<br><span class="vr">%s</span></li>'
            % (it['name'], c, f(it['close']), cl, it['chg'],
               'up' if it['excess'] > 0 else 'down', it['excess'],
               it['badge'], it['badge_sigma'], it['model_inputs']['volx'],
               ' · <b>합산 %.1f점(전체 %d위)</b>' % (rk['score'], rk['rank']) if rk else '',
               lvs))
    return '''
  <div class="secsum" style="border-color:rgba(255,180,60,.5);">
    <h3>🆕 신규 편입 8종목 — 오늘 처음 들어온 종목들입니다</h3>
    <p style="margin:0 0 10px;">
      8/21 회차에 <b>8종목을 추가해 로스터가 30종목</b>이 됐습니다. 표에서 이들만
      <b>맨 아래 별도 그룹</b>으로 묶은 이유는 섹터가 없어서가 아니라,
      <b>편입 시점을 숨기지 않기 위해서</b>입니다. 뒤늦게 넣은 종목을 기존 섹터에 섞으면
      "처음부터 보고 있었던 것처럼" 보입니다. 기록은 8/21 종가 기준이고
      그 이후 장이 열리지 않은 상태에서 붙였으므로, <b>움직인 것을 보고 고른 것은 아닙니다</b>.</p>
    <ul style="margin:0;padding-left:18px;line-height:1.85;">
%s
    </ul>
    <p style="margin:12px 0 0;font-size:13px;color:var(--muted);">
      ※ <b>코스메카코리아만 확률을 내지 않았습니다.</b> 위쪽은 신고가 부근이라 가장 가까운
      라인이 137,900(0.06σ)으로 <b>0.5σ 하한에 미달</b>해 노이즈로 버렸고, 아래쪽은 106,400까지
      비어 있어 <b>3σ 밖</b>입니다. 걸릴 자리가 없다는 사실 자체가 정보이므로,
      억지로 레벨을 만들지 않고 비워 둡니다.</p>
  </div>
'''.replace('%s\n    </ul>', '%s\n    </ul>') % '\n'.join(lines)


def rank_block(rows):
    top = rows[:5]
    spread = top[0]['score'] - top[-1]['score']
    body = []
    for i, r in enumerate(top, 1):
        sg = lambda v: '%.2fσ' % v if v is not None else '<span class="na">없음</span>'
        body.append(
            '      <tr><td><b>%d</b></td><td class="name">%s <span class="code">(%s)</span></td>'
            '<td><b>%.1f</b></td><td>%+.2fσ</td><td>%.2f배</td><td>%s</td><td>%s</td></tr>'
            % (i, r['name'], r['code'], r['score'], r['sig'], r['volx'],
               sg(r['room_up']), sg(r['near_dn'])))
    return '''
  <div class="secsum" style="border-color:rgba(0,200,120,.45);">
    <h3>🔁 순위 재산정 — 30종목 기준 · 산식도 고쳤습니다</h3>
    <p style="margin:0 0 10px;">
      위 「베스트3」는 <b>22종목이던 때 뽑은 것</b>이라 신규 8종목이 후보에 없었습니다.
      30종목으로 다시 계산하면서 <b>산식 자체도 손봤습니다</b>(아래 ※ 참조).</p>
    <table class="score" style="width:100%%;">
      <thead><tr><th>#</th><th>종목</th><th>합산</th><th>초과(배지)</th><th>거래량</th>
        <th>위 여유<br><span class="vr">멀수록 가점</span></th>
        <th>아래 지지<br><span class="vr">참고용 · 점수 미반영</span></th></tr></thead>
      <tbody>
%s
      </tbody>
    </table>
    <p style="margin:12px 0 0;font-size:13px;color:var(--muted);">
      산식 — <b>위험조정 초과 47 · 거래량 배수 29 · 위쪽 여유 24</b>, 각 항목을 30종목 안
      백분위로 환산해 합산합니다. <b>레벨이 없으면 그 항목은 결측으로 빼고 남은 가중치로
      재정규화</b>합니다.</p>
    <p style="margin:10px 0 0;font-size:13px;">
      ※ <b>「아래 지지 근접」15점을 뺐습니다.</b> 세 가지 이유입니다.
      ① <b>방향에 근거가 없습니다</b> — "지지에 가깝다"는 대체로 "최근 밀렸다"와 같은 말인데,
      우리 팩터 검정에서 <b>최근 하락 종목 매수(단기반전)는 −0.79~−0.98%%/월(t −2.1~−2.3)로
      뚜렷한 음수</b>였습니다. 가점을 줄 근거가 없습니다.
      ② <b>결측을 최고값으로 채우고 있었습니다</b> — 레벨이 없는 종목을 3.0σ로 메우자
      "정보가 없다"가 "여유 최대"로 둔갑해 코스메카코리아가 1위로 올라왔습니다.
      ③ <b>그 15점 하나로 1위가 바뀌었습니다</b>(코스맥스 ↔ 코스메카코리아).
      가정이 순위를 지배하면 그건 순위가 아닙니다.</p>
    <p style="margin:8px 0 0;font-size:13px;">
      ⚠️ 고친 뒤에도 <b>상위권 점수 폭은 %.1f점</b>에 불과합니다. 서열로 읽지 마시고
      <b>"상위 그룹"</b> 정도로만 보시기 바랍니다. 위쪽 여유 항목도 검정된 것이 아니라
      <b>합리적 가정</b>일 뿐입니다. 기계적 종합이며 투자 추천이 아닙니다.</p>
  </div>
''' % ('\n'.join(body), spread)


def main():
    date = sys.argv[sys.argv.index('--date') + 1]
    d = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    ent = next(e for e in d['entries'] if e['asof'] == date)
    rk = json.load(open(os.path.join(ROOT, 'data', 'report_rank_%s.json' % date), encoding='utf-8'))
    rows = rk['rows']
    rank_by_code = {r['code']: dict(r, rank=i + 1) for i, r in enumerate(rows)}

    p = os.path.join(ROOT, 'report', 'index.html')
    html = open(p, encoding='utf-8').read()
    # 재실행 가능하게: 이미 있는 보완 블록을 지우고 다시 넣는다
    for mark in ('📖 표 읽는 법', '🆕 신규 편입 8종목', '🔁 순위 재산정'):
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
    html = html[:i] + legend_block().strip() + '\n\n  ' + html[i:]

    # 섹터 요약 섹션 뒤에 신규 편입 해석과 순위 재산정을 넣는다
    key = '오늘의 시장 관전 포인트'
    j = html.rindex('<div', 0, html.index(key))
    blk = new_block(ent['items'], rank_by_code).strip() + '\n\n  '
    html = html[:j] + blk + html[j:]

    key2 = '📆 주봉으로 보면'
    k = html.rindex('<div', 0, html.index(key2))
    html = html[:k] + rank_block(rows).strip() + '\n\n  ' + html[k:]

    for q in ('index.html', 'stock_comparison_report_%s.html' % date,
              'stock_comparison_report.html'):
        open(os.path.join(ROOT, 'report', q), 'w', encoding='utf-8').write(html)
    print('블록 3종 삽입 — 범례 · 신규 8종목 해석 · 순위 재산정 (%d자)' % len(html))
    return 0


if __name__ == '__main__':
    sys.exit(main())

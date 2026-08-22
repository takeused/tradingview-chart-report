# 리포트 HTML 에 신규 로스터 행을 붙인다 — 숫자는 predictions.json 에서만 읽는다
#
# 왜 있나 (2026-08-22): 로스터를 늘릴 때 HTML 을 손으로 고치면 표와 데이터가 어긋난다.
#   check_report.py 가 그걸 잡지만, 애초에 어긋나지 않게 **한 원본에서 생성**한다.
#   숫자를 문서에서 베끼지 않는다는 v6 원칙을 표 생성에도 적용한 것이다.
#
# 사용법
#   python scripts/append_report_rows.py --date 2026-08-21 --codes 403870,214450,...

import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SECTOR = '신규 편입(2026-08-22 증설)'


def fmt(n):
    return '{:,}'.format(int(round(n))) if n is not None else '—'


def cls(v):
    return 'up' if v > 0 else 'down' if v < 0 else ''


def vol(n):
    return '%.2fM' % (n / 1e6) if n >= 1e6 else '%.1f만' % (n / 1e4)


def daily_row(it):
    b = {'강세': 'up', '약세': 'down', '중립': 'neutral'}[it['badge']]
    pt = it.get('p_touch') or {}
    up, dn = pt.get('up'), pt.get('dn')
    lv = []
    if up:
        lv.append('<b class="r">저</b>%s' % fmt(up['level']))
    else:
        lv.append('<b class="r">저</b><span class="na">유효 레벨 없음</span>')
    if dn:
        lv.append('<b class="s">지</b>%s' % fmt(dn['level']))
    else:
        lv.append('<b class="s">지</b><span class="na">유효 레벨 없음</span>')
    tail = ' / '.join(filter(None, [
        '위 %s <b>%.2fσ</b>' % ('존' if up['src'] == 'zone' else '라인', up['dist_sigma']) if up else '',
        '아래 %s <b>%.2fσ</b>' % ('존' if dn['src'] == 'zone' else '라인', dn['dist_sigma']) if dn else '']))
    return ('      <tr>\n'
            '        <td class="name">%s <span class="code">(%s)</span></td>\n'
            '        <td>%s</td><td class="%s">%+.2f%%<br><span class="rel %s">β조정 초과 %+.2f%%p</span></td>'
            '<td>%s~%s</td>\n'
            '        <td>%s<br><span class="vr">%.2f배</span></td>'
            '<td><span class="badge %s">%s(%+.2fσ)</span></td>'
            '<td class="zn">%s<br>%s<span class="atr">ATR %s · %s</span></td>\n'
            '      </tr>\n'
            % (it['name'], it['code'], fmt(it['close']), cls(it['chg']), it['chg'],
               cls(it['excess']), it['excess'], fmt(it['lo']), fmt(it['hi']),
               vol(it['vol']) if it.get('vol') else '—',
               it['volx'], b, it['badge'], it['badge_sigma'], lv[0], lv[1],
               fmt(it['atr']), tail or '유효 레벨 없음'))


def weekly_desc_row(w):
    tr = '상승' if w['wstreak'] > 0 else '하락'
    return ('      <tr>\n'
            '        <td class="name">%s <span class="code">(%s)</span></td>\n'
            '        <td>%s</td><td class="%s">%+.2f%%</td>\n'
            '        <td><span class="badge %s">%s</span><br><span class="vr">%d주 연속 %s</span></td>\n'
            '        <td class="%s">%d%%<br><span class="vr">12주 range</span></td>\n'
            '        <td><span class="%s">4주 %+.1f%%</span><br><span class="%s">12주 %+.1f%%</span></td>\n'
            '        <td>%.1f%%</td>\n'
            '      </tr>\n'
            % (w['name'], w['code'], fmt(w['close']), cls(w['wchg']), w['wchg'],
               cls(w['wstreak']), tr, abs(w['wstreak']), tr,
               cls(w['pos12'] - 50), w['pos12'],
               cls(w['m4']), w['m4'], cls(w['m12']), w['m12'], w['watrpct']))


def weekly_level_row(w):
    def cell(pr):
        if not pr:
            return ('<td><span class="na">유효 레벨 없음</span></td>'
                    '<td><span class="na">—</span></td>')
        return ('<td>%s <span class="vr">%s · <b>%.2fσ</b></span></td>'
                '<td><b>%.1f%%</b><br><span class="vr">기준선 %.1f%% (%+.1f)</span></td>'
                % (fmt(pr['level']), '존' if pr['src'] == 'zone' else '라인',
                   pr['dist_sigma'], pr['p'], pr['p_base'], pr['p'] - pr['p_base']))
    pt = w.get('p_touch') or {}
    return ('      <tr>\n'
            '        <td class="name">%s <span class="code">(%s)</span></td>\n'
            '        %s%s<td>%s</td>\n'
            '      </tr>\n'
            % (w['name'], w['code'], cell(pt.get('up')), cell(pt.get('dn')),
               w.get('horizon', '2~3주')))


def insert(html, header_text, block, colspan):
    """표의 </tbody> 앞에 섹터 그룹을 붙인다.

    표는 **인덱스가 아니라 헤더 내용으로** 찾는다. 앞에 블록을 끼워 넣으면 인덱스가
    조용히 밀려 엉뚱한 표에 행을 넣게 된다(2026-08-22에 범례 추가로 실제 발생).
    """
    st = None
    for m in re.finditer(r'<table[^>]*>', html):
        head = html[m.start():m.start() + 3000]
        if '</thead>' in head and header_text in head[:head.index('</thead>')]:
            st = m.start()
            break
    if st is None:
        raise SystemExit('표를 못 찾았다 — 헤더 "%s"' % header_text)
    end = html.index('</tbody>', st)
    grp = ('      <tr class="sector"><td colspan="%d">%s</td></tr>\n%s'
           % (colspan, SECTOR, block))
    return html[:end] + grp + html[end:]


def main():
    date = sys.argv[sys.argv.index('--date') + 1]
    codes = sys.argv[sys.argv.index('--codes') + 1].split(',')
    d = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    ent = next(e for e in d['entries'] if e['asof'] == date)
    went = next(e for e in d['weekly_entries'] if e['asof'] == date)
    items = [i for i in ent['items'] if i['code'] in codes]
    wrows = [i for i in went['items'] if i['code'] in codes]

    src = os.path.join(ROOT, 'report', 'stock_comparison_report_%s.html' % date)
    html = open(src, encoding='utf-8').read()
    if SECTOR in html:
        raise SystemExit('이미 증설 섹터가 있다 — 중복 삽입 방지')

    html = insert(html, '방향(위험조정)', ''.join(daily_row(i) for i in items), 7)
    html = insert(html, '추세(연속주)', ''.join(weekly_desc_row(w) for w in wrows), 7)
    html = insert(html, '위 레벨(주봉)', ''.join(weekly_level_row(w) for w in wrows), 6)
    html = html.replace('22종목', '30종목')

    for p in ('stock_comparison_report_%s.html' % date, 'index.html',
              'stock_comparison_report.html'):
        open(os.path.join(ROOT, 'report', p), 'w', encoding='utf-8').write(html)
    print('행 삽입 완료 — 일봉 %d · 주봉서술 %d · 주봉레벨 %d · 3개 파일 갱신'
          % (len(items), len(wrows), len(wrows)))
    if '{{' in html or '}}' in html:
        print('경고 — 미치환 플레이스홀더가 있다')
    return 0


if __name__ == '__main__':
    sys.exit(main())

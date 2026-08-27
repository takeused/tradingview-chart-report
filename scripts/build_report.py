# 새 회차 리포트 HTML 을 직전 스냅샷에서 만든다 — 표는 predictions.json 에서만 생성한다
#
# 왜 있나 (2026-08-24, 4회차): 지금까지 새 회차 HTML 은 직전 파일을 손으로 고쳐 왔다.
#   31종목이면 표 한 줄만 어긋나도 check_report 가 잡는데, 잡히기 전에 시간을 다 쓴다.
#   표·드롭다운·헤더 같은 기계적인 부분은 코드로 굳히고 서술만 사람이 쓴다.
#
# 섹터 묶음과 종목 순서는 **직전 회차 표에서 그대로 읽어** 유지한다. 로스터가 같은
#   회차에서 순서가 흔들리면 독자가 회차 간 비교를 못 한다.
#
# 주봉 확률 표는 건드리지 않는다 — 금요일 전용이라 월요일에는 금요일 값이 그대로
#   유효하고, 대신 제목에 기준 회차를 박는다(6-c 절).
#
# 사용법
#   python scripts/build_report.py --date 2026-08-24 --prev 2026-08-21 --weekday 월

import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from append_report_rows import daily_row, weekly_desc_row

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
REP = os.path.join(ROOT, 'report')


def find_table(html, header_text):
    for m in re.finditer(r'<table[^>]*>', html):
        head = html[m.start():m.start() + 3000]
        if '</thead>' in head and header_text in head[:head.index('</thead>')]:
            return m.start()
    raise SystemExit('표를 못 찾았다 — 헤더 "%s"' % header_text)


def sector_order(html):
    """직전 일봉 표에서 (섹터, [코드…]) 순서를 읽는다."""
    i = find_table(html, '방향(위험조정)')
    seg = html[i:html.index('</tbody>', i)]
    out, cur = [], None
    for m in re.finditer(r'<tr class="sector"><td colspan="\d+">(.*?)</td></tr>'
                         r'|<span class="code">\((\d+)\)</span>', seg):
        if m.group(1) is not None:
            cur = (m.group(1), [])
            out.append(cur)
        elif cur is not None:
            cur[1].append(m.group(2))
    return out


def rebuild(html, header_text, body):
    i = find_table(html, header_text)
    a = html.index('<tbody>', i) + len('<tbody>')
    b = html.index('</tbody>', i)
    return html[:a] + '\n' + body + '    ' + html[b:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--prev', required=True)
    ap.add_argument('--weekday', required=True)
    ap.add_argument('--add-sector', default=None,
                    help='직전 표에 없던 종목을 담을 섹터 라벨(증설 회차에만)')
    a = ap.parse_args()

    d = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    ent = next(e for e in d['entries'] if e['asof'] == a.date)
    items = {i['code']: i for i in ent['items']}
    wk = json.load(open(os.path.join(REP, '..', 'data', 'weekly_desc_%s.json' % a.date),
                        encoding='utf-8'))

    html = open(os.path.join(REP, 'stock_comparison_report_%s.html' % a.prev),
                encoding='utf-8').read()
    order = sector_order(html)
    seen = [c for _, cs in order for c in cs]
    missing = [c for c in items if c not in seen]
    if missing and not a.add_sector:
        raise SystemExit('직전 표에 없는 종목이 있다 — %s' % missing)
    if missing:
        # 증설 — 직전 표에 없던 종목은 별도 그룹으로 맨 뒤에 붙인다.
        # 순서는 entry 의 항목 순서를 따른다(코드순).
        order = order + [(a.add_sector, [c for c in items if c in missing])]
        seen = [c for _, cs in order for c in cs]
    gone = [c for c in seen if c not in items]
    if gone:
        raise SystemExit('직전 표에 있는데 이번 항목에 없는 종목 — %s' % gone)
    if len(seen) != len(items):
        raise SystemExit('직전 표 %d행 != 이번 항목 %d개' % (len(seen), len(items)))

    daily, weekly = '', ''
    for label, codes in order:
        daily += '      <tr class="sector"><td colspan="7">%s</td></tr>\n' % label
        weekly += '      <tr class="sector"><td colspan="7">%s</td></tr>\n' % label
        for c in codes:
            daily += daily_row(items[c])
            weekly += weekly_desc_row(wk[c])
    html = rebuild(html, '방향(위험조정)', daily)
    html = rebuild(html, '추세(연속주)', weekly)

    # 드롭다운 — 새 날짜를 넣고 (최신) 표시를 옮긴다
    html = html.replace('<option value="stock_comparison_report_%s.html" selected>%s (최신)</option>'
                        % (a.prev, a.prev),
                        '<option value="stock_comparison_report_%s.html">%s</option>\n'
                        '      <option value="stock_comparison_report_%s.html" selected>%s (최신)</option>'
                        % (a.prev, a.prev, a.date, a.date))
    # 헤더 기준일
    html = re.sub(r'기준일 \d{4}-\d{2}-\d{2}\([월화수목금]\)',
                  '기준일 %s(%s)' % (a.date, a.weekday), html)
    # <title> 도 같이 옮긴다 — check_report 가 title 의 회차를 대조한다
    html, n = re.subn(r'(<title>[^<]*?)\d{4}-\d{2}-\d{2}(</title>)',
                      r'\g<1>%s\g<2>' % a.date, html)
    if n != 1:
        raise SystemExit('<title> 기준일 치환 %d건 — 제목 형식을 확인하라' % n)

    for p in ('stock_comparison_report_%s.html' % a.date, 'index.html',
              'stock_comparison_report.html'):
        open(os.path.join(REP, p), 'w', encoding='utf-8').write(html)
    print('표 재생성 완료 — 일봉 %d행 · 주봉서술 %d행 · 3개 파일 기록'
          % (len(seen), len(seen)))
    if '{{' in html or '}}' in html:
        print('경고 — 미치환 플레이스홀더가 있다')
    return 0


if __name__ == '__main__':
    sys.exit(main())

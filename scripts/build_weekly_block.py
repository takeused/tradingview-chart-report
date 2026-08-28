# 리포트의 「주봉 도달확률」 블록(머리말·표·각주)을 주봉 entry 에서 다시 만든다 — 금요일 전용
#
# 왜 있나 (2026-08-28): build_report.py 는 주봉 확률 표를 일부러 건드리지 않는다.
#   월~목 회차에는 지난 금요일 값이 그대로 유효하기 때문이다. 그런데 금요일에는
#   그 표를 통째로 갈아야 하는데 그 코드가 없어서 8/21 회차는 손으로 만들었다.
#   머리말과 각주에 "위쪽 존이 남은 종목은 NAVER·클래시스·에스티팜 셋뿐" 같은
#   **그 회차의 사실**이 문장으로 박혀 있어, 손으로 두면 다음 회차의 거짓말이 된다.
#   그래서 표뿐 아니라 머리말·각주도 전부 entry 에서 세어 만든다.
#
# 사용법
#   python scripts/build_weekly_block.py --date 2026-08-28 --prev-week 2026-08-21

import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from append_report_rows import weekly_level_row
from build_report import sector_order, find_table

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
REP = os.path.join(ROOT, 'report')
HEAD = '위 레벨(주봉)'


def fmt(n):
    return format(int(n), ',')


def intro(date, n_calls, prev_week):
    return (
        '    <h3>📌 주봉 도달확률 — <span class="flip">%s(금) 종가 기준으로 갱신했습니다</span></h3>\n'
        '    <p style="margin:0;">아래 주봉 레벨·확률 표는 <b>오늘(%s) 종가 기준</b>입니다. '
        '<b>주봉은 금요일에만 분석합니다</b> — 주봉이 완성된 봉이 되는 시점이 금요일 종가이고, '
        '주봉 확률표가 <b>완성된 봉으로 보정</b>돼 있기 때문입니다. 진행 중인 봉으로 확률을 내면 '
        '<b>자를 바꿔 놓고 표를 그대로 쓰는</b> 꼴이 됩니다.</p>\n'
        '    <p style="margin:12px 0 0;">오늘 연 주봉 콜 <b>%d건</b>은 <b>일봉과 분리된 원장</b>'
        '(weekly_calls)에서 <b>주 단위로</b> 만기를 세며, 다음 금요일 회차에 그 주의 '
        '<b>주봉 고가·저가</b>로 채점됩니다. 일봉 원장에 섞으면 채점기가 하루마다 만기를 깎아 '
        '1~3일 만에 닫아 버립니다. 지난 회차(%s) 콜은 오늘 채점했습니다.</p>\n'
        % (date[5:].replace('-', '/').lstrip('0'), date, n_calls, prev_week))


def footnote(items, sample):
    up_zone = [i['name'] for i in items
               if (i.get('p_touch') or {}).get('up', {}).get('src') == 'zone']
    inzone = [i['name'] for i in items
              if (i.get('p_touch') or {}).get('up', {}).get('src') == 'zone'
              and (i.get('p_touch') or {}).get('dn', {}).get('src') == 'zone']
    no_up = [i['name'] for i in items if i.get('resist') is None]
    no_dn = [i['name'] for i in items if i.get('support') is None]
    short = ['%s(주봉 %d개)' % (i['name'], i['model_inputs']['watr_bars'])
             for i in items if i.get('atr_insufficient')]

    def lst(xs):
        return '·'.join(xs) if xs else '없음'

    out = ['  <div class="note">※ 거리 <b>σ는 전부 주봉 ATR(14)</b> 기준입니다 — 일봉 표의 σ와 '
           '<b>섞어 읽으면 안 됩니다</b>. 예를 들어 %s 일봉 ATR은 %s이고 주봉 ATR은 %s입니다.<br>'
           % (sample[0], fmt(sample[1]), fmt(sample[2]))]
    out.append('  ※ <b>주봉 존은 대부분 소진돼 있습니다.</b> %d종목 중 위쪽 주봉 존이 3σ 안에 '
               '남은 종목은 <b>%s</b>이고, 나머지는 몇 년 전 자리라 3σ 밖입니다. 그래서 위쪽 '
               '레벨은 대부분 <b>주봉 스윙 라인</b>에서 나옵니다.<br>'
               % (len(items), lst(up_zone)))
    if no_up or no_dn:
        out.append('  ※ 위쪽에 3σ 안 레벨이 없는 종목은 <b class="up">%s</b>, 아래쪽이 없는 종목은 '
                   '<b class="down">%s</b>입니다. 사유(3σ 밖·0.5σ 하한 미달·후보 없음)는 '
                   '각 종목의 기록(predictions.json 의 note)에 남깁니다.<br>'
                   % (lst(no_up), lst(no_dn)))
    if inzone:
        out.append('  ※ <b>%s</b>은 종가가 주봉 존 안에 있어 <b>존의 경계가 곧 레벨</b>입니다.<br>'
                   % lst(inzone))
    if short:
        out.append('  ※ <b>%s</b>는 ATR 창이 120주에 못 미쳐 <b>확률 미산출</b>로 두고 레벨만 '
                   '표시합니다.' % lst(short))
    txt = '\n'.join(out)
    if txt.endswith('<br>'):
        txt = txt[:-len('<br>')]
    return txt + '</div>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--prev-week', required=True)
    a = ap.parse_args()

    d = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    we = next(e for e in d['weekly_entries'] if e['asof'] == a.date)
    de = next(e for e in d['entries'] if e['asof'] == a.date)
    rows = {i['code']: i for i in we['items']}
    datr = {i['code']: i['atr'] for i in de['items']}
    n_calls = sum(len(i.get('p_touch') or {}) for i in we['items'])

    html = open(os.path.join(REP, 'index.html'), encoding='utf-8').read()
    order = sector_order(html)
    seen = [c for _, cs in order for c in cs]
    if sorted(seen) != sorted(rows):
        raise SystemExit('일봉 표 종목과 주봉 entry 종목이 다르다 — %s'
                         % (set(seen) ^ set(rows)))

    body = ''
    for label, codes in order:
        body += '      <tr class="sector"><td colspan="6">%s</td></tr>\n' % label
        for c in codes:
            body += weekly_level_row(rows[c])

    # 표 본문 교체
    i = find_table(html, HEAD)
    s = html.index('<tbody>', i) + len('<tbody>')
    e = html.index('</tbody>', s)
    html = html[:s] + '\n' + body + '    ' + html[e:]

    # 머리말 교체 — 표 바로 앞 div 의 h3 + 문단들
    dv = html.rindex('<div class="secsum"', 0, html.index('<h3>📌 주봉 도달확률'))
    dend = html.index('</div>', dv)
    open_tag = html[dv:html.index('>', dv) + 1]
    html = (html[:dv] + open_tag + '\n' + intro(a.date, n_calls, a.prev_week)
            + '  ' + html[dend:])

    # 각주 교체 — 표 뒤 첫 <div class="note">
    i2 = html.index('</tbody>', html.index(HEAD))
    n1 = html.index('<div class="note">', i2)
    n2 = html.index('</div>', n1) + len('</div>')
    sample_code = '005930'
    sample = (rows[sample_code]['name'], datr[sample_code], rows[sample_code]['atr'])
    html = html[:n1] + footnote(we['items'], sample).lstrip() + html[n2:]

    for p in ('stock_comparison_report_%s.html' % a.date, 'index.html',
              'stock_comparison_report.html'):
        open(os.path.join(REP, p), 'w', encoding='utf-8').write(html)
    print('주봉 블록 재생성 — %d행 · 콜 %d건' % (len(rows), n_calls))
    return 0


if __name__ == '__main__':
    sys.exit(main())

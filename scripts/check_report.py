# 발행된 리포트 HTML 이 predictions.json 과 같은 숫자를 말하는지 대조한다
#
# 왜 있나: predictions.json 은 validate_predictions.py 가 지키지만, 리포트는 사람이 산문으로
#   쓰기 때문에 그 사이에서 조용히 어긋난다. 2026-08-20 회차에서 실제로 SK스퀘어 레벨을
#   고친 뒤 섹터 요약·베스트3 각주가 옛 숫자를 그대로 인쇄할 뻔했다. 표 숫자는 기계가 만들어도
#   산문은 아니므로, 최소한 '표가 JSON 과 같은가' 는 기계로 못 박아 둔다.
#
# 무엇을 보는가
#   1) 리포트 3종(index / 스냅샷 / 복사본)이 바이트 단위로 같은가
#   2) 헤더의 기준일·제목이 마지막 회차 asof 와 같은가
#   3) 날짜 드롭다운의 최신 항목이 그 회차이고 selected 인가
#   4) 종목별 행에 종가·레벨·거리σ 가 JSON 과 같은 값으로 찍혔는가
#   5) 미치환 플레이스홀더가 남아 있지 않은가
#
# 사용법
#   python scripts/check_report.py                 # 마지막 회차 기준
#   python scripts/check_report.py 2026-08-20      # 특정 회차 기준

import io, json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PRED = os.path.join(ROOT, 'data', 'predictions.json')
REPDIR = os.path.join(ROOT, 'report')


def read(p):
    return io.open(p, encoding='utf-8').read()


def rows_of(html):
    """일봉 표를 종목별 구간으로 쪼갠다. 주봉 표는 제외한다."""
    end = html.find('<div class="wkhead">')
    day = html[:end] if end > 0 else html
    marks = [(m.start(), m.group(1)) for m in
             re.finditer(r'class="name">[^<]+? <span class="code">\((\d{6})\)', day)]
    return {c: day[p:(marks[i + 1][0] if i + 1 < len(marks) else len(day))]
            for i, (p, c) in enumerate(marks)}


def _split(seg):
    marks = [(m.start(), m.group(1)) for m in
             re.finditer(r'class="name">[^<]+? <span class="code">\((\d{6})\)', seg)]
    return {c: seg[p:(marks[i + 1][0] if i + 1 < len(marks) else len(seg))]
            for i, (p, c) in enumerate(marks)}


def wrows_of(html):
    """주봉 레벨·도달확률 표를 종목별 구간으로 쪼갠다."""
    i = html.find('주봉 도달확률')
    if i < 0:
        return {}
    j = html.find('<div class="foot">', i)
    return _split(html[i:(j if j > 0 else len(html))])


def main():
    asof = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else None
    d = json.load(open(PRED, encoding='utf-8'))
    e = d['entries'][-1] if asof is None else \
        next(x for x in d['entries'] if x['asof'] == asof)
    asof = e['asof']
    fail = []

    def need(cond, msg):
        if not cond:
            fail.append(msg)

    snap = os.path.join(REPDIR, 'stock_comparison_report_%s.html' % asof)
    idx = os.path.join(REPDIR, 'index.html')
    cp = os.path.join(REPDIR, 'stock_comparison_report.html')
    need(os.path.exists(snap), '스냅샷 %s 가 없다' % os.path.basename(snap))
    if not os.path.exists(snap):
        return report(fail, asof)

    # 1) 3종 동일
    a, b, c = read(snap), read(idx), read(cp)
    need(a == b, 'index.html 이 스냅샷과 다르다')
    need(a == c, 'stock_comparison_report.html 이 스냅샷과 다르다')
    html = a

    # 2) 기준일
    need('기준일 %s' % asof in html, '헤더 기준일이 %s 가 아니다' % asof)
    need(re.search(r'<title>[^<]*%s</title>' % asof, html) is not None,
         '<title> 이 %s 를 가리키지 않는다' % asof)

    # 3) 드롭다운
    sel = re.findall(r'<option value="([^"]+)" selected>', html)
    need(sel == ['stock_comparison_report_%s.html' % asof],
         '드롭다운 selected 가 %s 가 아니다 (%s)' % (asof, sel))
    need(html.count('stock_comparison_report_%s.html' % asof) >= 1,
         '드롭다운에 %s 항목이 없다' % asof)

    # 4) 종목별 숫자 대조
    seg = rows_of(html)
    need(len(seg) == len(e['items']),
         '일봉 표 종목 수 %d != entry 종목 수 %d' % (len(seg), len(e['items'])))
    for it in e['items']:
        g = seg.get(it['code'])
        nm = it.get('name', it['code'])
        if g is None:
            fail.append('%s 행이 리포트에 없다' % nm)
            continue
        need('{:,}'.format(it['close']) in g, '%s — 종가 %s 가 표에 없다'
             % (nm, '{:,}'.format(it['close'])))
        for dirn, fld in (('up', 'resist'), ('dn', 'support')):
            lvl = it.get(fld)
            blk = (it.get('p_touch') or {}).get(dirn)
            if lvl is None or blk is None:
                continue
            need('{:,}'.format(lvl) in g,
                 '%s — %s %s 가 표에 없다' % (nm, fld, '{:,}'.format(lvl)))
            need('<b>%.2fσ</b>' % blk['dist_sigma'] in g,
                 '%s — %s 거리 %.2fσ 가 표에 없다' % (nm, dirn, blk['dist_sigma']))

    # 4-b) 주봉 레벨표 대조 — 주봉 회차가 있으면 같은 숫자를 말해야 한다
    wents = d.get('weekly_entries', [])
    we = next((x for x in wents if x['asof'] == asof), None)
    if we is not None:
        wseg = wrows_of(html)
        need(len(wseg) == len(we['items']),
             '주봉 레벨표 종목 수 %d != 주봉 entry 종목 수 %d' % (len(wseg), len(we['items'])))
        for it in we['items']:
            g = wseg.get(it['code'])
            nm = it.get('name', it['code'])
            if g is None:
                fail.append('%s 행이 주봉 레벨표에 없다' % nm)
                continue
            for dirn, fld in (('up', 'resist'), ('dn', 'support')):
                lvl = it.get(fld)
                if lvl is None:
                    continue
                need('{:,}'.format(lvl) in g,
                     '%s(주봉) — %s %s 가 표에 없다' % (nm, fld, '{:,}'.format(lvl)))
                blk = (it.get('p_touch') or {}).get(dirn)
                if blk is None:
                    continue
                need('<b>%.2f\u03c3</b>' % blk['dist_sigma'] in g,
                     '%s(주봉) — %s 거리 %.2f\u03c3 가 표에 없다' % (nm, dirn, blk['dist_sigma']))
                need('<b>%.1f%%</b>' % blk['p'] in g,
                     '%s(주봉) — %s 확률 %.1f%% 가 표에 없다' % (nm, dirn, blk['p']))
            # ATR 창이 짧아 확률을 안 낸 종목은 그 사실이 표에 드러나야 한다
            if it.get('atr_insufficient'):
                need('확률 미산출' in g, '%s(주봉) — 확률 미산출 표시가 없다' % nm)

    # 5) 플레이스홀더
    for pat in (r'%\(\w+\)[sd]', r'\{\{\w+\}\}', r'\bTODO\b', r'\bXXX\b'):
        m = re.search(pat, html)
        need(m is None, '미치환 플레이스홀더가 남아 있다: %s' % (m.group(0) if m else ''))

    return report(fail, asof)


def report(fail, asof):
    print('리포트-데이터 대조 (%s) — 불일치 %d건' % (asof, len(fail)))
    for f in fail:
        print('  [불일치] ' + f)
    if not fail:
        print('통과')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()

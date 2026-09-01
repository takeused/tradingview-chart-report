# 리포트 보완 — 집계·순위·해석을 데이터에서 다시 계산해 반영한다
#
# 왜 있나 (2026-08-22): 로스터를 22 → 30 으로 늘리면서 **표만 갱신되고 집계와 해석이
#   그대로 남았다.** 헤더 배지 분포는 22종목 시절 값(강세 3·중립 16·약세 3)이었고,
#   시장 분포도 "코스피 13 · 코스닥 9"로 남아 있었으며, 베스트3 는 신규 8종목을
#   후보에서 뺀 채로 뽑혀 있었다(코스맥스 +0.64σ가 전체 3위인데 빠졌다).
#   check_report.py 는 표의 숫자만 대조하므로 이런 **서술부 정합성은 못 잡는다.**
#
# 그래서 배지 분포·시장 분포·상위 순위를 **발행된 표에서 파싱해** 다시 계산하고,
#   본문의 해당 숫자를 바꾼다. 손으로 고치면 다음 증설 때 또 어긋난다.
#
# 순위 정의(리포트에 함께 인쇄한다 — 재현 가능해야 순위다)
#   위험조정 초과 47 · 거래량 배수 29 · 위쪽 여유 24, 각 항목 백분위 합산.
#
#   **「아래 지지 근접」15점을 뺐다 (2026-08-22).** 세 가지 이유다.
#     (1) 방향에 근거가 없다. "지지에 가깝다"는 대체로 "최근 밀렸다"와 같은 말인데,
#         무수정 유니버스 검정에서 **단기반전(최근 하락 매수)은 −0.79~−0.98%/월
#         (t −2.1~−2.3)로 뚜렷한 음수**였다. 가점을 줄 근거가 없다.
#     (2) 결측 처리가 순위를 지배했다. 레벨이 없는 종목을 3.0σ 로 채웠더니
#         코스메카코리아(양쪽 레벨 없음)가 현행 최저점 ↔ 방향 반전 시 최고점이 된다.
#     (3) 이 항목 하나로 1위가 바뀐다 — 현행 코스맥스 / 제거 코스메카코리아 /
#         반전 코스메카코리아. 순위가 가정에 지배되면 그건 순위가 아니다.
#
#   위쪽 여유(저항까지 거리, 멀수록 유리)는 남긴다. 다만 **레벨이 없으면 3.0σ 로 채우지
#   않고 결측으로 두고, 그 종목은 남은 항목의 가중치로 재정규화**한다. 채워 넣으면
#   "정보가 없다"가 "최고값"으로 둔갑한다 — 실제로 코스메카코리아(위·아래 레벨 없음)가
#   그 처리 때문에 1위로 올라왔었다. **없는 것은 좋은 것이 아니다.**
#
# 사용법
#   python scripts/report_enrich.py --date 2026-08-21 [--dry]

import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
W = {'badge': 47, 'volx': 29, 'room_up': 24}       # 합 100. near_dn 은 위 주석 참조


def find_table(html, header_text):
    """표를 **인덱스가 아니라 헤더 내용으로** 찾는다.

    앞에 블록을 하나 끼워 넣으면 인덱스가 조용히 밀린다 — 2026-08-22에 범례 표를
    추가하자마자 일봉 표 파싱이 0행이 됐다. 위치로 고르면 다음에 또 밀린다.
    """
    for m in re.finditer(r'<table[^>]*>', html):
        seg = html[m.start():html.index('</thead>', m.start()) + 8]             if '</thead>' in html[m.start():m.start() + 3000] else ''
        if header_text in seg:
            return m.start()
    raise SystemExit('표를 못 찾았다 — 헤더 "%s"' % header_text)


def parse_rows(html):
    """일봉 표에서 종목·배지·σ 를 읽는다 — 발행된 값이 기준이다."""
    i = find_table(html, '방향(위험조정)')
    j = html.index('</tbody>', i)
    pat = (r'<td class="name">(.*?) <span class="code">\((\d+)\)</span>.*?'
           r'badge (?:up|down|neutral)">(강세|중립|약세)\(([+-][\d.]+)σ\)')
    return [{'name': n, 'code': c, 'badge': b, 'sig': float(v)}
            for n, c, b, v in re.findall(pat, html[i:j], re.S)]


def pct(vals):
    """백분위 0~100. 동점은 같은 값을 준다."""
    srt = sorted(vals)
    n = len(srt)
    return [100.0 * sum(1 for x in srt if x < v) / (n - 1) if n > 1 else 50.0 for v in vals]


def score(rows, items):
    by = {i['code']: i for i in items}
    for r in rows:
        it = by[r['code']]
        pt = it.get('p_touch') or {}
        r['volx'] = it['model_inputs']['volx']
        r['room_up'] = (pt.get('up') or {}).get('dist_sigma')      # 없으면 None = 결측
        r['near_dn'] = (pt.get('dn') or {}).get('dist_sigma')
        r['close'] = it['close']
        r['chg'] = it['chg']
    cols = {'sig': pct([r['sig'] for r in rows]), 'volx': pct([r['volx'] for r in rows])}
    have = [i for i, r in enumerate(rows) if r['room_up'] is not None]
    ru = pct([rows[i]['room_up'] for i in have])
    cols['room_up'] = [None] * len(rows)
    for k, i in enumerate(have):
        cols['room_up'][i] = ru[k]
    pair = (('badge', 'sig'), ('volx', 'volx'), ('room_up', 'room_up'))
    for i, r in enumerate(rows):
        num = den = 0.0
        for wk, ck in pair:
            if cols[ck][i] is None:
                continue                      # 결측 항목은 빼고 나머지로 재정규화한다
            num += W[wk] * cols[ck][i] / 100
            den += W[wk]
        r['score'] = round(num / den * 100, 1) if den else 0.0
        r['missing'] = [ck for wk, ck in pair if cols[ck][i] is None]
    rows.sort(key=lambda r: -r['score'])
    return rows


def main():
    date = sys.argv[sys.argv.index('--date') + 1]
    dry = '--dry' in sys.argv
    d = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    ent = next(e for e in d['entries'] if e['asof'] == date)
    p = os.path.join(ROOT, 'report', 'index.html')
    html = open(p, encoding='utf-8').read()

    rows = parse_rows(html)
    if len(rows) != len(ent['items']):
        raise SystemExit('표 %d행 != 항목 %d개' % (len(rows), len(ent['items'])))
    rows = score(rows, ent['items'])

    n_up = sum(1 for r in rows if r['badge'] == '강세')
    n_mid = sum(1 for r in rows if r['badge'] == '중립')
    n_dn = sum(1 for r in rows if r['badge'] == '약세')
    n_kp = sum(1 for i in ent['items'] if i['market'] == 'KOSPI')
    n_kq = len(ent['items']) - n_kp

    print('배지 — 강세 %d · 중립 %d · 약세 %d' % (n_up, n_mid, n_dn))
    print('시장 — KOSPI %d · KOSDAQ %d' % (n_kp, n_kq))
    print('상위 6 (재현 가능 합산)')
    for r in rows[:6]:
        sg = lambda v: '%.2fσ' % v if v is not None else '없음'
        print('  %5.1f점  %-10s %+.2fσ · 거래량 %.2f배 · 위 %s · 아래 %s%s'
              % (r['score'], r['name'], r['sig'], r['volx'], sg(r['room_up']),
                 sg(r['near_dn']), ' · 결측 ' + ','.join(r['missing']) if r['missing'] else ''))
    if dry:
        return 0

    # 치환은 **패턴**으로 한다. 옛 값 리터럴로 짜면 다음 증설 때 또 안 먹는다 —
    # 2026-08-22에 30 → 31 종목으로 늘렸을 때 실제로 그렇게 조용히 실패했다.
    n_all = len(ent['items'])
    # ATR 창은 회차마다 다른데(수집 봉 수) 헤더·푸터·HTML 주석에 **상수로 박혀** 있었다.
    # 2026-09-01 점검에서 셋 다 160봉으로 남아 있었고 실제 값은 170봉이었다.
    bars = max(i['model_inputs']['atr_bars'] for i in ent['items'])
    subs = [
        (r'ATR14\s*\d+봉', 'ATR14 %d봉' % bars, 0),
        (r'(ATR\(14\)\s*Wilder·)\d+봉', r'\g<1>%d봉' % bars, 0),
        (r'(비교 리포트 \()\d{4}-\d{2}-\d{2}( 종가 기준\))', r'\g<1>%s\g<2>' % date, 0),
        (r'강세\s*\d+\s*·\s*중립\s*\d+\s*·\s*약세\s*\d+',
         '강세 %d · 중립 %d · 약세 %d' % (n_up, n_mid, n_dn), 0),
        (r'코스닥\s*\d+\s*종목', '코스닥 %d종목' % n_kq, 0),
        (r'코스피\s*\d+\s*종목', '코스피 %d종목' % n_kp, 0),
        (r'(?<![\d])\d+\s*종목(?=\s*비교 리포트)', '%d종목' % n_all, 0),
        (r'(로스터가?\s*)\d+\s*종목', r'\g<1>%d종목' % n_all, 0),
        # 헤더는 `KRX · <b>30종목</b>` 처럼 태그가 끼어 있다. 태그를 건너뛰고 숫자만 바꾼다.
        (r'(KRX\s*·\s*(?:<b>)?\s*)\d+(\s*종목)', r'\g<1>%d\g<2>' % n_all, 1),
        # "N종목 중 위쪽 주봉 존이 …" 처럼 로스터 전체를 가리키는 서술
        (r'\d+(종목 중 위쪽 주봉 존)', r'%d\g<1>' % n_all, 0),
        (r'(>)\s*\d+\s*(<[^>]*>\s*강세)', r'\g<1>%d\g<2>' % n_up, 1),
        (r'(>)\s*\d+\s*(<[^>]*>\s*중립)', r'\g<1>%d\g<2>' % n_mid, 1),
        (r'(>)\s*\d+\s*(<[^>]*>\s*약세)', r'\g<1>%d\g<2>' % n_dn, 1),
    ]
    hits = 0
    for pat, rep, cnt in subs:
        html, k = re.subn(pat, rep, html, count=cnt)
        hits += k
    if not hits:
        print('경고 — 치환 0건. 본문 문구가 바뀌었는지 확인하라')
    else:
        print('본문 치환 %d건' % hits)
    open(p, 'w', encoding='utf-8').write(html)
    for q in ('stock_comparison_report_%s.html' % date, 'stock_comparison_report.html'):
        open(os.path.join(ROOT, 'report', q), 'w', encoding='utf-8').write(html)
    json.dump({'rows': rows, 'n_up': n_up, 'n_mid': n_mid, 'n_dn': n_dn,
               'n_kp': n_kp, 'n_kq': n_kq},
              open(os.path.join(ROOT, 'data', 'report_rank_%s.json' % date), 'w',
                   encoding='utf-8'), ensure_ascii=False, indent=1)
    print('집계 반영 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main())

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
#   위험조정 초과 40 · 거래량 배수 25 · 위쪽 여유 20 · 아래 지지 근접 15, 각 항목 백분위.
#   위쪽 여유는 저항까지 거리(멀수록 유리), 아래 지지 근접은 지지까지 거리(가까울수록 유리).
#   레벨이 없으면 3.0σ 로 본다(저항 없음 = 여유 최대 / 지지 없음 = 받침 최약).
#
# 사용법
#   python scripts/report_enrich.py --date 2026-08-21 [--dry]

import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
W = {'badge': 40, 'volx': 25, 'room_up': 20, 'near_dn': 15}


def parse_rows(html):
    """일봉 표에서 종목·배지·σ 를 읽는다 — 발행된 값이 기준이다."""
    i = [m.start() for m in re.finditer(r'<table[^>]*>', html)][1]
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
        r['room_up'] = (pt.get('up') or {}).get('dist_sigma', 3.0)
        r['near_dn'] = (pt.get('dn') or {}).get('dist_sigma', 3.0)
        r['close'] = it['close']
        r['chg'] = it['chg']
    cols = {k: pct([r[k] for r in rows]) for k in ('sig', 'volx', 'room_up')}
    cols['near_dn'] = [100 - p for p in pct([r['near_dn'] for r in rows])]
    for i, r in enumerate(rows):
        r['score'] = round(W['badge'] * cols['sig'][i] / 100
                           + W['volx'] * cols['volx'][i] / 100
                           + W['room_up'] * cols['room_up'][i] / 100
                           + W['near_dn'] * cols['near_dn'][i] / 100, 1)
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
        print('  %5.1f점  %-10s %+.2fσ · 거래량 %.2f배 · 위 %.2fσ · 아래 %.2fσ'
              % (r['score'], r['name'], r['sig'], r['volx'], r['room_up'], r['near_dn']))
    if dry:
        return 0

    before = html
    html = html.replace('강세 3 · 중립 16 · 약세 3',
                        '강세 %d · 중립 %d · 약세 %d' % (n_up, n_mid, n_dn))
    html = html.replace('코스닥 9종목', '코스닥 %d종목' % n_kq)
    html = html.replace('코스피 13종목', '코스피 %d종목' % n_kp)
    # 헤더 알약(3 강세 / 16 중립 / 3 약세)
    html = re.sub(r'(>)\s*3\s*(<[^>]*>\s*강세)', r'\g<1>%d\g<2>' % n_up, html, count=1)
    html = re.sub(r'(>)\s*16\s*(<[^>]*>\s*중립)', r'\g<1>%d\g<2>' % n_mid, html, count=1)
    if html == before:
        print('경고 — 바뀐 것이 없다. 문구가 이미 다르다면 패턴을 확인하라')
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

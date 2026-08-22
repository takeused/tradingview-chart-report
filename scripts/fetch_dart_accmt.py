# 회사별 결산월 수집 — 밸류 팩터의 룩어헤드 구멍을 막는다
#
# 왜 있나 (2026-08-22): `fetch_dart_financials.py` 는 사업연도 Y 재무를 (Y+1)-04-30 부터
#   쓸 수 있다고 봤다. **12월 결산을 전제한 규칙**이다. 표본 150사를 재 보니 12월 결산이
#   98.7%, 3월 결산이 1.3% 였다. 3월 결산 회사는 FY 가 3/31 에 끝나 사업보고서가 6월 말에
#   나오는데 4/30 부터 쓰면 **두 달치 룩어헤드**다.
#
#   비중이 작다고 두면 안 된다. 모멘텀도 "작아 보이던" 룩어헤드 하나로 부호가 뒤집혔다.
#   결산월을 받아 `avail = 결산월말 + 4개월` 로 일반화한다(12월 결산은 기존 4/30 과 동일).
#
# 사용법
#   python scripts/fetch_dart_accmt.py            # data/dart_accmt.csv 생성
#   python scripts/fetch_dart_accmt.py --apply    # dart_financials.csv 의 avail 재계산

import csv, os, sys, time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CORP = os.path.join(ROOT, 'data', 'dart_corpcode.csv')
FIN = os.path.join(ROOT, 'data', 'dart_financials.csv')
OUT = os.path.join(ROOT, 'data', 'dart_accmt.csv')
API = 'https://opendart.fss.or.kr/api/company.json'
LAG_MONTHS = 4          # 결산 후 90일 제출 + 한 달 여유


def api_key():
    k = os.environ.get('API_K_DART')
    if k:
        return k.strip()
    p = os.path.join(ROOT, 'API', 'keys.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            if line.strip().startswith('API_K_DART='):
                return line.strip().split('=', 1)[1].strip().strip('"\'')
    raise SystemExit('DART 인증키가 없다.')


def avail_of(year, acc_mt):
    """사업연도 Y · 결산월 M → 사용 가능일. 결산월말 + LAG 개월의 말일 근사."""
    m = int(acc_mt or 12)
    y, mm = year, m + LAG_MONTHS
    while mm > 12:
        mm -= 12
        y += 1
    last = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mm - 1]
    return '%04d-%02d-%02d' % (y, mm, last)


def fetch():
    import requests

    key = api_key()
    codes = {}
    with open(FIN, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            codes[r['code']] = None
    corp = {}
    with open(CORP, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['code'] in codes:
                corp[r['code']] = r['corp_code']

    rows, err = [], 0
    t0 = time.time()
    for i, (code, cc) in enumerate(sorted(corp.items()), 1):
        try:
            j = requests.get(API, params={'crtfc_key': key, 'corp_code': cc}, timeout=20).json()
            rows.append([code, j.get('acc_mt') if j.get('status') == '000' else ''])
        except Exception:
            err += 1
            rows.append([code, ''])
        if i % 300 == 0:
            el = time.time() - t0
            print('  %d/%d · 실패 %d · %.0f초 · 남은 예상 %.0f분'
                  % (i, len(corp), err, el, (el / i) * (len(corp) - i) / 60), flush=True)
        time.sleep(0.02)
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['code', 'acc_mt'])
        w.writerows(rows)
    import collections
    c = collections.Counter(r[1] for r in rows)
    print('완료 — %d사 · 실패 %d · 결산월 분포 %s'
          % (len(rows), err, dict(c.most_common(5))))
    return 0


def apply():
    acc = {}
    with open(OUT, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            acc[r['code']] = r['acc_mt']
    rows, changed = [], 0
    with open(FIN, encoding='utf-8') as f:
        rd = csv.DictReader(f)
        hdr = rd.fieldnames
        for r in rd:
            new = avail_of(int(r['year']), acc.get(r['code']) or 12)
            if new != r['avail']:
                changed += 1
            r['avail'] = new
            rows.append(r)
    with open(FIN, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerows(rows)
    print('avail 재계산 — %d행 중 %d행 변경' % (len(rows), changed))
    return 0


if __name__ == '__main__':
    sys.exit(apply() if '--apply' in sys.argv else fetch())

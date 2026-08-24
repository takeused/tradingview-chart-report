# 무수정 원자료 두 출처를 대조하고 합친다 — KRX Open API(2010~) + 공공데이터포털(2020~)
#
# 왜 있나 (2026-08-24, 4회차): 유니버스가 오염됐던 원인이 "출처가 주는 값의 성격을
#   확인하지 않고 쓴 것"이었다(거래대금 = 수정주가 x 미수정 거래량). 같은 실수를
#   반복하지 않으려면 **합치기 전에 두 출처가 같은 것을 말하는지 재야 한다.**
#
# 검사 둘. 강한 쪽부터 한다.
#   (1) 동일일 교차검증 — KRX 는 2020년 이후도 주므로 겹치는 날을 받아 종목별로
#       종가·상장주식수·시가총액을 직접 대조한다. 경계 연속성보다 훨씬 강한 시험이다.
#   (2) 경계 연속성 — 2019 마지막 거래일과 2020 첫 거래일 사이 상장주식수 비율을 본다.
#       연말연시에 증자·감자가 없었다면 비율은 1 근처에 몰려야 한다.
#
# 합치기는 검사를 통과한 뒤에만 한다(--merge). 겹치는 날짜는 **datago 를 우선**한다 —
#   2020년 이후 검정이 이미 그 위에서 돌았으므로 바꾸면 과거 결과와 대조가 깨진다.
#
# **KONEX 는 뺀다.** datago 에만 있고 KRX 수집분(KOSPI+KOSDAQ)에는 없는 종목이 매 회
#   109~151개인데 전부 KONEX 였다. KONEX 는 **2013-07-01 개장**이라 2010~2013 에는
#   존재조차 하지 않는다. 그대로 합치면 유니버스 정의가 표본 중간에 바뀐다.
#   무시해도 되는 크기가 아니다 — 2026-08-14 기준 KONEX 최대 종목(본시스템즈)이
#   시총 전체 **310위**라 top_n 500·1000 유니버스에 실제로 들어오고, 수익률 패널에도
#   38종목이 겹친다. 시기 일관성을 위해 양쪽에서 모두 제외한다.
#
# 사용법
#   python scripts/merge_krx_marketdata.py --check
#   python scripts/merge_krx_marketdata.py --check --days 2020-01-03,2023-06-16,2026-08-14
#   python scripts/merge_krx_marketdata.py --merge

import argparse, csv, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OLD = os.path.join(ROOT, 'data', 'krx_openapi_marketdata.csv')     # 2010~2019 (KRX, 일별)
# datago 쪽은 **금요일 주간 표본**이다(326일, 2020-01-03~). 일별이 아니다 —
# 대조일을 아무 날짜나 넣으면 "datago 에 없다"만 나온다.
NEW = os.path.join(ROOT, 'data', 'krx_marketdata.csv')             # 2020~     (datago, 주간)
OUT = os.path.join(ROOT, 'data', 'krx_marketdata_full.csv')
HDR = ['date', 'code', 'name', 'mkt', 'close', 'volume', 'value', 'shares', 'mktcap']


def read(path, only_dates=None):
    rows = defaultdict(dict)
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.DictReader(f)
        for d in r:
            if only_dates and d['date'] not in only_dates:
                continue
            rows[d['date']][d['code']] = d
    return rows


def num(s):
    s = (s or '').strip()
    return float(s) if s not in ('', '-') else None


def cross_check(days):
    """같은 날짜를 KRX 에서 새로 받아 datago 와 종목별로 맞춰 본다."""
    from fetch_krx_openapi import api_key
    from krx_backfill import fetch_day

    key = api_key()
    dg = read(NEW, set(days))
    bad = 0
    for day in days:
        if day not in dg:
            print('  %s — datago 에 없다(휴장이거나 적재 전)' % day)
            continue
        got = fetch_day(key, day.replace('-', ''), day)
        kx = {r[1]: r for r in got}
        common = sorted(set(kx) & set(dg[day]))
        if not common:
            print('  %s — 공통 종목이 없다' % day)
            bad += 1
            continue
        diff = {'close': 0, 'shares': 0, 'mktcap': 0, 'volume': 0}
        worst = {}
        for c in common:
            a, b = kx[c], dg[day][c]
            for k, i in (('close', 4), ('volume', 5), ('shares', 7), ('mktcap', 8)):
                x, y = num(a[i]), num(b[k])
                if x is None or y is None or y == 0:
                    continue
                rel = abs(x - y) / abs(y)
                if rel > 1e-6:
                    diff[k] += 1
                    if rel > worst.get(k, (0, None))[0]:
                        worst[k] = (rel, '%s %s: KRX %s vs datago %s' % (c, b['name'], x, y))
        n = len(common)
        print('  %s — 공통 %d종목 · 불일치 종가 %d · 거래량 %d · 상장주식수 %d · 시총 %d'
              % (day, n, diff['close'], diff['volume'], diff['shares'], diff['mktcap']))
        for k, (rel, msg) in sorted(worst.items()):
            print('      최대 %s 편차 %.4f%% — %s' % (k, rel * 100, msg))
        bad += sum(1 for k in ('close', 'shares', 'mktcap') if diff[k] > n * 0.001)
        only_kx = len(set(kx) - set(dg[day]))
        only_dg = len(set(dg[day]) - set(kx))
        print('      한쪽에만 있는 종목 — KRX %d · datago %d' % (only_kx, only_dg))
    return bad


def boundary_check():
    """2019 마지막 거래일 ↔ 2020 첫 거래일 상장주식수 비율."""
    kx = read(OLD)
    dg = read(NEW)
    if not kx or not dg:
        raise SystemExit('두 파일이 다 있어야 한다')
    d0, d1 = max(kx), min(dg)
    print('  경계 — %s(KRX) → %s(datago)' % (d0, d1))
    a, b = kx[d0], dg[d1]
    common = sorted(set(a) & set(b))
    same, moved, missing = 0, [], 0
    for c in common:
        x, y = num(a[c]['shares']), num(b[c]['shares'])
        if x is None or y is None or x == 0:
            missing += 1
            continue
        r = y / x
        if abs(r - 1) < 1e-9:
            same += 1
        else:
            moved.append((r, c, a[c]['name'], x, y))
    print('  공통 %d종목 · 상장주식수 동일 %d (%.1f%%) · 변동 %d · 결측 %d'
          % (len(common), same, 100.0 * same / len(common) if common else 0,
             len(moved), missing))
    moved.sort(key=lambda t: -abs(t[0] - 1))
    for r, c, nm, x, y in moved[:8]:
        print('      %s %s — %.4f배 (%s → %s)' % (c, nm, r, format(int(x), ','), format(int(y), ',')))
    print('  한쪽에만 — KRX %d · datago %d' % (len(set(a) - set(b)), len(set(b) - set(a))))
    return len(moved)


def merge():
    seen = set()
    n, konex = 0, 0
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(HDR)
        # datago 를 먼저 쓴다 — 겹치면 이쪽이 이긴다
        for path in (NEW, OLD):
            with open(path, encoding='utf-8', newline='') as g:
                r = csv.DictReader(g)
                for d in r:
                    if d['mkt'] == 'KONEX':      # 시기 일관성 — 머리말 참조
                        konex += 1
                        continue
                    k = (d['date'], d['code'])
                    if k in seen:
                        continue
                    seen.add(k)
                    w.writerow([d[c] for c in HDR])
                    n += 1
    print('결합 완료 — %s · %s행 (KONEX %s행 제외)'
          % (OUT, format(n, ','), format(konex, ',')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--merge', action='store_true')
    ap.add_argument('--days', default='2020-01-03,2023-06-16,2026-08-14')
    a = ap.parse_args()
    if a.check:
        print('(1) 동일일 교차검증 — KRX 를 새로 받아 datago 와 대조한다')
        bad = cross_check([d for d in a.days.split(',') if d])
        print('\n(2) 경계 연속성')
        boundary_check()
        if bad:
            print('\n⚠️ 교차검증에서 불일치가 있다. 합치기 전에 원인을 봐야 한다.')
        else:
            print('\n교차검증 통과.')
    if a.merge:
        merge()
    return 0


if __name__ == '__main__':
    sys.exit(main())

# KRX Open API 로 2010~ 무수정 원자료를 받아 krx_marketdata.csv 앞 구간을 채운다
#
# 왜 있나 (2026-08-24, 4회차): 공공데이터포털(API_K_DATAGO)은 2020-01-02 까지만 준다.
#   그 앞은 수정계수 f 를 못 구해 유니버스가 오염됐고, 그래서 밸류 검정 표본이 6.4년뿐이었다.
#   KRX Open API 이용신청이 승인되어 2010-01-04 부터 같은 성격의 무수정 원자료가 열렸다.
#   주력 패널(panel_weekly_krx15)이 2010-01 부터이므로 이걸로 전 구간이 맞물린다.
#
# 출력은 기존 `data/krx_marketdata.csv` 와 **같은 스키마**다. 합치는 게 목적이기 때문이다.
#   date,code,name,mkt,close,volume,value,shares,mktcap  (date 는 기존 파일과 같은 YYYY-MM-DD)
#
# 이어받기 — 이미 받은 날짜는 건너뛴다. 중간에 끊겨도 다시 돌리면 된다.
#
# 사용법
#   python scripts/krx_backfill.py --from 2010-01-04 --to 2019-12-31
#   python scripts/krx_backfill.py --from 2010-01-04 --to 2019-12-31 --out data/krx_openapi_marketdata.csv

import argparse, csv, os, sys, time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_krx_openapi import api_key, HOSTS, PATHS

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
HDR = ['date', 'code', 'name', 'mkt', 'close', 'volume', 'value', 'shares', 'mktcap']
HOST = HOSTS[0]


def num(s):
    """KRX 는 숫자를 콤마 낀 문자열로 준다. 빈 값·'-' 는 0 이 아니라 빈칸으로 남긴다."""
    s = (s or '').replace(',', '').strip()
    if s in ('', '-'):
        return ''
    return s


def fetch_day(key, ymd, iso):
    """하루치를 두 시장에서 받아 표준 행으로 만든다. 휴장일이면 빈 리스트가 온다."""
    import requests

    out = []
    for mkt, path in PATHS:
        for attempt in range(4):
            try:
                r = requests.get(HOST + path, params={'basDd': ymd},
                                 headers={'AUTH_KEY': key, 'User-Agent': 'Mozilla/5.0'},
                                 timeout=60)
            except Exception as e:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code != 200:
                if attempt == 3:
                    raise SystemExit('%s %s HTTP %d %s' % (ymd, mkt, r.status_code, r.text[:120]))
                time.sleep(2 * (attempt + 1))
                continue
            rows = r.json().get('OutBlock_1', [])
            for d in rows:
                out.append([iso, d['ISU_CD'], d['ISU_NM'], mkt,
                            num(d.get('TDD_CLSPRC')), num(d.get('ACC_TRDVOL')),
                            num(d.get('ACC_TRDVAL')), num(d.get('LIST_SHRS')),
                            num(d.get('MKTCAP'))])
            break
        time.sleep(0.2)
    return out


def done_days(path):
    if not os.path.exists(path):
        return set()
    seen = set()
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if row:
                seen.add(row[0])
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='d0', required=True)
    ap.add_argument('--to', dest='d1', required=True)
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'krx_openapi_marketdata.csv'))
    a = ap.parse_args()

    key = api_key()
    d0 = date(*map(int, a.d0.split('-')))
    d1 = date(*map(int, a.d1.split('-')))
    seen = done_days(a.out)
    print('출력 %s — 이미 받은 날짜 %d일' % (a.out, len(seen)))

    new = not os.path.exists(a.out)
    f = open(a.out, 'a', encoding='utf-8', newline='')
    w = csv.writer(f)
    if new:
        w.writerow(HDR)

    d, days, rows, holidays = d0, 0, 0, 0
    t0 = time.time()
    while d <= d1:
        if d.weekday() >= 5:            # 토·일은 부르지 않는다. 휴장일은 응답으로 가려낸다.
            d += timedelta(days=1)
            continue
        ymd, iso = d.strftime('%Y%m%d'), d.isoformat()
        if iso in seen:
            d += timedelta(days=1)
            continue
        got = fetch_day(key, ymd, iso)
        if got:
            w.writerows(got)
            rows += len(got)
        else:
            holidays += 1
        days += 1
        if days % 25 == 0:
            f.flush()
            el = time.time() - t0
            print('  %s 까지 · 요청 %d일 · %d행 · 휴장 %d일 · %.0f분 경과'
                  % (ymd, days, rows, holidays, el / 60), flush=True)
        d += timedelta(days=1)
    f.close()
    print('완료 — 요청 %d일 · %d행 · 휴장 %d일 · %.1f분'
          % (days, rows, holidays, (time.time() - t0) / 60))
    return 0


if __name__ == '__main__':
    sys.exit(main())

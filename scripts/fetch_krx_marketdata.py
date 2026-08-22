# 시점별 시가총액·거래대금 원자료 수집 — 유니버스 오염을 근본에서 없앤다
#
# 왜 있나 (2026-08-22, 2회차): 지금까지 유니버스를 `수정주가 x 거래량` 으로 만든 거래대금
#   상위 N 으로 정의했는데, **가격은 수정되고 거래량은 수정되지 않아** 미래 액면분할·감자
#   정보가 새어 들어왔다(자세한 진단은 study_universe_audit.py 머리말).
#   공공데이터포털 금융위원회_주식시세정보는 **무수정 원자료**로 거래대금·상장주식수·
#   시가총액을 일자별로 준다. 이걸 받으면 우회로(수정계수 복원) 자체가 필요 없다.
#
# 인증키 — 공공데이터포털에서 받은 **Decoding 키**를 다음 중 한 곳에 둔다(둘 다 .gitignore).
#   1) 환경변수 `API_K_DATAGO`  (기존 `API_K_DART` 와 같은 방식)
#   2) 파일 `API/keys.env` 안에 `API_K_DATAGO=발급받은키` 한 줄
#
# 사용법
#   python scripts/fetch_krx_marketdata.py --probe        # 소급 범위·폐지종목 포함 여부 확인
#   python scripts/fetch_krx_marketdata.py --from 2010-01-01 --to 2026-08-21
#   중단돼도 다시 돌리면 이미 받은 날짜는 건너뛴다(재개 가능).

import csv, os, sys, time
from datetime import datetime, timedelta

BASE = 'https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo'
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'data', 'krx_marketdata.csv')
HDR = ['date', 'code', 'name', 'mkt', 'close', 'volume', 'value', 'shares', 'mktcap']
ROWS = 1000


def api_key():
    k = os.environ.get('API_K_DATAGO') or os.environ.get('DATA_GO_KR_KEY')
    if k:
        return k.strip()
    path = os.path.join(ROOT, 'API', 'keys.env')
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line.startswith('API_K_DATAGO=') and len(line) > 13:
                return line.split('=', 1)[1].strip().strip('"\'')
    raise SystemExit('인증키가 없다. 환경변수 API_K_DATAGO 또는 API/keys.env 에 넣어라.')


def fetch_day(key, ymd, page=1):
    """하루치 한 페이지. (행 목록, 전체건수) 를 준다."""
    import requests

    p = {'serviceKey': key, 'resultType': 'json', 'numOfRows': ROWS,
         'pageNo': page, 'basDt': ymd}
    r = requests.get(BASE, params=p, timeout=30)
    r.raise_for_status()
    j = r.json()['response']
    head = j.get('header', {})
    if head.get('resultCode') not in ('00', '000', None):
        raise RuntimeError('%s %s' % (head.get('resultCode'), head.get('resultMsg')))
    body = j.get('body', {})
    items = body.get('items', {})
    it = items.get('item', []) if isinstance(items, dict) else []
    if isinstance(it, dict):
        it = [it]
    return it, int(body.get('totalCount', 0))


def rows_of(items):
    out = []
    for x in items:
        try:
            out.append([x['basDt'][:4] + '-' + x['basDt'][4:6] + '-' + x['basDt'][6:],
                        x['srtnCd'][-6:], x.get('itmsNm', ''), x.get('mrktCtg', ''),
                        int(float(x['clpr'])), int(float(x['trqu'])), int(float(x['trPrc'])),
                        int(float(x['lstgStCnt'])), int(float(x['mrktTotAmt']))])
        except (KeyError, ValueError, TypeError):
            continue
    return out


def fridays(d_from, d_to):
    d = datetime.strptime(d_from, '%Y-%m-%d')
    d += timedelta(days=(4 - d.weekday()) % 7)          # 첫 금요일로
    end = datetime.strptime(d_to, '%Y-%m-%d')
    while d <= end:
        yield d.strftime('%Y%m%d')
        d += timedelta(days=7)


def probe(key):
    """소급 범위와 폐지 종목 포함 여부를 먼저 확인한다 — 받기 전에 알아야 한다."""
    print('소급 범위 확인 — 기준일자별 응답 건수')
    for ymd in ('20100108', '20120106', '20150109', '20180105', '20211119', '20260821'):
        try:
            it, total = fetch_day(key, ymd, 1)
            names = [x.get('itmsNm', '') for x in it[:3]]
            print('  %s · 전체 %6d건 · 예시 %s' % (ymd, total, names))
        except Exception as e:
            print('  %s · 실패 — %s' % (ymd, e))
        time.sleep(0.2)

    print('\n폐지 종목 확인 — 대우조선해양(042660, 2025 상장폐지 여부 무관하게 과거 조회)')
    for ymd in ('20150109', '20200103'):
        try:
            import requests
            p = {'serviceKey': key, 'resultType': 'json', 'numOfRows': 5, 'pageNo': 1,
                 'basDt': ymd, 'likeSrtnCd': '042660'}
            j = requests.get(BASE, params=p, timeout=30).json()['response']['body']
            it = j.get('items', {}).get('item', [])
            if isinstance(it, dict):
                it = [it]
            for x in it:
                print('  %s %s %s 종가 %s · 거래대금 %s · 상장주식수 %s · 시총 %s'
                      % (ymd, x.get('srtnCd'), x.get('itmsNm'), x.get('clpr'),
                         x.get('trPrc'), x.get('lstgStCnt'), x.get('mrktTotAmt')))
            if not it:
                print('  %s · 해당 없음' % ymd)
        except Exception as e:
            print('  %s · 실패 — %s' % (ymd, e))
        time.sleep(0.2)
    return 0


def done_dates(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as f:
        return {r['date'].replace('-', '') for r in csv.DictReader(f)}


def main():
    key = api_key()
    if '--probe' in sys.argv:
        return probe(key)

    d_from = sys.argv[sys.argv.index('--from') + 1] if '--from' in sys.argv else '2010-01-01'
    d_to = sys.argv[sys.argv.index('--to') + 1] if '--to' in sys.argv else '2026-08-21'
    have = done_dates(OUT)
    todo = [d for d in fridays(d_from, d_to) if d not in have]
    print('금요일 %d일 중 받을 것 %d일' % (len(list(fridays(d_from, d_to))), len(todo)), flush=True)

    new = not os.path.exists(OUT)
    f = open(OUT, 'a', encoding='utf-8', newline='')
    w = csv.writer(f)
    if new:
        w.writerow(HDR)

    ok = empty = err = 0
    t0 = time.time()
    for i, ymd in enumerate(todo, 1):
        try:
            got, total = fetch_day(key, ymd, 1)
            page = 1
            while len(got) < total and page < 20:
                page += 1
                more, _ = fetch_day(key, ymd, page)
                if not more:
                    break
                got += more
                time.sleep(0.05)
            rs = rows_of(got)
            if rs:
                w.writerows(rs)
                ok += 1
            else:
                empty += 1          # 휴장일
        except Exception as e:
            err += 1
            if err <= 3:
                print('  %s 실패 — %s' % (ymd, e), flush=True)
        if i % 25 == 0:
            f.flush()
            el = time.time() - t0
            print('  %d/%d · 수집 %d · 휴장 %d · 실패 %d · %.0f초 · 남은 예상 %.0f분'
                  % (i, len(todo), ok, empty, err, el, (el / i) * (len(todo) - i) / 60), flush=True)
        time.sleep(0.05)
    f.close()
    print('완료 — 수집 %d일 · 휴장 %d · 실패 %d · %s' % (ok, empty, err, OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())

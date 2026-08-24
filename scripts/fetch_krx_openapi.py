# KRX Open API 수집 — 공공데이터 API 가 못 주는 2020년 이전 구간을 노린다
#
# 왜 있나 (2026-08-22, 3회차): 금융위원회_주식시세정보는 무수정 원자료를 주지만 소급이
#   **2020-01-02 까지**다. 그 앞은 수정계수 f 를 못 구해 유니버스가 오염된다
#   (진단 전문은 study_universe_audit.py 머리말). KRX Open API 가 더 과거를 주면
#   15.6년 패널 전체를 깨끗하게 쓸 수 있다.
#
#   **그래서 받기 전에 소급 범위부터 잰다.** 안 되면 대안(DART 증자·감자 현황)으로 간다.
#
# 인증키 — `API/keys.env` 의 `KRX_API_KEY=` 또는 환경변수 `KRX_API_KEY`.
#
# 401 이 두 종류다 (2026-08-24 확인). 헷갈리면 엉뚱한 데를 고치게 된다.
#   "Unauthorized Key"      → 키를 못 알아본다. 오타·미저장·미발급.
#   "Unauthorized API Call" → 키는 유효한데 그 API 에 **이용신청**이 안 걸려 있다.
#     인증키 발급 승인과 API 별 이용신청(1M/3M/6M/12M)은 별개 단계다. 서비스 목록
#     https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd 에서 신청한다.
#
# 소급 범위는 문서상 stk_bydd_trd·ksq_bydd_trd 둘 다 **2010-01-04** 부터다.
# 응답 컬럼에 MKTCAP·LIST_SHRS·ACC_TRDVAL 이 있어 universe_pit 요구를 그대로 채운다.
#
# 사용법
#   python scripts/fetch_krx_openapi.py --probe
#   python scripts/fetch_krx_openapi.py --from 2010-01-01 --to 2019-12-31

import csv, os, sys, time
from datetime import datetime, timedelta

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'data', 'krx_openapi_marketdata.csv')
HDR = ['date', 'code', 'name', 'mkt', 'close', 'volume', 'value', 'shares', 'mktcap']

# KRX Open API — 시장별 일별매매정보
HOSTS = ['https://data-dbg.krx.co.kr/svc/apis', 'http://data-dbg.krx.co.kr/svc/apis']
# KRX 문서의 공개 테스트 엔드포인트 + 공개 샘플키. 우리 코드가 멀쩡한지 가르는 대조군이다.
SAMPLE = ('https://data-dbg.krx.co.kr/svc/sample/apis', '74D1B99DFBF345BBA3FB4476510A4BED4C78D13A')
PATHS = [('KOSPI', '/sto/stk_bydd_trd'), ('KOSDAQ', '/sto/ksq_bydd_trd')]


def api_key():
    k = os.environ.get('KRX_API_KEY')
    if k:
        return k.strip()
    path = os.path.join(ROOT, 'API', 'keys.env')
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line.startswith('KRX_API_KEY=') and len(line) > 12:
                return line.split('=', 1)[1].strip().strip('"\'')
    raise SystemExit('KRX 인증키가 없다. API/keys.env 의 KRX_API_KEY= 뒤에 넣어라.')


def call(key, host, path, ymd):
    import requests

    r = requests.get(host + path, params={'basDd': ymd},
                     headers={'AUTH_KEY': key, 'User-Agent': 'Mozilla/5.0'}, timeout=30)
    if r.status_code != 200:
        return None, 'HTTP %d %s' % (r.status_code, r.text[:120].replace('\n', ' '))
    try:
        j = r.json()
    except ValueError:
        return None, '비JSON: ' + r.text[:120].replace('\n', ' ')
    for k in ('OutBlock_1', 'output', 'OutBlock1', 'data'):
        if isinstance(j, dict) and k in j:
            return j[k], None
    return None, '알 수 없는 응답 구조: %s' % list(j)[:6]


def probe(key):
    # 먼저 대조군 — 샘플키가 200 을 주면 헤더·호스트·파서는 무죄다.
    host, path = SAMPLE[0], PATHS[0][1]
    rows, err = call(SAMPLE[1], host, path, '20240105')
    print('대조군(공개 샘플키) → %s' % ('행 %d, 클라이언트 정상' % len(rows) if rows else err))
    rows, err = call(key, host, path, '20240105')
    print('대조군(우리 키)     → %s' % ('행 %d' % len(rows) if rows else err))
    if err and 'Unauthorized API Call' in err:
        print('  -> 키는 유효하나 이 API 에 이용신청이 없다. 서비스 목록에서 신청할 것.')
    elif err and 'Unauthorized Key' in err:
        print('  -> 키 자체를 못 알아본다. API/keys.env 의 KRX_API_KEY 를 확인할 것.')
    print()

    print('엔드포인트 확인')
    live = None
    for host in HOSTS:
        for mkt, path in PATHS[:1]:
            rows, err = call(key, host, path, '20240105')
            print('  %-45s → %s' % (host + path, '행 %d' % len(rows) if rows is not None else err))
            if rows:
                live = (host, path)
                print('     컬럼: %s' % list(rows[0])[:14])
            time.sleep(0.3)
        if live:
            break
    if not live:
        print('\n응답을 못 받았다. 키 승인 상태와 엔드포인트를 확인해야 한다.')
        return 1

    host, path = live
    print('\n소급 범위 확인 — 기준일자별 응답 건수')
    for ymd in ('20100108', '20120106', '20150109', '20180105', '20191227',
                '20200103', '20240105', '20260820'):
        rows, err = call(key, host, path, ymd)
        print('  %s → %s' % (ymd, ('%5d건' % len(rows)) if rows is not None else err))
        time.sleep(0.3)
    return 0


def main():
    key = api_key()
    if '--probe' in sys.argv or len(sys.argv) == 1:
        return probe(key)
    print('수집 모드는 probe 로 소급 범위를 확인한 뒤 붙인다.')
    return 1


if __name__ == '__main__':
    sys.exit(main())

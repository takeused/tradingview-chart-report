# DART 재무제표 수집 — 밸류·퀄리티 팩터용
#
# 왜 있나 (2026-08-22, 3회차): 등록부에 밸류(PBR·PER)와 퀄리티(ROE·영업수익성·부채비율)를
#   넣으려면 재무제표가 필요하다. DART 다중회사 주요계정(fnlttMultiAcnt)은 한 번에
#   100개 법인을 받으므로 2,500종목 × 8개년이 200여 회 호출로 끝난다.
#
# **룩어헤드 차단이 이 스크립트의 존재 이유다.**
#   재무제표는 결산일이 아니라 **공시된 뒤에야** 알 수 있다. 사업보고서는 결산 후 90일
#   이내 제출이라 12월 결산 법인의 FY2023 은 2024-03 말에 나온다. 여기서는 한 달을 더
#   얹어 **다음 해 4월 30일부터 사용 가능**으로 본다(AVAIL_MMDD). 늦게 내는 법인과
#   정정공시를 감안한 보수적 처리다. 이 한 줄을 빼먹으면 "미래의 실적으로 과거를 산" 것이
#   되어 모멘텀 때와 같은 방식으로 결과가 뒤집힌다.
#
# 인증키 — 환경변수 `API_K_DART` 또는 `API/keys.env` 의 `API_K_DART=`.
#
# 사용법
#   python scripts/fetch_dart_financials.py [--from-year 2015] [--to-year 2025]
#
# 소급 한계 — DART 다중회사 주요계정은 **FY2015 부터**다(2014 이하는 0행, 2026-08-24 확인).
#   그래서 밸류 검정은 (2015+1)-04-30 = **2016-04-30** 부터 설 수 있다. 가격 데이터가
#   2010년까지 있어도 여기가 병목이다.

import csv, os, sys, time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'data', 'dart_financials.csv')
CORP = os.path.join(ROOT, 'data', 'dart_corpcode.csv')
API = 'https://opendart.fss.or.kr/api/fnlttMultiAcnt.json'
BATCH = 100
AVAIL_MMDD = '-04-30'      # FY Y 는 (Y+1)-04-30 부터 사용 가능으로 본다

WANT = {'자산총계': 'assets', '부채총계': 'debt', '자본총계': 'equity',
        '매출액': 'sales', '영업이익': 'opinc', '당기순이익(손실)': 'netinc'}
HDR = ['code', 'year', 'avail', 'fs', 'assets', 'debt', 'equity', 'sales', 'opinc', 'netinc']


def api_key():
    k = os.environ.get('API_K_DART')
    if k:
        return k.strip()
    p = os.path.join(ROOT, 'API', 'keys.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            if line.strip().startswith('API_K_DART=') and len(line.strip()) > 11:
                return line.strip().split('=', 1)[1].strip().strip('"\'')
    raise SystemExit('DART 인증키가 없다(API_K_DART).')


def num(s):
    s = (s or '').replace(',', '').strip()
    if not s or s == '-':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def universe_codes():
    """마켓데이터에 등장하는 종목 중 DART 법인코드가 있는 것.

    **전 구간 시장데이터를 쓴다(2026-08-24 수정).** 원래 2020년 이후만 담긴
    krx_marketdata.csv 를 봤는데, 그러면 2020년 전에 상장폐지된 회사가 대상에서
    통째로 빠진다 — 살아남은 회사만 재무를 갖게 되어 **생존편향**이 들어간다.
    검정 구간이 2016년까지 내려가므로 그때 살아 있던 회사가 모두 필요하다.
    """
    md = os.path.join(ROOT, 'data', 'krx_marketdata_full.csv')
    if not os.path.exists(md):
        md = os.path.join(ROOT, 'data', 'krx_marketdata.csv')
    have = set()
    if os.path.exists(md):
        with open(md, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                have.add(r['code'])
    m = {}
    with open(CORP, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['code'] in have:
                m[r['corp_code']] = r['code']
    return m


def fetch(key, corps, year, reprt='11011'):
    import requests

    r = requests.get(API, params={'crtfc_key': key, 'corp_code': ','.join(corps),
                                  'bsns_year': str(year), 'reprt_code': reprt}, timeout=60)
    j = r.json()
    if j.get('status') not in ('000', '013'):        # 013 = 조회된 데이타 없음
        raise RuntimeError('%s %s' % (j.get('status'), j.get('message')))
    return j.get('list', [])


def main():
    key = api_key()
    y0 = int(sys.argv[sys.argv.index('--from-year') + 1]) if '--from-year' in sys.argv else 2015
    y1 = int(sys.argv[sys.argv.index('--to-year') + 1]) if '--to-year' in sys.argv else 2025

    cmap = universe_codes()
    corps = sorted(cmap)
    print('대상 법인 %d개 · 사업연도 %d~%d · 배치 %d' % (len(corps), y0, y1, BATCH), flush=True)

    rows, ok, err = [], 0, 0
    t0 = time.time()
    jobs = [(y, corps[i:i + BATCH]) for y in range(y0, y1 + 1)
            for i in range(0, len(corps), BATCH)]
    for n, (year, chunk) in enumerate(jobs, 1):
        try:
            got = fetch(key, chunk, year)
            # 법인·재무제표구분별로 모아 한 줄로 만든다. 연결(CFS) 우선, 없으면 개별(OFS).
            acc = {}
            for x in got:
                nm = x.get('account_nm')
                if nm not in WANT:
                    continue
                k = (x['corp_code'], x.get('fs_div', 'OFS'))
                v = num(x.get('thstrm_amount'))
                if v is not None:
                    acc.setdefault(k, {})[WANT[nm]] = v
            for corp in chunk:
                d = acc.get((corp, 'CFS')) or acc.get((corp, 'OFS'))
                if not d or 'equity' not in d:
                    continue
                fs = 'CFS' if (corp, 'CFS') in acc else 'OFS'
                rows.append([cmap[corp], year, str(year + 1) + AVAIL_MMDD, fs] +
                            [d.get(f) for f in ('assets', 'debt', 'equity', 'sales', 'opinc', 'netinc')])
            ok += 1
        except Exception as e:
            err += 1
            if err <= 3:
                print('  %d년 배치 실패 — %s' % (year, e), flush=True)
        if n % 20 == 0:
            el = time.time() - t0
            print('  %d/%d · 성공 %d · 실패 %d · 누적 %d행 · %.0f초 · 남은 예상 %.0f분'
                  % (n, len(jobs), ok, err, len(rows), el, (el / n) * (len(jobs) - n) / 60), flush=True)
        time.sleep(0.05)

    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(HDR)
        w.writerows(rows)
    codes = len({r[0] for r in rows})
    print('완료 — %d행 · %d종목 · %s' % (len(rows), codes, OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())

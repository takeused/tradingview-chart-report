# KRX 전 종목(상장폐지 포함) 주봉 패널을 만든다 — 시점별(point-in-time) 검정용
#
# 왜 있나 (2026-08-22): TradingView 스크리너로 만든 유니버스는 **오늘 기준 시총 상위**라
#   과거 구간에 두 가지 편향이 있다.
#     (a) 생존편향 — 그 사이 상장폐지된 종목이 통째로 빠져 있다
#     (b) 유니버스 룩어헤드 — 그동안 커진 종목이 처음부터 목록에 들어가 있다
#   둘 다 **모멘텀(과거 상승 종목 매수)** 검정에는 가짜 수익을 만드는 방향이다.
#   여기서 무너지면 지금까지의 모멘텀 결과를 폐기해야 하므로, 다른 걸 더 쌓기 전에 확인한다.
#
# 어떻게 푸는가
#   - FinanceDataReader 로 **현재 상장 주권 + 검정 구간에 폐지된 주권**을 모두 받는다.
#     (pykrx 는 2026 기준 KRX 계정 로그인을 요구해서 쓰지 않는다)
#   - 유니버스는 시총이 아니라 **직전 12주 평균 거래대금 상위 N** 으로 정의한다.
#     과거 시점의 상장주식수를 못 구해 시총을 시점별로 재구성하기 어렵고,
#     거래대금은 관측값만으로 계산되며 매매 가능성(비용)과도 직결된다.
#
# 사용법
#   python scripts/fetch_krx_history.py [--from 2020-10-01] [--to 2026-08-21]
#   중단돼도 다시 돌리면 이미 받은 종목은 건너뛴다(재개 가능).
#
#   python scripts/fetch_krx_history.py --update --to 2026-08-28
#   갱신 모드 — 종목별 마지막 주 이후만 받아 이어 붙인다. 전진 추적(원장 pending 승격)에
#   매주 필요하다. 기본 모드는 이미 받은 종목을 통째로 건너뛰므로 새 주가 한 줄도 안 붙는다.
#   마지막 주봉은 미완성 주였을 수 있으므로 **다시 받아 덮어쓴다**.
#   장기 무거래(--stale-weeks 주 이상, 기본 12) 종목은 폐지·거래정지로 보고 건너뛴다.
#
#   --out data/panel_weekly_krx15.csv 로 다른 패널 파일에 받을 수 있다(표본 기간별 병행 보관).

import csv, os, sys, time
from datetime import datetime, timedelta

FROM, TO = '2020-10-01', '2026-08-21'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'panel_weekly_krx.csv')
HDR = ['code', 'mkt', 'date', 'open', 'high', 'low', 'close', 'volume']


def universe(d_from, d_to):
    """검정 구간에 한 번이라도 상장돼 있던 보통주 목록."""
    import pandas as pd
    import FinanceDataReader as fdr

    cur = fdr.StockListing('KRX')
    cur = cur[cur['Market'].isin(['KOSPI', 'KOSDAQ'])]
    cur = cur[cur['Code'].str.endswith('0')]                 # 우선주 제외
    cur = cur[~cur['Name'].str.contains('스팩', na=False)]
    live = [(r.Code, r.Market) for r in cur.itertuples()]

    de = fdr.StockListing('KRX-DELISTING')
    de['DelistingDate'] = pd.to_datetime(de['DelistingDate'], errors='coerce')
    de = de[(de['SecuGroup'] == '주권') & de['Market'].isin(['KOSPI', 'KOSDAQ'])]
    de = de[(de['DelistingDate'] >= d_from) & (de['DelistingDate'] <= d_to)]
    de = de[de['Symbol'].str.endswith('0')]
    de = de[~de['Name'].str.contains('스팩', na=False)]
    dead = [(r.Symbol, r.Market) for r in de.itertuples()]

    seen, out = set(), []
    for code, mkt in live + dead:
        if code in seen:
            continue
        seen.add(code)
        out.append((code, mkt))
    return out, len(live), len(dead)


def done_codes(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as f:
        return {r['code'] for r in csv.DictReader(f)}


def weekly_rows(fdr, code, mkt, d_from, d_to):
    """일봉을 받아 금요일 마감 주봉으로 재표본한 행 목록."""
    df = fdr.DataReader(code, d_from, d_to)
    if df is None or df.empty:
        return []
    wk = df.resample('W-FRI').agg({'Open': 'first', 'High': 'max', 'Low': 'min',
                                   'Close': 'last', 'Volume': 'sum'}).dropna()
    return [[code, mkt, ts.strftime('%Y-%m-%d'),
             int(r.Open), int(r.High), int(r.Low), int(r.Close), int(r.Volume)]
            for ts, r in wk.iterrows()]


def update(d_to, stale_weeks):
    """종목별 마지막 주 이후만 받아 패널을 다시 쓴다."""
    import FinanceDataReader as fdr

    if not os.path.exists(OUT):
        print('패널이 없다. 갱신 모드 대신 전체 수집으로 돌려라.', file=sys.stderr)
        return 1

    rows, last, mkt_of = [], {}, {}
    with open(OUT, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append([r[k] for k in HDR])
            if r['date'] > last.get(r['code'], ''):
                last[r['code']] = r['date']
            mkt_of[r['code']] = r['mkt']

    cut = (datetime.strptime(d_to, '%Y-%m-%d') - timedelta(weeks=stale_weeks)).strftime('%Y-%m-%d')
    todo = sorted(c for c, d in last.items() if d >= cut and d < d_to)
    stale = len(last) - len(todo) - sum(1 for d in last.values() if d >= d_to)
    print('패널 %d행 · %d종목 · 갱신대상 %d · 무거래건너뜀 %d (기준 %s 이전)'
          % (len(rows), len(last), len(todo), stale, cut), flush=True)

    add, ok, err = {}, 0, 0
    t0 = time.time()
    for i, code in enumerate(todo, 1):
        # 마지막 주봉은 미완성이었을 수 있으므로 그 주 월요일부터 다시 받는다
        start = (datetime.strptime(last[code], '%Y-%m-%d') - timedelta(days=6)).strftime('%Y-%m-%d')
        try:
            got = [r for r in weekly_rows(fdr, code, mkt_of[code], start, d_to)
                   if r[2] >= last[code]]
            if got:
                add[code] = got
                ok += 1
        except Exception:
            err += 1
        if i % 100 == 0:
            el = time.time() - t0
            print('  %d/%d · 갱신 %d · 실패 %d · %.0f초 경과 · 남은 예상 %.0f분'
                  % (i, len(todo), ok, err, el, (el / i) * (len(todo) - i) / 60), flush=True)

    kept = [r for r in rows if not (r[0] in add and r[2] >= last[r[0]])]
    out = kept + [r for code in add for r in add[code]]
    out.sort(key=lambda r: (r[0], r[2]))

    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(HDR)
        w.writerows(out)
    os.replace(tmp, OUT)

    added = len(out) - len(kept)
    print('갱신 완료 — %d종목 · 새 주봉 %d행(마지막 주 재수집 포함) · 총 %d행 · 실패 %d'
          % (len(add), added, len(out), err))
    return 0


def main():
    d_from = sys.argv[sys.argv.index('--from') + 1] if '--from' in sys.argv else FROM
    d_to = sys.argv[sys.argv.index('--to') + 1] if '--to' in sys.argv else TO
    global OUT
    if '--out' in sys.argv:
        OUT = sys.argv[sys.argv.index('--out') + 1]
    if '--update' in sys.argv:
        sw = int(sys.argv[sys.argv.index('--stale-weeks') + 1]) if '--stale-weeks' in sys.argv else 12
        return update(d_to, sw)
    import FinanceDataReader as fdr

    uni, n_live, n_dead = universe(d_from, d_to)
    have = done_codes(OUT)
    todo = [(c, m) for c, m in uni if c not in have]
    print('유니버스 %d종목 (현재상장 %d + 구간내폐지 %d) · 이미받음 %d · 받을것 %d'
          % (len(uni), n_live, n_dead, len(have), len(todo)), flush=True)

    new = not os.path.exists(OUT)
    f = open(OUT, 'a', encoding='utf-8', newline='')
    w = csv.writer(f)
    if new:
        w.writerow(HDR)

    ok = err = 0
    t0 = time.time()
    for i, (code, mkt) in enumerate(todo, 1):
        try:
            got = weekly_rows(fdr, code, mkt, d_from, d_to)
            if got:
                w.writerows(got)
                ok += 1
            else:
                err += 1
        except Exception:
            err += 1
        if i % 100 == 0:
            f.flush()
            el = time.time() - t0
            print('  %d/%d · 성공 %d · 실패 %d · %.0f초 경과 · 남은 예상 %.0f분'
                  % (i, len(todo), ok, err, el, (el / i) * (len(todo) - i) / 60), flush=True)
    f.close()
    print('완료 — 성공 %d · 실패 %d · %s' % (ok, err, OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())

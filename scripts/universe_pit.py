# 시점별 유니버스 — 무수정 원자료(공공데이터포털)로 정의한다
#
# 왜 있나 (2026-08-22, 2회차): 기존 `pit_pool` 은 거래대금을 `수정주가 x 거래량` 으로 쟀다.
#   가격은 수정되고 거래량은 안 되므로, 나중에 분할한 종목은 과거 거래대금이 축소되고
#   감자한 종목은 부풀려진다 — 유니버스가 미래 corporate action 정보를 담게 된다
#   (진단 전문은 study_universe_audit.py 머리말).
#
#   금융위원회_주식시세정보는 **무수정 원자료**로 시가총액·거래대금을 준다. 여기서 만든
#   유니버스에는 그 통로가 없다. 대신 자료 범위가 **2020-01-02 ~** 로 6.6년뿐이다.
#
# 덤 — API 의 종가(clpr)는 무수정이라 패널의 수정종가로 나누면 **수정계수 f 가 정확히 나온다.**
#   f 를 알면 2010~2019 구간의 거래대금도 되살릴 수 있다(pre_factor 참조).
#
# 사용법 (모듈)
#   from universe_pit import load_market, pool_cap, pool_value

import csv, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
MD = os.path.join(ROOT, 'data', 'krx_marketdata.csv')


def load_market(path=MD):
    """(code, date) -> {cap, value, close}. 무수정 원자료."""
    if not os.path.exists(path):
        raise SystemExit('data/krx_marketdata.csv 가 없다. '
                         'python scripts/fetch_krx_marketdata.py --from 2020-01-01 로 받아라.')
    m = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            m[(r['code'], r['date'])] = {'cap': int(r['mktcap']), 'value': int(r['value']),
                                         'close': int(r['close'])}
    return m


def _rank_pool(P, M, t, top_n, key, back, min_obs):
    """t 시점까지의 관측만 써서 상위 N 을 고른다."""
    scores = []
    for c in P.stocks:
        if P.c[c][t] is None:
            continue
        vals = []
        for k in range(max(0, t - back), t + 1):
            d = M.get((c, P.dates[k]))
            if d and d[key] > 0:
                vals.append(d[key])
        if len(vals) < min_obs:
            continue
        scores.append((sum(vals) / len(vals), c))
    scores.sort(key=lambda x: -x[0])
    return [c for _, c in scores[:top_n]]


def pool_cap(P, M, t, top_n, back=4, min_obs=3):
    """시점별 시가총액 상위 N — 실제 펀드가 쓰는 유니버스 정의."""
    return _rank_pool(P, M, t, top_n, 'cap', back, min_obs)


def pool_value(P, M, t, top_n, back=12, min_obs=8):
    """시점별 거래대금 상위 N — 무수정 원자료 기준(기존 pit_pool 의 올바른 버전)."""
    return _rank_pool(P, M, t, top_n, 'value', back, min_obs)


def adjust_factor(P, M, t):
    """f(c) = 무수정 종가 / 수정 종가. 그 시점 이후의 분할·감자·무상증자 누적 배수다."""
    out = {}
    d = P.dates[t]
    for c in P.stocks:
        a = P.c[c][t]
        m = M.get((c, d))
        if a and m and m['close'] > 0:
            out[c] = m['close'] / a
    return out

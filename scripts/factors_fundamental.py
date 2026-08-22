# 밸류·퀄리티 팩터 — 재무제표를 시점별로 안전하게 붙인다
#
# 왜 있나 (2026-08-22, 3회차): 등록부에 밸류·퀄리티가 없었다. 시가총액을 못 구해
#   PBR·PER 자체를 계산할 수 없었기 때문이다. 무수정 시가총액이 생겨 이제 가능하다.
#
# **룩어헤드 차단** — 재무제표는 공시된 뒤에야 알 수 있다. `dart_financials.csv` 의
#   `avail` 열(사업연도 +1 의 4월 30일)보다 **이후 시점에서만** 그 재무를 쓴다.
#   fetch_dart_financials.py 머리말에 근거를 적었다. 이걸 어기면 "미래 실적으로 과거를 산"
#   결과가 나오고, 모멘텀 때와 같은 방식으로 나중에 전부 뒤집힌다.
#
# 자본잠식·적자 처리 — 자본총계 <= 0 이면 PBR·ROE·부채비율이 뜻을 잃으므로 제외한다.
#   순이익 <= 0 이면 PER 을 제외한다(학계 관행). 제외는 None 을 돌려주는 것으로 한다 —
#   0 이나 큰 수로 채우면 그 종목이 분위 끝에 몰려 결과를 조용히 왜곡한다.

import csv, math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FIN_CSV = os.path.join(ROOT, 'data', 'dart_financials.csv')
FIELDS = ('assets', 'debt', 'equity', 'sales', 'opinc', 'netinc')


def load_financials(path=FIN_CSV):
    """code -> [(avail_date, {계정}), ...] 을 avail 오름차순으로."""
    if not os.path.exists(path):
        raise SystemExit('data/dart_financials.csv 가 없다. '
                         'python scripts/fetch_dart_financials.py 로 받아라.')
    fin = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            d = {}
            for k in FIELDS:
                v = r.get(k, '')
                d[k] = float(v) if v not in ('', 'None') else None
            fin.setdefault(r['code'], []).append((r['avail'], d))
    for c in fin:
        fin[c].sort()
    return fin


def at(fin, code, date):
    """그 시점에 **이미 공시돼 있던** 가장 최근 재무. 없으면 None."""
    seq = fin.get(code)
    if not seq:
        return None
    got = None
    for avail, d in seq:
        if avail <= date:
            got = d
        else:
            break
    return got


def build(fin):
    """등록부에 넣을 {이름: (근거, fn(M, P, c, t, mkt))} 를 만든다."""

    def acc(P, c, t):
        return at(fin, c, P.dates[t])

    def cap(M, P, c, t):
        d = M.get((c, P.dates[t]))
        return d['cap'] if d and d['cap'] > 0 else None

    def ratio(M, P, c, t, key, positive_only):
        """시가총액 대비 배수의 역수 — 쌀수록 큰 점수."""
        f, v = acc(P, c, t), cap(M, P, c, t)
        if not f or v is None or f.get(key) is None:
            return None
        x = f[key]
        if positive_only and x <= 0:
            return None
        return x / v                     # 자본총계/시총 = 1/PBR, 순이익/시총 = 1/PER

    def quality(P, c, t, num_key, den_key, den_positive=True):
        f = acc(P, c, t)
        if not f or f.get(num_key) is None or f.get(den_key) is None:
            return None
        den = f[den_key]
        if den <= 0 if den_positive else den == 0:
            return None
        return f[num_key] / den

    return {
        '저PBR(순자산/시총)': ('Fama-French 1992 HML',
                          lambda M, P, c, t, m: ratio(M, P, c, t, 'equity', True)),
        '저PER(순이익/시총)': ('Basu 1977 — 적자기업 제외',
                          lambda M, P, c, t, m: ratio(M, P, c, t, 'netinc', True)),
        '저PSR(매출/시총)': ('Fisher 1984 매출 대비 저평가',
                        lambda M, P, c, t, m: ratio(M, P, c, t, 'sales', True)),
        '고ROE(순이익/자본)': ('Quality — 수익성',
                          lambda M, P, c, t, m: quality(P, c, t, 'netinc', 'equity')),
        '고영업수익성(영업이익/자산)': ('Novy-Marx 2013 수익성',
                              lambda M, P, c, t, m: quality(P, c, t, 'opinc', 'assets')),
        '저부채비율(자본/부채)': ('Quality — 안전성. 부채 0 이면 최상위',
                           lambda M, P, c, t, m: (lambda f: None if not f or f.get('equity') is None
                                                  or f.get('debt') is None or f['equity'] <= 0
                                                  else math.log(f['equity'] / max(f['debt'], 1.0)))
                                                 (acc(P, c, t))),
    }

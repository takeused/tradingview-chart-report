# 120일 베타를 daily_raw.json 의 rets 로 직접 계산한다 (시장별 지수 대비)
#
# 왜 있나: 회차마다 betas.json 을 이월하면 120일 창이 굳어 버린다. 원자료에 이미
#   rets 가 실려 오므로 매 회차 다시 낸다. 검증은 직전 회차 betas.json 재현으로 한다.

import json, os, sys

SCR = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(os.path.join(sys.argv[1] if len(sys.argv) > 1 else SCR,
                                 'daily_raw.json'), encoding='utf-8'))['metrics']


def beta(rs, ms):
    n = min(len(rs), len(ms))
    rs, ms = rs[-n:], ms[-n:]
    mm = sum(ms) / n
    var = sum((x - mm) ** 2 for x in ms)
    rm = sum(rs) / n
    cov = sum((rs[i] - rm) * (ms[i] - mm) for i in range(n))
    return cov / var if var else 1.0


idx = {'P': raw['KOSPI']['rets'], 'Q': raw['KOSDAQ']['rets']}
out = {}
for code, v in raw.items():
    if code in ('KOSPI', 'KOSDAQ') or 'rets' not in v:
        continue
    out[code] = {'beta': round(beta(v['rets'], idx[v['mkt']]), 2)}
json.dump(out, open(os.path.join(SCR, 'betas.json'), 'w', encoding='utf-8'), indent=1)
print('betas %d' % len(out))

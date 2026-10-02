# 수집 뒤처리 — metrics_daily 에 beta 를 채우고, 주봉 지표를 build_items 형식으로 바꾸고, weekly_desc 를 쓴다
import json, os, sys
S = os.path.dirname(os.path.abspath(__file__))
ROOT = r'D:\01 WORK\260705 Trading View'
DATE = sys.argv[1]
L = lambda n: json.load(open(os.path.join(S, n), encoding='utf-8'))
md, mw, betas = L('metrics_daily.json'), L('metrics_weekly.json'), L('betas.json')
names = {c: n for c, n, _ in L('roster.json')['roster']}

for c, v in md.items():
    if c in betas:
        v['beta'] = betas[c]['beta']
json.dump(md, open(os.path.join(S, 'metrics_daily.json'), 'w', encoding='utf-8'), indent=0)

REN = {'atr': 'watr', 'rngatr': 'wrngatr', 'atrpct': 'watrpct', 'chg': 'wchg',
       'mom4': 'm4', 'mom12': 'm12', 'streak': 'wstreak'}
out, desc = {}, {}
for c, v in mw.items():
    w = dict(v)
    for a, b in REN.items():
        if a in w:
            w[b] = w.pop(a)
    out[c] = w
    if c in names and not w.get('err'):
        dd = dict(w, code=c, name=names[c])
        desc[c] = dd
json.dump(out, open(os.path.join(S, 'metrics_weekly.json'), 'w', encoding='utf-8'), indent=0)

# 주봉 지표가 없는 종목(신규 상장)은 직전 회차 서술값이 아니라 일봉 종가만으로는 못 채운다 — 알린다
miss = [c for c in names if c not in desc]
prev = json.load(open(os.path.join(ROOT, 'data', 'weekly_desc_2026-10-01.json'), encoding='utf-8'))
print('weekly_desc %d · 결측 %s · 직전 결측 %s' % (len(desc), miss, [c for c in names if c not in prev]))
json.dump(desc, open(os.path.join(ROOT, 'data', 'weekly_desc_%s.json' % DATE), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=0)
k = sorted(set(prev[next(iter(prev))]) ^ set(desc[next(iter(desc))]))
print('키 차이(직전 vs 오늘):', k)

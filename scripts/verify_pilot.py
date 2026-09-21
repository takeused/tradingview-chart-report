# 파일럿 회귀 검증 — 리플레이로 되감아 받은 광역 수집이 그날 기록과 같은가
#
# 9/18 은 이미 현행 규격(9/10 존·라인 분리) 아래 회차라, **같은 값이 나와야 한다.**
# 어긋나면 리플레이가 그 시점의 존·라인을 못 되감았다는 뜻이고 6시간을 쓸 이유가 없다.
import json, os, sys

ROOT = r'D:\01 WORK\260705 Trading View'
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_items as bi

DATE = sys.argv[1] if len(sys.argv) > 1 else '2026-09-18'

g = json.load(open(os.path.join(S, 'wide', 'room_%s.json' % DATE), encoding='utf-8'))
pred = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
e = next(x for x in pred['entries'] if x['asof'] == DATE)

ok = bad = miss = 0
rows = []
for it in e['items']:
    c = it['code']
    if c not in g or g[c].get('err'):
        miss += 1
        continue
    v = g[c]
    if v.get('sym', '').split(':')[-1] != c:
        rows.append((c, it['name'], '심볼 불일치 %s' % v.get('sym')))
        bad += 1
        continue
    rec = (it['p_touch'].get('up') or {})
    pick = bi.pick_level(v['c'], v['a'], v.get('zones'), v.get('lines'), 'up')
    same_px = abs(v['c'] - it['close']) < 1e-6
    same_atr = abs(round(v['a']) - it['atr']) <= 1
    rl, pl = rec.get('level'), (pick or {}).get('level')
    rs, ps = rec.get('dist_sigma'), (pick or {}).get('dist_sigma')
    hit = (rl == pl) and (rs is None or ps is None or abs(rs - ps) <= 0.006)
    if same_px and same_atr and hit:
        ok += 1
    else:
        bad += 1
        rows.append((c, it['name'],
                     '종가 %s/%s · ATR %s/%s · 레벨 %s/%s · σ %s/%s'
                     % (it['close'], round(v['c']), it['atr'], round(v['a']),
                        rl, pl, rs, ps)))

print('%s 대조 — 로스터 %d종목' % (DATE, len(e['items'])))
print('  일치 %d · 불일치 %d · 유니버스300 밖(수집 안 함) %d' % (ok, bad, miss))
tot = ok + bad
if tot:
    print('  일치율 %.1f%%' % (100.0 * ok / tot))
for r in rows[:15]:
    print('   [불일치] %s %s — %s' % r)
print()
n_z = sum(1 for v in g.values() if not v.get('err') and v.get('zones'))
n_l = sum(1 for v in g.values() if not v.get('err') and v.get('lines'))
tot_l = sum(len(v.get('lines') or []) for v in g.values() if not v.get('err'))
print('광역 수집 상태 — %d종목 · 존 있는 종목 %d · 라인 있는 종목 %d · 근접 라인 평균 %.1f개'
      % (len(g), n_z, n_l, tot_l / max(1, n_l)))
up = 0
for code, v in g.items():
    if v.get('err') or v.get('sym', '').split(':')[-1] != code:
        continue
    if bi.pick_level(v['c'], v['a'], v.get('zones'), v.get('lines'), 'up'):
        up += 1
print('위쪽 레벨이 잡힌 종목 %d / %d (%.0f%%)' % (up, len(g), 100.0 * up / len(g)))

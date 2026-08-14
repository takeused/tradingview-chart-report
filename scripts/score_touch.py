# v6 도달확률 채점기 — p_probe(고정거리)와 p_touch(차트 레벨)를 Brier·신뢰도 곡선으로 채점한다
#
# 왜 이게 있나: v5까지는 회차당 실제 채점이 0~2건이라 표본이 안 쌓였고,
#   2~3세션 이연분 27건은 만기 채점 기록이 아예 없었다(열고 안 닫음).
#   p_probe는 레벨 유무와 무관하게 22종목 x 2방향 = 44건을 매 회차 강제로 채점한다.
#
# 사용법:
#   python scripts/score_touch.py <actuals.json>
#   actuals.json = {"005930": {"next_hi": 275500, "next_lo": 266000}, ...}
#   (기준일 다음 거래일의 고가/저가. 수집은 실행방법.md의 ui_evaluate 한 패스 방식.)
#
# 핵심 판정: 조건부 모델이 '거리 단독' 기준선을 이기는가.
#   못 이기면 조건부는 폐기한다 — 거리만으로 낸 확률은 ATR의 재진술이라 그 자체는 실력이 아니다.

import json, sys, os

PRED = os.path.join(os.path.dirname(__file__), '..', 'data', 'predictions.json')


def brier(pairs):
    """pairs = [(예측확률 0~1, 실제 0/1)]"""
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else None


def reliability(pairs, bins=((0, .2), (.2, .35), (.35, .5), (.5, .65), (.65, .8), (.8, 1.01))):
    out = []
    for lo, hi in bins:
        s = [(p, y) for p, y in pairs if lo <= p < hi]
        if not s:
            continue
        out.append({'bin': '%.0f~%.0f%%' % (lo * 100, hi * 100), 'n': len(s),
                    'pred': round(sum(p for p, _ in s) / len(s) * 100, 1),
                    'actual': round(sum(y for _, y in s) / len(s) * 100, 1)})
    return out


def score_entry(entry, actuals):
    cond, base, touch = [], [], []
    detail = []
    for it in entry['items']:
        a = actuals.get(it['code'])
        if not a:
            continue
        hi, lo = a['next_hi'], a['next_lo']

        pb = it.get('p_probe')
        if pb:
            for key, blk in pb.items():
                up_hit = 1 if hi >= blk['up_level'] else 0
                dn_hit = 1 if lo <= blk['dn_level'] else 0
                cond.append((blk['up'] / 100, up_hit))
                cond.append((blk['dn'] / 100, dn_hit))
                base.append((blk['up_base'] / 100, up_hit))
                base.append((blk['dn_base'] / 100, dn_hit))
                detail.append({'code': it['code'], 'name': it.get('name'), 'dist': key,
                               'up_pred': blk['up'], 'up_hit': up_hit,
                               'dn_pred': blk['dn'], 'dn_hit': dn_hit})

        # 차트 레벨 p_touch (있는 방향만)
        if it.get('p_touch_up') is not None and it.get('resist'):
            touch.append((it['p_touch_up'] / 100, 1 if hi >= it['resist'] else 0))
        if it.get('p_touch_dn') is not None and it.get('support'):
            touch.append((it['p_touch_dn'] / 100, 1 if lo <= it['support'] else 0))

    bc, bb = brier(cond), brier(base)
    return {
        'asof': entry['asof'],
        'n_probe': len(cond),
        'brier_conditional': round(bc, 5) if bc is not None else None,
        'brier_distance_only': round(bb, 5) if bb is not None else None,
        'skill_vs_baseline_pct': round((bb - bc) / bb * 100, 2) if bc is not None and bb else None,
        'verdict': ('조건부가 기준선을 이김' if bc is not None and bb and bc < bb
                    else '조건부가 기준선에 못 미침 — 누적되면 폐기 검토'),
        'reliability_conditional': reliability(cond),
        'n_touch': len(touch),
        'brier_touch': round(brier(touch), 5) if touch else None,
        'touch_hit_rate': round(sum(y for _, y in touch) / len(touch) * 100, 1) if touch else None,
        'detail': detail,
        '_caveat': ('회차 내 관측은 독립이 아니다(같은 날·같은 시장). 한 회차 Brier 차이로 결론 내지 말고 '
                    '누적 10회차 이후에 판단한다.')}


def main():
    if len(sys.argv) < 2:
        print(__doc__ or 'usage: score_touch.py <actuals.json>')
        sys.exit(1)
    actuals = json.load(open(sys.argv[1], encoding='utf-8'))
    d = json.load(open(PRED, encoding='utf-8'))
    entry = d['entries'][-1]
    res = score_entry(entry, actuals)
    print(json.dumps({k: v for k, v in res.items() if k != 'detail'}, ensure_ascii=False, indent=1))
    return res


if __name__ == '__main__':
    main()

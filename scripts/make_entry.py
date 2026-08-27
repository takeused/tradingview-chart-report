# build_items 산출물을 정규 회차 entry 로 만들어 predictions.json 에 붙인다
#
# 왜 있나 (2026-08-24, 4회차): build_items.py 는 로스터 증설용이라 line_provenance 를
#   전부 'fresh' 로 박고 note 를 "신규 편입"으로 쓴다. 정규 회차에서 그대로 쓰면
#   라인 이월 규칙을 검증기가 검사하지 못하고, 본문에 없는 편입 사실이 인쇄된다.
#
# 결측 사유도 여기서 적는다 — "유효 레벨 없음"은 왜 없는지가 정보다.
#   0.5σ 하한 미달인지, 3σ 밖인지, 후보 자체가 없는지를 가른다.
#
# 사용법
#   python scripts/make_entry.py --dir <스크래치> --date 2026-08-24 --next 2026-08-25

import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json_io

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PRED = os.path.join(ROOT, 'data', 'predictions.json')


def why_missing(close, atr, zones, lines, direction):
    """레벨이 없을 때 그 이유를 문장으로 돌려준다."""
    near, far = [], []
    for hi, lo in zones or []:
        lvl = lo if direction == 'up' else hi
        if (direction == 'up' and lvl <= close) or (direction == 'dn' and lvl >= close):
            continue
        (far if abs(lvl - close) / atr > 3.0 else near).append(lvl)
    for lv in lines or []:
        if (direction == 'up' and lv <= close) or (direction == 'dn' and lv >= close):
            continue
        d = abs(lv - close) / atr
        if d < 0.5:
            near.append(lv)
        elif d > 3.0:
            far.append(lv)
    if near:
        return '0.5σ 하한 미달(최근접 %s)' % format(int(round(min(near, key=lambda x: abs(x - close)))), ',')
    if far:
        return '3σ 밖'
    return '후보 없음'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--next', required=True)
    ap.add_argument('--weekday', required=True, help='기준일 요일 한 글자 — 월화수목금')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    new = json.load(open(os.path.join(a.dir, 'items_new.json'), encoding='utf-8'))
    md = json.load(open(os.path.join(a.dir, 'metrics_daily.json'), encoding='utf-8'))
    fp = os.path.join(a.dir, 'lines_fresh.json')
    fresh = set(json.load(open(fp, encoding='utf-8'))) if os.path.exists(fp) else set()

    items = new['items'] if isinstance(new, dict) else new
    calls = new.get('open_calls', []) if isinstance(new, dict) else []

    for it in items:
        code = it['code']
        m = md[code]
        zl = json.load(open(os.path.join(a.dir, '%s.json' % code), encoding='utf-8'))
        close, atr = float(m['close']), float(m['atr'])
        it['line_provenance'] = 'fresh' if code in fresh else 'carry'

        miss = []
        for d, key in (('up', 'resist'), ('dn', 'support')):
            if it.get(key) is None:
                miss.append('%s %s' % ('위' if d == 'up' else '아래',
                                       why_missing(close, atr, zl['zones'], zl['lines'], d)))
        lv = []
        for d, key, lab in (('up', 'resist', '저항'), ('dn', 'support', '지지')):
            if it.get(key) is not None:
                p = it['p_touch'][d]
                lv.append('%s %s(%.2fσ·%s·%s%%)'
                          % (lab, format(it[key], ','), p['dist_sigma'],
                             '존' if p['src'] == 'zone' else '라인', p['p']))
        it['note'] = ('초과 %+.2f%%p(β%.2f) · 배지 %s(%.2fσ) · 거래량 %.2f배 · %s'
                      % (it['excess'], m['beta'], it['badge'], it['badge_sigma'],
                         m['volx'], ' / '.join(lv) if lv else '유효 레벨 없음'))
        if miss:
            it['note'] += ' · 없는 쪽 — ' + ', '.join(miss)
        it['prob_reason'] = '검정 통과 신호 없음(60종목 확장 유니버스) — 무정보 기본값'

    d = json.load(open(PRED, encoding='utf-8'))
    entry = {'asof': a.date, 'next_session': a.next,
             # 지수는 정수로 맞춘다 — 직전 회차까지 정수라 섞이면 대조가 깨진다
             'index': {'KOSPI': int(round(md['KOSPI']['close'])),
                       'KOSDAQ': int(round(md['KOSDAQ']['close']))},
             'scored': None, 'roster_change': None,
             '_note': '로스터·수집·확률 전 과정 v6.1. 주봉 확률은 금요일에만 낸다(오늘은 %s요일).'
                      % a.weekday,
             'items': items}

    want = sum(1 for it in items for k in it['p_touch'])
    if want != len(calls):
        raise SystemExit('원장 등록 수 불일치 — 레벨 있는 방향 %d, 등록분 %d' % (want, len(calls)))

    if a.dry:
        print('dry — 항목 %d · 원장 %d건 · 지수 %s' % (len(items), len(calls), entry['index']))
        return 0

    d['entries'].append(entry)
    d['open_calls']['active'].extend(calls)
    json_io.dump_predictions(d, PRED, backup=True)
    print('기록 완료 — 항목 %d · 원장 신규 %d건 · active 총 %d건'
          % (len(items), len(calls), len(d['open_calls']['active'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())

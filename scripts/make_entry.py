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
import build_items as bi          # 하한·상한은 레벨을 고르는 쪽이 진실이다

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PRED = os.path.join(ROOT, 'data', 'predictions.json')


def why_missing(close, atr, zones, lines, direction):
    """레벨이 없을 때 그 이유를 문장으로 돌려준다.

    후보 열거는 build_items.pick_level 과 **같은 규칙**이어야 한다 — 여기서만 다르게 세면
    "왜 없는지"가 거짓말이 된다. 그래서 하한도 그 모듈에서 가져온다.
    (2026-09-09: 존에도 하한이 생겨 사유가 셋으로 갈린다 — 존 0.3σ · 라인 0.5σ · 3σ 밖.)
    """
    near_z, near_l, far = [], [], []
    for hi, lo in zones or []:
        lvl = (hi if direction == 'up' else lo) if lo <= close <= hi else \
              (lo if direction == 'up' else hi)
        if (direction == 'up' and lvl <= close) or (direction == 'dn' and lvl >= close):
            continue
        d = abs(lvl - close) / atr
        if d < bi.MIN_ZONE_SIGMA:
            near_z.append(lvl)
        elif d > bi.MAX_SIGMA:
            far.append(lvl)
    for lv in lines or []:
        if (direction == 'up' and lv <= close) or (direction == 'dn' and lv >= close):
            continue
        d = abs(lv - close) / atr
        if d < bi.MIN_LINE_SIGMA:
            near_l.append(lv)
        elif d > bi.MAX_SIGMA:
            far.append(lv)

    def fmt(xs):
        return format(int(round(min(xs, key=lambda x: abs(x - close)))), ',')

    why = []
    if near_z:
        why.append('존 %.1fσ 하한 미달(최근접 %s)' % (bi.MIN_ZONE_SIGMA, fmt(near_z)))
    if near_l:
        why.append('라인 %.1fσ 하한 미달(최근접 %s)' % (bi.MIN_LINE_SIGMA, fmt(near_l)))
    if why:
        return ' · '.join(why)
    if far:
        return '3σ 밖'
    return '후보 없음'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--next', required=True)
    ap.add_argument('--weekday', required=True, help='기준일 요일 한 글자 — 월화수목금')
    ap.add_argument('--roster-change', default=None,
                    help='로스터가 바뀐 회차에만 — 바뀐 종목과 편향을 문장으로 적는다')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    new = json.load(open(os.path.join(a.dir, 'items_new.json'), encoding='utf-8'))
    md = json.load(open(os.path.join(a.dir, 'metrics_daily.json'), encoding='utf-8'))

    items = new['items'] if isinstance(new, dict) else new
    calls = new.get('open_calls', []) if isinstance(new, dict) else []

    for it in items:
        code = it['code']
        m = md[code]
        zl = json.load(open(os.path.join(a.dir, '%s.json' % code), encoding='utf-8'))
        close, atr = float(m['close']), float(m['atr'])

        # 라인 출처는 **라인을 담은 파일에서** 읽는다(2026-09-10 개정).
        #
        # 전에는 스크래치패드에 `lines_fresh.json` 이 있는지로 갈랐는데, 2026-09-04부터
        # 라인은 매 회차 전 종목 새로 읽으므로 그 파일이 없을 이유가 없다 — 그런데도
        # 없으면 조용히 36종목 전부 'carry' 가 됐다(2026-09-10 회차에 발생).
        # **없는 파일이 거짓을 만드는 구조**였으므로, 판정을 수집물 쪽으로 옮기고
        # 키가 없으면 **멈춘다**. 기본값으로 메우면 같은 거짓말이 되돌아온다.
        if 'line_src' not in zl:
            raise SystemExit(
                '%s.json 에 line_src 가 없다 — 수집물을 scripts/split_graphics.py (전 종목 '
                '새로 읽은 회차) 또는 scripts/prep_round.py (이월 회차) 로 나눌 것.' % code)
        if zl['line_src'] not in ('fresh', 'carry'):
            raise SystemExit('%s.json 의 line_src 값이 이상하다 — %r' % (code, zl['line_src']))
        it['line_provenance'] = zl['line_src']

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
        # 대체 레벨(같은 방향의 다른 출처)도 note 에 남긴다 — 원장에 올라간 콜이
        # 항목 서술에 없으면 리포트만 읽는 사람은 그 콜의 존재를 모른다.
        alt = [('%s %s(%.2fσ·%s·%s%%)'
                % ('저항' if d0 == 'up' else '지지', format(p['level'], ','),
                   p['dist_sigma'], '존' if p['src'] == 'zone' else '라인', p['p']))
               for d0, p in sorted((it.get('p_alt') or {}).items())]
        if alt:
            it['note'] += ' · 대체 — ' + ' / '.join(alt)
        if miss:
            it['note'] += ' · 없는 쪽 — ' + ', '.join(miss)
        it['prob_reason'] = '검정 통과 신호 없음(60종목 확장 유니버스) — 무정보 기본값'

    d = json.load(open(PRED, encoding='utf-8'))
    entry = {'asof': a.date, 'next_session': a.next,
             # 지수는 정수로 맞춘다 — 직전 회차까지 정수라 섞이면 대조가 깨진다
             'index': {'KOSPI': int(round(md['KOSPI']['close'])),
                       'KOSDAQ': int(round(md['KOSDAQ']['close']))},
             'scored': None, 'roster_change': a.roster_change,
             '_note': '로스터·수집·확률 전 과정 v6.2. 주봉 확률은 금요일에만 낸다(오늘은 %s요일).'
                      % a.weekday,
             'items': items}

    # 원장에는 p_touch(가까운 쪽)와 p_alt(같은 방향 다른 출처)가 **둘 다** 올라간다.
    # 세는 쪽도 둘 다 세야 한다 — 한쪽만 세면 분리 기록분이 통째로 누락돼도 통과한다.
    want = sum(1 for it in items for k in it['p_touch']) \
        + sum(1 for it in items for k in (it.get('p_alt') or {}))
    if want != len(calls):
        raise SystemExit('원장 등록 수 불일치 — 레벨 있는 방향 %d, 등록분 %d' % (want, len(calls)))

    if a.dry:
        n_alt = sum(1 for it in items for k in (it.get('p_alt') or {}))
        print('dry — 항목 %d · 원장 %d건(가까운 쪽 %d · 대체 %d) · 지수 %s'
              % (len(items), len(calls), len(calls) - n_alt, n_alt, entry['index']))
        return 0

    d['entries'].append(entry)
    d['open_calls']['active'].extend(calls)
    json_io.dump_predictions(d, PRED, backup=True)
    print('기록 완료 — 항목 %d · 원장 신규 %d건 · active 총 %d건'
          % (len(items), len(calls), len(d['open_calls']['active'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())

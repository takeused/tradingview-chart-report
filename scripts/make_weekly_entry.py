# build_items 산출물의 주봉 부분을 정규 주봉 회차로 만들어 predictions.json 에 붙인다
#
# 왜 있나 (2026-08-28, 금요일 2회차): 주봉 entry 를 만드는 코드가 없었다. 8/21 첫 회차는
#   손으로 만들었고, merge_items.py 는 **이미 있는** 주봉 entry 에 종목을 더하는 도구다.
#   금요일마다 손으로 만들면 note·결측사유·ATR 창 미달 처리가 회차마다 달라진다.
#
# build_items.py 가 주봉에서 남기는 구멍 둘을 여기서 메운다.
#   1) note 가 "신규 편입"으로 박힌다 — 정규 회차 문장으로 바꾼다.
#   2) ATR 창 120주 미달 종목은 {code, name, atr_insufficient} 만 남는다 —
#      레벨은 내야 하므로(확률만 안 낸다) pick_level 로 채워 완전한 행을 만든다.
#
# 사용법
#   python scripts/make_weekly_entry.py --dir <스크래치> --date 2026-08-28 \
#          --next 2026-09-04 --kospi -1.79 --kosdaq 4.55

import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json_io
from build_items import pick_level
from make_entry import why_missing

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PRED = os.path.join(ROOT, 'data', 'predictions.json')
WEEKS = 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--next', required=True)
    ap.add_argument('--kospi', type=float, required=True, help='주간 KOSPI 등락률 %%')
    ap.add_argument('--kosdaq', type=float, required=True, help='주간 KOSDAQ 등락률 %%')
    ap.add_argument('--note', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    new = json.load(open(os.path.join(a.dir, 'items_new.json'), encoding='utf-8'))
    mw = json.load(open(os.path.join(a.dir, 'metrics_weekly.json'), encoding='utf-8'))
    md = json.load(open(os.path.join(a.dir, 'metrics_daily.json'), encoding='utf-8'))
    rows, wcalls = new['weekly_rows'], new['weekly_calls']

    for r in rows:
        code = r['code']
        w, m = mw[code], md[code]
        wz = json.load(open(os.path.join(a.dir, 'w_%s.json' % code), encoding='utf-8'))
        close, watr = float(w['close']), float(w['watr'])

        if r.get('atr_insufficient'):
            # 확률은 못 내지만 레벨은 낸다 — 8/21 회차의 달바글로벌·웨이비스와 같은 규격
            up = pick_level(close, watr, wz['zones'], wz['lines'], 'up')
            dn = pick_level(close, watr, wz['zones'], wz['lines'], 'dn')
            main_dir = 'up' if (up and (not dn or up['dist_sigma'] <= dn['dist_sigma'])) else 'dn'
            r.update({
                'market': 'KOSPI' if m['mkt'] == 'P' else 'KOSDAQ', 'timeframe': '1W',
                'close': int(close), 'atr': int(watr), 'wchg': w['wchg'],
                'resist': up['level'] if up else None,
                'support': dn['level'] if dn else None,
                'src': (up or dn or {}).get('src'),
                'src_up': up['src'] if up else None,
                'src_dn': dn['src'] if dn else None,
                'sigma': [up['dist_sigma'] if up else None, dn['dist_sigma'] if dn else None],
                'call': ('up_test' if main_dir == 'up' else 'down_test') if (up or dn) else 'no_level',
                'distance_sigma': (up or dn or {}).get('dist_sigma'),
                'horizon': '2~3주', 'prior': None,
                'direction_prob': 0.5, 'expected_fret': 0.0,
                'prob_reason': '검정 통과 신호 없음 — 무정보 기본값', 'conf': 'low',
                'model_inputs': {'wrngatr': w['wrngatr'], 'watrpct': w['watrpct'],
                                 'watr_bars': w['bars'], 'atr_method': 'wilder14_1W'},
                'p_touch': {}, 'p_probe': None,
                'm4': w['m4'], 'm12': w['m12'], 'pos12': w['pos12'],
                'wstreak': w['wstreak'], 'watrpct': w['watrpct'],
            })
            r['note'] = ('ATR 창 %d주로 120주 미달 — 레벨만 표시하고 확률은 내지 않았다. '
                         '주간 %+.2f%% · 12주 위치 %d%%' % (w['bars'], w['wchg'], w['pos12']))
            continue

        lv = []
        for d, key, lab in (('up', 'resist', '저항'), ('dn', 'support', '지지')):
            if r.get(key) is not None:
                p = r['p_touch'][d]
                lv.append('%s %s(%.2fσ·%s·%s%%)'
                          % (lab, format(r[key], ','), p['dist_sigma'],
                             '존' if p['src'] == 'zone' else '라인', p['p']))
        miss = []
        for d, key in (('up', 'resist'), ('dn', 'support')):
            if r.get(key) is None:
                miss.append('%s %s' % ('위' if d == 'up' else '아래',
                                       why_missing(close, watr, wz['zones'], wz['lines'], d)))
        r['note'] = ('주간 %+.2f%% · 4주 %+.1f%% · 12주 %+.1f%% · 12주위치 %d%% · 연속 %d주 · %s'
                     % (w['wchg'], w['m4'], w['m12'], w['pos12'], w['wstreak'],
                        ' / '.join(lv) if lv else '유효 레벨 없음'))
        if miss:
            r['note'] += ' · 없는 쪽 — ' + ', '.join(miss)
        r['atr_insufficient'] = None

    want = sum(len(r.get('p_touch') or {}) for r in rows)
    if want != len(wcalls):
        raise SystemExit('주봉 원장 등록 수 불일치 — 레벨 있는 방향 %d, 등록분 %d'
                         % (want, len(wcalls)))

    entry = {'asof': a.date, 'next_week': a.next, 'timeframe': '1W', 'model': 'v6.2-W',
             'index': {'KOSPI_wchg': a.kospi, 'KOSDAQ_wchg': a.kosdaq},
             'scored': None, 'roster_change': None, '_note': a.note, 'items': rows}

    if a.dry:
        print('dry — 주봉 항목 %d · 원장 %d건 · 확률 미산출 %d종목'
              % (len(rows), len(wcalls), sum(1 for r in rows if r.get('atr_insufficient'))))
        return 0

    d = json_io.load_predictions(PRED)
    if any(e.get('asof') == a.date for e in d['weekly_entries']):
        raise SystemExit('주봉 entry %s 가 이미 있다' % a.date)
    d['weekly_entries'].append(entry)
    d['weekly_calls']['active'].extend(wcalls)
    json_io.dump_predictions(d, PRED, backup=True)
    print('기록 완료 — 주봉 항목 %d · 원장 신규 %d건 · active 총 %d건'
          % (len(rows), len(wcalls), len(d['weekly_calls']['active'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())

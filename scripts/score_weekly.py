# 주봉 회차 채점기 (v6.1-W) — 매주 금요일 1회만 돌린다
#
# 왜 별도 스크립트인가: 채점 로직 자체는 score_touch.py 것을 그대로 쓴다(복사하지 않는다).
#   다른 것은 딱 두 가지다.
#     1) 만기 단위가 '주'다. 주봉 콜을 일봉 원장에 넣으면 score_touch.py 가 하루마다
#        만기를 깎아 1~3'일'만에 닫아 버린다 — 그래서 원장을 weekly_calls 로 분리했다.
#     2) 확률표가 주봉 표(TABLE_W)다. 같은 σ 거리에서 주봉은 위쪽 도달률이 체계적으로 높다.
#
# 사용법
#   python scripts/score_weekly.py <actuals.json> [--week YYYY-MM-DD] [--write]
#   actuals.json = {"005930": {"hi": …, "lo": …}, …}
#     ← 채점 주(월~금)의 **주봉 고가/저가**. 일봉 값을 넣으면 안 된다.

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_model as tm
from score_touch import score_probe, close_open_calls

PRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'predictions.json')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    write = '--write' in sys.argv
    week = None
    if '--week' in sys.argv:
        week = sys.argv[sys.argv.index('--week') + 1]
    if not args:
        print('usage: score_weekly.py <actuals.json> [--week YYYY-MM-DD] [--write]')
        sys.exit(1)

    actuals = json.load(open(args[0], encoding='utf-8'))
    d = json.load(open(PRED, encoding='utf-8'))
    entries = d.get('weekly_entries')
    if not entries:
        print('[중단] weekly_entries 가 없다.')
        sys.exit(2)
    entry = entries[-1]

    expected = entry.get('next_week')
    if week and expected and week != expected:
        print('[중단] 채점 대상 주봉 회차의 next_week 는 %s 인데 --week %s 가 들어왔다.'
              % (expected, week))
        sys.exit(2)
    if entry.get('scored') is not None:
        print('[중단] 마지막 주봉 회차(%s)는 이미 채점됐다.' % entry['asof'])
        sys.exit(2)

    res = {
        'asof': entry['asof'],
        'scored_on': week or expected,
        'model': tm.META_W['version'],
        'probe': score_probe(entry, actuals),
        'weekly_calls': close_open_calls(
            d.setdefault('weekly_calls', {'active': []}), actuals, week or expected,
            hkey='horizon_weeks', ekey='weeks_elapsed'),
        '_caveat': ('주봉은 회차당 관측이 적고(레벨 콜 약 20건) 같은 주 시장을 공유한다. '
                    '일봉보다 훨씬 느리게 쌓이므로 누적 10주 이전에는 추세를 말하지 않는다.'),
    }

    print(json.dumps({k: v for k, v in res.items() if k != 'weekly_calls'},
                     ensure_ascii=False, indent=1))
    print(json.dumps({'weekly_calls': {k: v for k, v in res['weekly_calls'].items()
                                       if k != 'rows'}}, ensure_ascii=False, indent=1))

    if write:
        entry['scored'] = res
        from json_io import dump_predictions
        dump_predictions(d, PRED)
        print('\n기록 완료 — %s 주봉 entry.scored' % entry['asof'])
    return res


if __name__ == '__main__':
    main()

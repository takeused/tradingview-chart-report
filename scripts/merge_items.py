# build_items.py 산출물을 predictions.json 의 해당 회차에 병합한다
#
# 왜 있나 (2026-08-22): 로스터를 8종목 늘리면서 항목·일봉 원장·주봉 항목·주봉 원장 네 곳을
#   동시에 갱신해야 한다. 손으로 하면 어느 하나를 빠뜨리고, 원장 누락은 채점기가 영원히
#   그 콜을 못 보는 사고로 이어진다(v6.1 감사에서 8/14 레벨 콜 16건이 그렇게 사라졌다).
#
# 사용법
#   python scripts/merge_items.py --in <items_new.json> --date 2026-08-21 [--dry]

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json_io

PRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'predictions.json')


def main():
    src = sys.argv[sys.argv.index('--in') + 1]
    date = sys.argv[sys.argv.index('--date') + 1]
    dry = '--dry' in sys.argv
    new = json.load(open(src, encoding='utf-8'))
    d = json_io.load_predictions(PRED)

    ent = next((e for e in d['entries'] if e.get('asof') == date), None)
    if ent is None:
        raise SystemExit('일봉 entry %s 를 못 찾았다' % date)
    went = next((e for e in d['weekly_entries'] if e.get('asof') == date), None)
    if went is None:
        raise SystemExit('주봉 entry %s 를 못 찾았다' % date)

    have = {i['code'] for i in ent['items']}
    add = [i for i in new['items'] if i['code'] not in have]
    whave = {i['code'] for i in went['items']}
    wadd = [i for i in new['weekly_rows'] if i['code'] not in whave]

    ochave = {(c['code'], c['dir'], c['opened']) for c in d['open_calls']['active']}
    ocadd = [c for c in new['open_calls'] if (c['code'], c['dir'], c['opened']) not in ochave]
    wchave = {(c['code'], c['dir'], c['opened']) for c in d['weekly_calls']['active']}
    wcadd = [c for c in new['weekly_calls'] if (c['code'], c['dir'], c['opened']) not in wchave]

    print('추가 — 일봉 항목 %d · 주봉 항목 %d · 일봉 레벨콜 %d · 주봉 레벨콜 %d'
          % (len(add), len(wadd), len(ocadd), len(wcadd)))
    if dry:
        return 0

    ent['items'] += add
    went['items'] += wadd
    d['open_calls']['active'] += ocadd
    d['weekly_calls']['active'] += wcadd
    ent['roster_change'] = ('8/21과 같은 22종목에 HPSP·파마리서치·코스메카코리아·알테오젠·'
                            '키움증권·삼양식품·KCC·코스맥스 8종목 추가 — 총 30종목.')
    went['roster_change'] = ent['roster_change']

    # 등록 누락 검증 — 레벨 콜 수와 원장 등록 수가 같아야 한다
    n_lv = sum(len(i.get('p_touch') or {}) for i in add)
    n_wlv = sum(len(i.get('p_touch') or {}) for i in wadd)
    assert n_lv == len(ocadd), '일봉 레벨콜 %d 인데 원장 %d' % (n_lv, len(ocadd))
    assert n_wlv == len(wcadd), '주봉 레벨콜 %d 인데 원장 %d' % (n_wlv, len(wcadd))

    json_io.dump_predictions(d, PRED, backup=True)
    print('저장 — 일봉 항목 %d · 주봉 항목 %d · open_calls %d · weekly_calls %d'
          % (len(ent['items']), len(went['items']),
             len(d['open_calls']['active']), len(d['weekly_calls']['active'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())

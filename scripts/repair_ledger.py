# 원장 누락 복구 — 반대편 방향 콜이 등록되지 않아 절반이 채점되지 않던 문제
#
# 왜 있나 (2026-08-22 발견): 항목마다 p_touch 로 **위·아래 확률을 둘 다** 내면서 원장에는
#   주 방향 한 건만 등록해 왔다. 채점기(score_touch)는 active 목록을 방향별로 독립 처리하므로
#   등록만 하면 그대로 채점된다. 즉 예측의 절반을 **버리고 있었다** — 8/21 회차만 해도
#   일봉 15건·주봉 다수가 영원히 채점 대상이 아니었다.
#
#   확률을 냈으면 채점해야 한다. 안 그러면 "조건부가 기준선을 이겼는가"를 절반의 표본으로만
#   판정하게 되고, 하필 주 방향(=가까운 쪽)만 남아 표본이 **거리 짧은 콜로 편향**된다.
#
# 룩어헤드 — 이미 계산해 둔 확률을 원장에 옮겨 적는 것뿐이고, 해당 회차 이후 세션이
#   지나지 않은 시점에만 돌린다. 세션이 지난 뒤 소급 등록하면 결과를 보고 고르는 것이 되므로 금지.
#
# 사용법
#   python scripts/repair_ledger.py --date 2026-08-21 [--dry]

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json_io

PRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'predictions.json')


def rows_for(items, date, key_h, elapsed_key):
    out = []
    for it in items:
        for d, pr in (it.get('p_touch') or {}).items():
            if pr.get('level') is None:
                continue
            row = {'opened': date, 'code': it['code'], 'name': it['name'], 'dir': d,
                   'level': pr['level'], 'dist_sigma': pr['dist_sigma'],
                   key_h: pr.get(key_h), 'expiry_after_' + key_h.split('_')[1]: pr.get(key_h),
                   'p': pr['p'], 'p_base': pr['p_base'], elapsed_key: 0,
                   'status': 'open', 'model_inputs': it.get('model_inputs')}
            out.append(row)
    return out


def main():
    date = sys.argv[sys.argv.index('--date') + 1]
    dry = '--dry' in sys.argv
    d = json_io.load_predictions(PRED)

    # 라벨 오탈자 교정 — 규격은 'down_test' 인데 'dn_test' 가 섞였다
    fixed = 0
    for e in d['entries'] + d['weekly_entries']:
        for it in e['items']:
            if it.get('call') == 'dn_test':
                it['call'] = 'down_test'
                fixed += 1

    total = 0
    for label, ekey, lkey, hkey, elapsed in (
            ('일봉', 'entries', 'open_calls', 'horizon_sessions', 'sessions_elapsed'),
            ('주봉', 'weekly_entries', 'weekly_calls', 'horizon_weeks', 'weeks_elapsed')):
        ent = next((e for e in d[ekey] if e.get('asof') == date), None)
        if ent is None:
            continue
        led = d[lkey]
        have = {(c['code'], c['dir']) for c in led['active'] if c.get('opened') == date}
        want = rows_for(ent['items'], date, hkey, elapsed)
        add = [r for r in want if (r['code'], r['dir']) not in have]
        print('%s — 항목 %d · 레벨 있는 방향 %d · 이미 등록 %d · 신규 등록 %d'
              % (label, len(ent['items']), len(want), len(have), len(add)))
        for r in add[:5]:
            print('    + %s %s %s @ %s (%.2fσ, p=%.1f)'
                  % (r['code'], r['name'], r['dir'], '{:,}'.format(r['level']),
                     r['dist_sigma'], r['p']))
        if not dry:
            led['active'] += add
        total += len(add)

    print('call 라벨 교정 %d건 · 원장 신규 등록 %d건' % (fixed, total))
    if not dry:
        json_io.dump_predictions(d, PRED, backup=True)
        print('저장 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main())

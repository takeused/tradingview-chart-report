# predictions.json 정합성 검증 — 매 회차 기록 직후 반드시 돌린다
#
# 왜 있나: v6.1 감사에서 결함 6종이 한꺼번에 나왔다. 전부 "사람이 눈으로 보면 놓치는" 종류였다.
#   - 확률표와 적용의 ATR 정의 불일치
#   - horizon 라벨과 확률표 세션 수 불일치
#   - 같은 항목에서 prior와 p_touch가 다른 기간을 지칭
#   - open_calls.active 가 비어 있음(레벨 콜 16건 미등록)
#   - 확률은 있는데 대응 레벨 필드가 null
#   - 거리 0 근방 보간 누락
#   이 스크립트는 그 여섯을 전부 기계로 잡는다.
#
# 사용법
#   python scripts/validate_predictions.py            # 마지막 회차 검사
#   python scripts/validate_predictions.py --all      # 전 회차 검사

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_model as tm

PRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'predictions.json')
LEVEL_CALLS = ('up_test', 'down_test')


def check_entry(e, ledger, strict_ledger=True):
    err, warn = [], []
    tag = e['asof']
    codes = set()

    for it in e['items']:
        c = it['code']
        nm = '%s %s' % (tag, it.get('name', c))
        if c in codes:
            err.append('%s — 종목 중복' % nm)
        codes.add(c)

        h = tm.horizon_sessions(it.get('horizon'))
        sg = it.get('sigma') or [None, None]

        # 1) 확률이 있으면 대응 레벨이 반드시 있어야 한다
        pt = it.get('p_touch') or {}
        for dirn, fld in (('up', 'resist'), ('dn', 'support')):
            if pt.get(dirn) is not None and it.get(fld) is None:
                err.append('%s — p_touch.%s 있는데 %s 가 null (채점 불가)' % (nm, dirn, fld))
            # 2) 확률·기준선은 쌍으로
            if pt.get(dirn) is not None:
                blk = pt[dirn]
                if blk.get('p') is None or blk.get('p_base') is None:
                    err.append('%s — p_touch.%s 에 p/p_base 짝이 없다' % (nm, dirn))
                # 3) horizon 일치
                if blk.get('horizon_sessions') != h:
                    err.append('%s — p_touch.%s horizon %s != item horizon %s(%d세션)'
                               % (nm, dirn, blk.get('horizon_sessions'), it.get('horizon'), h))
                # 4) 모델 재현 검증 — 저장값이 모듈 계산과 일치하는가
                exp = tm.base_p(blk.get('dist_sigma'), dirn, h)
                if exp is not None and blk.get('p_base') is not None and abs(exp - blk['p_base']) > 0.15:
                    err.append('%s — p_base %s != 모듈 계산 %s (표 불일치)' % (nm, blk['p_base'], exp))

        # 5) sigma 와 레벨 필드의 대응
        for i, (fld, dirn) in enumerate((('resist', 'up'), ('support', 'dn'))):
            has_sig = isinstance(sg[i], (int, float))
            has_lvl = it.get(fld) is not None
            if has_sig and not has_lvl:
                warn.append('%s — sigma[%d]=%s 인데 %s 가 null' % (nm, i, sg[i], fld))
            if has_lvl and not has_sig:
                warn.append('%s — %s 있는데 sigma[%d] 가 null' % (nm, fld, i))

        # 6) prior 는 거리단독 기저값과 같아야 한다(같은 지평)
        if it.get('prior') is not None and it.get('distance_sigma') is not None \
                and it['call'] in LEVEL_CALLS:
            dirn = 'up' if it['call'] == 'up_test' else 'dn'
            exp = round(tm.base_p(it['distance_sigma'], dirn, h))
            if abs(exp - it['prior']) > 1:
                err.append('%s — prior %s != 기저표 %s (거리 %.2fσ, %d세션)'
                           % (nm, it['prior'], exp, it['distance_sigma'], h))

        # 7) p_probe 완전성 — 레벨 유무와 무관하게 전 종목에 있어야 한다
        pb = it.get('p_probe')
        if not pb:
            err.append('%s — p_probe 없음 (채점 집합에서 누락된다)' % nm)
        else:
            for key, blk in pb.items():
                for k in ('up', 'dn', 'up_base', 'dn_base', 'up_level', 'dn_level'):
                    if blk.get(k) is None:
                        err.append('%s — p_probe[%s].%s 누락' % (nm, key, k))
                if blk.get('up_level') and blk.get('dn_level') and blk['up_level'] <= blk['dn_level']:
                    err.append('%s — p_probe[%s] 위/아래 레벨이 뒤집혔다' % (nm, key))

        # 8) 확률 범위
        for label, v in [('direction_prob', it.get('direction_prob'))]:
            if v is not None and not (0 <= v <= 1):
                err.append('%s — %s 범위 이탈 %s' % (nm, label, v))

    # 9) 레벨 콜은 전부 원장에 등록돼야 한다
    if strict_ledger:
        lv = [it for it in e['items'] if it['call'] in LEVEL_CALLS]
        reg = [c for c in ledger.get('active', []) if c.get('opened') == e['asof']]
        if len(reg) != len(lv):
            err.append('%s — 레벨 콜 %d건인데 open_calls.active 등록 %d건 (채점기가 못 본다)'
                       % (tag, len(lv), len(reg)))
        for c in reg:
            for k in ('code', 'dir', 'level', 'horizon_sessions', 'p', 'p_base', 'status'):
                if c.get(k) is None:
                    err.append('%s — 원장 %s 항목에 %s 누락' % (tag, c.get('code'), k))
    return err, warn


def main():
    d = json.load(open(PRED, encoding='utf-8'))
    ledger = d.get('open_calls', {})
    entries = d['entries'] if '--all' in sys.argv else d['entries'][-1:]
    all_err, all_warn = [], []
    for e in entries:
        # 과거 회차는 v6.1 규격 이전이라 원장 검사를 건너뛴다
        strict = (e is d['entries'][-1])
        er, wr = check_entry(e, ledger, strict_ledger=strict)
        all_err += er
        all_warn += wr

    # 원장 자체 검사
    for c in ledger.get('active', []):
        if c.get('sessions_elapsed', 0) > c.get('horizon_sessions', 1):
            all_err.append('원장 %s — 만기(%d세션) 지났는데 open 상태' % (c.get('code'), c.get('horizon_sessions')))

    # 채점 순서 검사 — 마지막 직전 회차는 채점돼 있어야 한다
    if len(d['entries']) >= 2 and d['entries'][-2].get('scored') is None:
        all_err.append('%s 회차가 채점되지 않은 채 다음 회차가 추가됐다' % d['entries'][-2]['asof'])

    print('오류 %d건 · 경고 %d건 (모델 %s)' % (len(all_err), len(all_warn), tm.META['version']))
    for x in all_err:
        print('  [오류] ' + x)
    for x in all_warn:
        print('  [경고] ' + x)
    if not all_err:
        print('통과')
    sys.exit(1 if all_err else 0)


if __name__ == '__main__':
    main()

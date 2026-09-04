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
# 2026-08-20 감사에서 7종을 추가했다. 그날 실제로 난 사고와 손으로만 잡히던 것들이다.
#   - SK스퀘어가 1.04σ 움직였는데 라인을 이월했다(재수집 규칙 위반) → 11
#   - dist_sigma 가 (레벨−종가)/ATR 과 맞는지 아무도 안 봤다 → 8
#   - atr_bars 를 검사하는 곳이 없었다(v6 ATR 창 드리프트의 재발 경로) → 7
#   - 라인 0.5σ 하한·존 3σ 상한이 코드로 강제되지 않았다 → 9
#   - 원장 레벨이 항목 레벨과 같은지 대조하지 않았다 → 12
#   - p_probe 레벨이 종가±kσ 와 맞는지 검사하지 않았다 → 10
#   - sigma[] 배열과 p_touch.dist_sigma 가 따로 놀 수 있었다 → 8-b
#
# 사용법
#   python scripts/validate_predictions.py            # 마지막 회차 검사
#   python scripts/validate_predictions.py --all      # 전 회차 검사

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_model as tm

PRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'predictions.json')
LEVEL_CALLS = ('up_test', 'down_test')

# 2026-08-20 회차부터 도입한 근거 필드(chg · p_touch.src · line_provenance)를 필수로 본다.
# 그 이전 회차는 필드가 없으므로 해당 검사를 건너뛴다.
V62_FROM = '2026-08-20'
# 확률표 격자를 3.0σ까지 늘린 회차(v6.2). 그 전 회차의 1.5σ 밖 확률은 당시 표로는
# 옳으므로 표 대조에서 뺀다 — 안 빼면 옛 회차마다 거짓 오류가 나 진짜 오류가 묻힌다.
TABLE_V62_FROM = '2026-09-04'
MIN_ATR_BARS = 120      # 확률표(300봉)와의 오차가 0.004% 이하로 떨어지는 지점
MAX_SIGMA = 3.0         # 존·라인 표시 상한
MIN_LINE_SIGMA = 0.5    # 라인은 이보다 가까우면 노이즈라 쓰지 않는다
SIG_TOL = 0.02          # dist_sigma 는 소수 둘째 자리 반올림이라 이 정도는 허용


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
        mi_it = it.get('model_inputs') or {}
        new_spec = tag >= V62_FROM

        # 7) ATR 창 — v6 에서 확률표와 적용의 ATR 정의가 어긋났던 경로다
        ab = mi_it.get('atr_bars')
        if new_spec and ab is None:
            err.append('%s — model_inputs.atr_bars 없음 (ATR 창 검증 불가)' % nm)
        elif ab is not None and ab < MIN_ATR_BARS:
            err.append('%s — atr_bars %s < %d (Wilder 시드가 남아 확률표와 어긋난다)'
                       % (nm, ab, MIN_ATR_BARS))

        # 11) 1σ 이상 움직인 종목은 라인을 이월하면 안 된다(스윙 구조가 바뀐다)
        if new_spec and it.get('chg') is not None and mi_it.get('atrpct'):
            mv = abs(it['chg']) / mi_it['atrpct']
            if mv >= 1.0 and it.get('line_provenance') == 'carry':
                err.append('%s — %.2fσ 움직였는데 라인을 이월했다 (재수집 규칙 위반)' % (nm, mv))

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
                cur_table = tag >= TABLE_V62_FROM
                exp = tm.base_p(blk.get('dist_sigma'), dirn, h)
                if cur_table and exp is not None and blk.get('p_base') is not None \
                        and abs(exp - blk['p_base']) > 0.15:
                    err.append('%s — p_base %s != 모듈 계산 %s (표 불일치)' % (nm, blk['p_base'], exp))
                # 4-b) 조건부 p 도 저장된 입력으로 재현되는가
                mi = it.get('model_inputs')
                if cur_table and mi and blk.get('p') is not None:
                    rep = tm.cond_p(blk.get('dist_sigma'), dirn, mi.get('volx'),
                                    mi.get('rngatr'), mi.get('atrpct'), h)
                    if rep is not None and abs(rep - blk['p']) > 0.15:
                        err.append('%s — p %s 가 저장된 입력으로 재현되지 않는다(계산 %s)'
                                   % (nm, blk['p'], rep))
                if not mi:
                    warn.append('%s — model_inputs 없음 (p 재현·감사 불가)' % nm)

                # 8) dist_sigma 가 (레벨−종가)/ATR 과 일치하는가 — 레벨 산정 자체의 검산
                lvl, cl, atr = it.get(fld), it.get('close'), it.get('atr')
                ds = blk.get('dist_sigma')
                if None not in (lvl, cl, atr, ds) and atr:
                    signed = (lvl - cl) / atr if dirn == 'up' else (cl - lvl) / atr
                    if signed < 0:
                        err.append('%s — %s %s 가 종가 %s 의 반대쪽에 있다'
                                   % (nm, fld, '{:,}'.format(lvl), '{:,}'.format(cl)))
                    elif abs(signed - ds) > SIG_TOL:
                        err.append('%s — dist_sigma %.2f != (레벨−종가)/ATR %.3f'
                                   % (nm, ds, signed))
                    # 8-b) sigma[] 배열도 같은 값을 가리켜야 한다
                    i_sg = 0 if dirn == 'up' else 1
                    if isinstance(sg[i_sg], (int, float)) and abs(sg[i_sg] - ds) > SIG_TOL:
                        err.append('%s — sigma[%d]=%s 가 p_touch.%s dist_sigma %s 와 다르다'
                                   % (nm, i_sg, sg[i_sg], dirn, ds))

                # 9) 존 3σ 상한 · 라인 0.5σ 하한
                src = blk.get('src')
                if new_spec and src is None:
                    err.append('%s — p_touch.%s 에 src(zone/line) 없음 (규칙 검증 불가)' % (nm, dirn))
                if ds is not None and ds > MAX_SIGMA:
                    err.append('%s — %s 거리 %.2fσ 가 상한 %.1fσ 초과' % (nm, dirn, ds, MAX_SIGMA))
                if src == 'line' and ds is not None and ds < MIN_LINE_SIGMA:
                    err.append('%s — 라인인데 %.2fσ 로 하한 %.1fσ 미만 (노이즈 레벨)'
                               % (nm, ds, MIN_LINE_SIGMA))

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
            if tag >= TABLE_V62_FROM and abs(exp - it['prior']) > 1:
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
                # 10) 프로브 레벨이 종가 ± kσ 와 맞는가
                k = {'0p5': 0.5, '1p0': 1.0}.get(key)
                if k and it.get('close') and it.get('atr'):
                    for side, want in (('up_level', it['close'] + k * it['atr']),
                                       ('dn_level', it['close'] - k * it['atr'])):
                        got = blk.get(side)
                        if got is not None and abs(got - want) > max(1.0, it['atr'] * 0.005):
                            err.append('%s — p_probe[%s].%s %s != 종가±%.1fσ %s'
                                       % (nm, key, side, '{:,}'.format(got), k,
                                          '{:,}'.format(int(round(want)))))
                # 10-b) 프로브 확률은 **1세션** 표에서 나와야 한다 (2026-09-04 신설).
                #   score_probe 는 다음 한 기간의 고저로만 채점한다. 지평이 어긋나면
                #   확률이 통째로 과대평가되고 신뢰도 곡선이 거짓말을 한다 —
                #   주봉에서 실제로 3주 확률을 1주로 채점하고 있었다.
                # model_inputs 는 **여기서 다시 꺼낸다**(2026-09-05 수정).
                # 위쪽 p_touch 루프의 mi 를 그대로 쓰면, 레벨이 없어 그 루프를 한 번도
                # 돌지 않은 항목에서 **직전 종목의 mi** 가 남아 엉뚱한 값으로 대조한다.
                pmi = it.get('model_inputs')
                if k and pmi:
                    for side, dirn in (('up', 'up'), ('dn', 'dn')):
                        rep = tm.predict(k, dirn, pmi, 1)
                        for fld, want2 in ((side, rep['p']), (side + '_base', rep['p_base'])):
                            got2 = blk.get(fld)
                            if got2 is not None and abs(got2 - want2) > 0.15:
                                err.append('%s — p_probe[%s].%s %s 가 1세션 표(%s)와 다르다'
                                           % (nm, key, fld, got2, want2))

        # 8) 확률 범위
        for label, v in [('direction_prob', it.get('direction_prob'))]:
            if v is not None and not (0 <= v <= 1):
                err.append('%s — %s 범위 이탈 %s' % (nm, label, v))

    # 9) 레벨 콜은 전부 원장에 등록돼야 한다
    #    **방향 단위로 센다**(2026-08-22 수정). 항목 단위로 세던 때는 위·아래 확률을 둘 다
    #    내고 원장에는 주 방향만 넣어도 통과했고, 그 바람에 예측의 절반이 영원히 채점되지
    #    않았다(8/21 회차만 일봉 15건·주봉 15건). 확률을 냈으면 채점해야 한다.
    if strict_ledger:
        lv = [(it['code'], d) for it in e['items']
              for d, pr in (it.get('p_touch') or {}).items()
              if pr.get('level') is not None]
        reg = [c for c in ledger.get('active', []) if c.get('opened') == e['asof']]
        if len(reg) != len(lv):
            miss = sorted(set(lv) - {(c.get('code'), c.get('dir')) for c in reg})
            err.append('%s — 레벨 콜 %d방향인데 원장 등록 %d건 (채점기가 못 본다)%s'
                       % (tag, len(lv), len(reg),
                          ' · 누락 ' + ', '.join('%s/%s' % m for m in miss[:6]) if miss else ''))
        by_code = {it['code']: it for it in e['items']}
        for c in reg:
            for k in ('code', 'dir', 'level', 'horizon_sessions', 'p', 'p_base', 'status'):
                if c.get(k) is None:
                    err.append('%s — 원장 %s 항목에 %s 누락' % (tag, c.get('code'), k))
            # 12) 원장 값이 항목과 같은가 — 다르면 채점이 딴 레벨을 본다
            it = by_code.get(c.get('code'))
            if it is None:
                err.append('%s — 원장에 로스터 밖 종목 %s 가 있다' % (tag, c.get('code')))
                continue
            blk = (it.get('p_touch') or {}).get(c.get('dir'))
            if blk is None:
                err.append('%s — 원장 %s %s 방향에 대응하는 p_touch 가 없다'
                           % (tag, it.get('name'), c.get('dir')))
                continue
            for k in ('level', 'p', 'p_base', 'horizon_sessions'):
                if c.get(k) != blk.get(k):
                    err.append('%s — 원장 %s %s 가 항목과 다르다 (원장 %s / 항목 %s)'
                               % (tag, it.get('name'), k, c.get(k), blk.get(k)))
            if c.get('dist_sigma') is not None and blk.get('dist_sigma') is not None \
                    and abs(c['dist_sigma'] - blk['dist_sigma']) > SIG_TOL:
                err.append('%s — 원장 %s dist_sigma 가 항목과 다르다 (%s / %s)'
                           % (tag, it.get('name'), c['dist_sigma'], blk['dist_sigma']))
    return err, warn


MIN_WEEK_BARS = tm.MIN_WEEK_BARS   # 주봉 ATR 창 하한 — 모듈이 진실


def check_weekly(e, ledger):
    """주봉 회차 검사. 일봉과 규격이 다른 곳(주 단위 만기·주봉 표·거래량 무효)을 따로 본다."""
    err, warn = [], []
    tag = e['asof']
    lv = 0

    for it in e['items']:
        nm = '%s(주봉) %s' % (tag, it.get('name', it['code']))
        mi = it.get('model_inputs') or {}
        wb = mi.get('watr_bars')
        short = wb is not None and wb < MIN_WEEK_BARS

        if wb is None:
            err.append('%s — model_inputs.watr_bars 없음 (ATR 창 검증 불가)' % nm)
        if short and not it.get('atr_insufficient'):
            err.append('%s — 주봉 %s개(<%d)인데 atr_insufficient 표시가 없다' % (nm, wb, MIN_WEEK_BARS))
        if short and (it.get('p_touch') or it.get('p_probe')):
            err.append('%s — ATR 창이 짧은데 확률이 매겨져 있다 (표와 자가 어긋난다)' % nm)
        if not short and not it.get('p_probe'):
            err.append('%s — p_probe 없음 (채점 집합에서 누락된다)' % nm)

        h = tm.horizon_weeks(it.get('horizon'))
        sg = it.get('sigma') or [None, None]
        pt = it.get('p_touch') or {}

        for i, (dirn, fld) in enumerate((('up', 'resist'), ('dn', 'support'))):
            blk = pt.get(dirn)
            if blk is None:
                continue
            if it.get(fld) is None:
                err.append('%s — p_touch.%s 있는데 %s 가 null (채점 불가)' % (nm, dirn, fld))
            if blk.get('p') is None or blk.get('p_base') is None:
                err.append('%s — p_touch.%s 에 p/p_base 짝이 없다' % (nm, dirn))
            if blk.get('horizon_weeks') != h:
                err.append('%s — p_touch.%s horizon_weeks %s != item horizon %s(%d주)'
                           % (nm, dirn, blk.get('horizon_weeks'), it.get('horizon'), h))
            cur_table = tag >= TABLE_V62_FROM
            exp = tm.base_p_w(blk.get('dist_sigma'), dirn, h)
            if cur_table and exp is not None and blk.get('p_base') is not None \
                    and abs(exp - blk['p_base']) > 0.15:
                err.append('%s — p_base %s != 주봉표 %s' % (nm, blk['p_base'], exp))
            rep = tm.cond_p_w(blk.get('dist_sigma'), dirn, mi.get('wrngatr'), mi.get('watrpct'), h)
            if cur_table and rep is not None and blk.get('p') is not None and abs(rep - blk['p']) > 0.15:
                err.append('%s — p %s 가 저장된 입력으로 재현되지 않는다(계산 %s)' % (nm, blk['p'], rep))

            lvl, cl, atr, ds = it.get(fld), it.get('close'), it.get('atr'), blk.get('dist_sigma')
            if None not in (lvl, cl, atr, ds) and atr:
                signed = (lvl - cl) / atr if dirn == 'up' else (cl - lvl) / atr
                if signed < 0:
                    err.append('%s — %s 가 종가의 반대쪽에 있다' % (nm, fld))
                elif abs(signed - ds) > SIG_TOL:
                    err.append('%s — dist_sigma %.2f != (레벨-종가)/주봉ATR %.3f' % (nm, ds, signed))
                if isinstance(sg[i], (int, float)) and abs(sg[i] - ds) > SIG_TOL:
                    err.append('%s — sigma[%d]=%s 가 p_touch.%s 와 다르다' % (nm, i, sg[i], dirn))

            src = blk.get('src')
            if src is None:
                err.append('%s — p_touch.%s 에 src 없음' % (nm, dirn))
            if ds is not None and ds > MAX_SIGMA:
                err.append('%s — %s 거리 %.2f 가 상한 %.1f 초과' % (nm, dirn, ds, MAX_SIGMA))
            if src == 'line' and ds is not None and ds < MIN_LINE_SIGMA:
                err.append('%s — 라인인데 %.2f 로 하한 %.1f 미만' % (nm, ds, MIN_LINE_SIGMA))

        pb = it.get('p_probe')
        if pb:
            for key, blk in pb.items():
                for k in ('up', 'dn', 'up_base', 'dn_base', 'up_level', 'dn_level'):
                    if blk.get(k) is None:
                        err.append('%s — p_probe[%s].%s 누락' % (nm, key, k))
                k = {'0p5': 0.5, '1p0': 1.0}.get(key)
                if k and it.get('close') and it.get('atr'):
                    for side, want in (('up_level', it['close'] + k * it['atr']),
                                       ('dn_level', it['close'] - k * it['atr'])):
                        got = blk.get(side)
                        if got is not None and abs(got - want) > max(1.0, it['atr'] * 0.005):
                            err.append('%s — p_probe[%s].%s 가 종가±%.1f주봉ATR 과 다르다'
                                       % (nm, key, side, k))
                if k:
                    for side, dirn in (('up', 'up'), ('dn', 'dn')):
                        rep = tm.predict_w(k, dirn, mi, 1)
                        for fld, want2 in ((side, rep['p']), (side + '_base', rep['p_base'])):
                            got2 = blk.get(fld)
                            if got2 is not None and abs(got2 - want2) > 0.15:
                                err.append('%s — p_probe[%s].%s %s 가 1주 표(%s)와 다르다'
                                           % (nm, key, fld, got2, want2))

        if it.get('prior') is not None and it.get('distance_sigma') is not None \
                and it['call'] in LEVEL_CALLS:
            dirn = 'up' if it['call'] == 'up_test' else 'dn'
            exp = round(tm.base_p_w(it['distance_sigma'], dirn, h))
            if tag >= TABLE_V62_FROM and abs(exp - it['prior']) > 1:
                err.append('%s — prior %s != 주봉표 %s' % (nm, it['prior'], exp))

        # 방향 단위로 센다(2026-08-22 수정) — 일봉 9)번과 같은 이유다.
        if not short:
            lv += sum(1 for pr in (it.get('p_touch') or {}).values()
                      if pr.get('level') is not None)

    reg = [c for c in ledger.get('active', []) if c.get('opened') == tag]
    if len(reg) != lv:
        want = {(it['code'], d) for it in e['items']
                for d, pr in (it.get('p_touch') or {}).items() if pr.get('level') is not None}
        miss = sorted(want - {(c.get('code'), c.get('dir')) for c in reg})
        err.append('%s(주봉) — 레벨 콜 %d방향인데 weekly_calls 등록 %d건%s'
                   % (tag, lv, len(reg),
                      ' · 누락 ' + ', '.join('%s/%s' % m for m in miss[:6]) if miss else ''))
    by = {it['code']: it for it in e['items']}
    for c in reg:
        for k in ('code', 'dir', 'level', 'horizon_weeks', 'p', 'p_base', 'status'):
            if c.get(k) is None:
                err.append('%s(주봉) — 원장 %s 에 %s 누락' % (tag, c.get('code'), k))
        it = by.get(c.get('code'))
        if it is None:
            err.append('%s(주봉) — 원장에 로스터 밖 종목 %s' % (tag, c.get('code')))
            continue
        blk = (it.get('p_touch') or {}).get(c.get('dir'))
        if blk is None:
            err.append('%s(주봉) — 원장 %s %s 에 대응하는 p_touch 없음'
                       % (tag, it.get('name'), c.get('dir')))
            continue
        for k in ('level', 'p', 'p_base'):
            if c.get(k) != blk.get(k):
                err.append('%s(주봉) — 원장 %s %s 가 항목과 다르다 (%s / %s)'
                           % (tag, it.get('name'), k, c.get(k), blk.get(k)))
        if c.get('horizon_weeks') != blk.get('horizon_weeks'):
            err.append('%s(주봉) — 원장 %s horizon_weeks 가 항목과 다르다' % (tag, it.get('name')))

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

    # ── 주봉 회차 ──
    wled = d.get('weekly_calls', {})
    wents = d.get('weekly_entries', [])
    if wents:
        er, wr = check_weekly(wents[-1], wled)
        all_err += er
        all_warn += wr
        for c in wled.get('active', []):
            if c.get('weeks_elapsed', 0) > c.get('horizon_weeks', 1):
                all_err.append('주봉원장 %s — 만기(%d주) 지났는데 open 상태'
                               % (c.get('code'), c.get('horizon_weeks', 1)))
        if len(wents) >= 2 and wents[-2].get('scored') is None:
            all_err.append('%s 주봉 회차가 채점되지 않은 채 다음 주봉 회차가 추가됐다'
                           % wents[-2]['asof'])
        # 오염 검사 — 주봉 콜이 일봉 원장에 섞이면 하루마다 만기가 깎여 1~3'일'만에 닫힌다
        for c in ledger.get('active', []):
            if 'horizon_weeks' in c:
                all_err.append('일봉 원장에 주봉 콜(%s)이 섞였다 — 하루마다 만기가 깎인다'
                               % c.get('code'))
        for c in wled.get('active', []):
            if 'horizon_sessions' in c:
                all_err.append('주봉 원장에 일봉 콜(%s)이 섞였다' % c.get('code'))

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

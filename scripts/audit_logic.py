# 로직 감사 — 기존 검사기 3종이 보지 않는 곳을 훑는다
#
# 왜 있나 (2026-08-22): validate_predictions 는 규격 위반을, check_report 는 표-데이터
#   대조를, check_docs_sync 는 문서-코드 일치를 본다. 그 사이에 빈 곳이 있다 —
#   원장 필드 완전성, 일봉·주봉 원장 교차 오염, 중복 콜, 확률의 모듈 재계산 대조,
#   레벨-종가 순서, 주봉 항목에 일봉 ATR 이 섞였는지 같은 것들이다.
#
#   이 회차에 실제로 있었던 사고가 전부 그 빈 곳에서 나왔다 — 반대편 콜 미등록,
#   call 라벨 오탈자, float 레벨, 섹터 헤더 중복.
#
# 원칙 — **통과는 검출력을 뜻하지 않는다.** 새 검사를 넣으면 주입 시험으로 확인한다.
#
# 사용법
#   python scripts/audit_logic.py [--date 2026-08-21]

import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_model as tm

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PRED = os.path.join(ROOT, 'data', 'predictions.json')


def main():
    date = sys.argv[sys.argv.index('--date') + 1] if '--date' in sys.argv else None
    d = json.load(open(PRED, encoding='utf-8'))
    ent = d['entries'][-1] if date is None else next(e for e in d['entries'] if e['asof'] == date)
    went = next((e for e in d['weekly_entries'] if e['asof'] == ent['asof']), None)
    date = ent['asof']
    bad = []

    def need(cond, msg):
        if not cond:
            bad.append(msg)

    # ── 1) 원장 필드 완전성 — score_touch 가 쓰는 키가 다 있는가 ────────────
    for led, hkey, ekey, label in ((d['open_calls'], 'horizon_sessions', 'sessions_elapsed', '일봉'),
                                   (d['weekly_calls'], 'horizon_weeks', 'weeks_elapsed', '주봉')):
        for c in led['active']:
            nm = '%s %s/%s' % (label, c.get('name'), c.get('dir'))
            for k in ('code', 'dir', 'level', 'p', 'p_base', 'status', hkey):
                need(c.get(k) is not None, '%s — 원장 필드 %s 누락' % (nm, k))
            need(isinstance(c.get('level'), int),
                 '%s — level 이 정수가 아니다(%r)' % (nm, c.get('level')))
            need(c.get('dir') in ('up', 'dn'), '%s — dir 값이 이상하다' % nm)

    # ── 2) 두 원장의 교차 오염 ─────────────────────────────────────────────
    for c in d['open_calls']['active']:
        need('horizon_weeks' not in c,
             '일봉 원장에 주봉 키가 있다 — %s/%s' % (c.get('name'), c.get('dir')))
    for c in d['weekly_calls']['active']:
        need('horizon_sessions' not in c,
             '주봉 원장에 일봉 키가 있다 — %s/%s' % (c.get('name'), c.get('dir')))

    # ── 3) 중복 콜 ─────────────────────────────────────────────────────────
    for led, label in ((d['open_calls'], '일봉'), (d['weekly_calls'], '주봉')):
        seen = {}
        for c in led['active']:
            k = (c.get('opened'), c.get('code'), c.get('dir'))
            seen[k] = seen.get(k, 0) + 1
        for k, n in seen.items():
            need(n == 1, '%s 원장 중복 콜 %s x%d' % (label, k, n))

    # ── 4) 확률을 모듈로 재계산해 대조 (문서에서 베낀 숫자 색출) ───────────
    for items, weekly, label in ((ent['items'], False, '일봉'),
                                 (went['items'] if went else [], True, '주봉')):
        for it in items:
            nm = '%s %s' % (label, it.get('name'))
            mi = it.get('model_inputs') or {}
            for dirn, pr in (it.get('p_touch') or {}).items():
                ds = pr.get('dist_sigma')
                if ds is None:
                    continue
                if weekly:
                    q = tm.predict_w(ds, dirn, mi, pr.get('horizon_weeks', 1))
                else:
                    q = tm.predict(ds, dirn, mi, pr.get('horizon_sessions', 1))
                need(abs(q['p'] - pr['p']) < 0.06,
                     '%s %s — p %.1f != 모듈 %.1f' % (nm, dirn, pr['p'], q['p']))
                need(abs(q['p_base'] - pr['p_base']) < 0.06,
                     '%s %s — p_base %.1f != 모듈 %.1f' % (nm, dirn, pr['p_base'], q['p_base']))
                # dist_sigma 검산
                if it.get('close') and it.get('atr'):
                    want = abs(pr['level'] - it['close']) / float(it['atr'])
                    need(abs(want - ds) < 0.02,
                         '%s %s — dist_sigma %.3f != |레벨-종가|/ATR %.3f' % (nm, dirn, ds, want))
                # 레벨 방향
                if it.get('close'):
                    if dirn == 'up':
                        need(pr['level'] > it['close'], '%s up 레벨이 종가 아래다' % nm)
                    else:
                        need(pr['level'] < it['close'], '%s dn 레벨이 종가 위다' % nm)
                # 존·라인 규칙
                if pr.get('src') == 'line':
                    need(ds >= 0.5, '%s %s — 라인인데 %.3fσ (0.5σ 하한 위반)' % (nm, dirn, ds))
                need(ds <= 3.0, '%s %s — %.3fσ (3σ 상한 위반)' % (nm, dirn, ds))

    # ── 5) p_probe 레벨 검산 ───────────────────────────────────────────────
    for it in ent['items']:
        pb = it.get('p_probe') or {}
        for tag, k in (('0p5', 0.5), ('1p0', 1.0)):
            blk = pb.get(tag)
            if not blk or not it.get('close') or not it.get('atr'):
                continue
            for side, want in (('up_level', it['close'] + k * it['atr']),
                               ('dn_level', it['close'] - k * it['atr'])):
                got = blk.get(side)
                need(got is not None and abs(got - want) <= max(1, it['atr'] * 0.005),
                     '%s — p_probe[%s].%s %s != 종가±%.1fσ %d'
                     % (it['name'], tag, side, got, k, round(want)))

    # ── 6) 주봉 항목에 일봉 자가 섞였는가 ──────────────────────────────────
    if went:
        by = {i['code']: i for i in ent['items']}
        for w in went['items']:
            dl = by.get(w['code'])
            if dl and w.get('atr') and dl.get('atr'):
                need(w['atr'] != dl['atr'],
                     '주봉 %s — ATR 이 일봉과 같다(자를 섞었다)' % w['name'])
            mi = w.get('model_inputs') or {}
            need('watrpct' in mi or w.get('atr_insufficient'),
                 '주봉 %s — model_inputs 에 주봉 지표가 없다' % w['name'])
            need(mi.get('watr_bars', 999) >= tm.MIN_WEEK_BARS or w.get('atr_insufficient'),
                 '주봉 %s — 주봉 창 %s < %d 인데 확률을 냈다'
                 % (w['name'], mi.get('watr_bars'), tm.MIN_WEEK_BARS))

    # ── 7) 항목-원장 1:1 ───────────────────────────────────────────────────
    for items, led, label in ((ent['items'], d['open_calls'], '일봉'),
                              (went['items'] if went else [], d['weekly_calls'], '주봉')):
        want = {(i['code'], dd) for i in items
                for dd, pr in (i.get('p_touch') or {}).items() if pr.get('level') is not None}
        have = {(c['code'], c['dir']) for c in led['active'] if c.get('opened') == date}
        for k in sorted(want - have):
            need(False, '%s — 항목에 있는데 원장에 없다: %s/%s' % (label, k[0], k[1]))
        for k in sorted(have - want):
            need(False, '%s — 원장에 있는데 항목에 없다: %s/%s' % (label, k[0], k[1]))

    # ── 8) call 라벨 ───────────────────────────────────────────────────────
    OK = ('up_test', 'down_test', 'no_level')
    for items, label in ((ent['items'], '일봉'), (went['items'] if went else [], '주봉')):
        for it in items:
            need(it.get('call') in OK,
                 '%s %s — call 라벨 %r 은 규격 밖' % (label, it.get('name'), it.get('call')))

    print('로직 감사 (%s · 일봉 %d항목 / 주봉 %d항목) — 결함 %d건'
          % (date, len(ent['items']), len(went['items']) if went else 0, len(bad)))
    for b in bad[:40]:
        print('  [결함] ' + b)
    if len(bad) > 40:
        print('  … 외 %d건' % (len(bad) - 40))
    if not bad:
        print('통과')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

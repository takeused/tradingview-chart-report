# v6.1 도달확률 채점기 — p_probe(고정거리)와 open_calls(차트 레벨)를 Brier·신뢰도로 채점한다
#
# 왜 이게 있나: v5까지는 회차당 실제 채점이 0~2건이라 표본이 안 쌓였고,
#   2~3세션 이연분 27건은 만기 채점 기록이 아예 없었다(열고 안 닫음).
#   p_probe는 레벨 유무와 무관하게 매 회차 88건을 강제로 채점하고,
#   open_calls는 만기가 박힌 원장이라 닫지 않고 넘어갈 수 없다.
#
# 사용법
#   python scripts/score_touch.py <actuals.json> [--session YYYY-MM-DD] [--write]
#   actuals.json = {"005930": {"hi": 275500, "lo": 266000, "close": 274500}, ...}
#     (기준일 다음 거래일 값. 구 포맷 next_hi/next_lo도 받는다.)
#   --write 를 주면 채점 결과를 predictions.json의 해당 entry.scored 에 기록한다.
#
# 핵심 판정: 조건부 모델이 '거리 단독' 기준선을 이기는가. 못 이기면 조건부를 폐기한다.

import json, sys, os, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_model as tm

PRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'predictions.json')
MIN_BIN = 10  # 신뢰도 곡선에서 이보다 적은 구간은 노이즈라 따로 표시한다


def brier(pairs):
    return round(sum((p - y) ** 2 for p, y in pairs) / len(pairs), 5) if pairs else None


def _logit(p):
    p = min(0.998, max(0.002, p))
    return math.log(p / (1 - p))


def shift_null(cond, base):
    """기준선을 조건부의 '평균 로짓 이동량'만큼 일괄로 옮긴 귀무모형.

    조건부가 이것을 못 이기면 그 회차의 우세는 종목별 구별이 아니라 수준 이동일 뿐이다.
    2026-08-19 회차가 정확히 그 경우였다(88건 중 84건이 한 방향으로 조정됐다).
    """
    if not cond or len(cond) != len(base):
        return None
    delta = sum(_logit(c) - _logit(b) for (c, _), (b, _) in zip(cond, base)) / len(cond)
    shifted = [(1 / (1 + math.exp(-(_logit(b) + delta))), y) for b, y in base]
    n_lower = sum(1 for (c, _), (b, _) in zip(cond, base) if c < b)
    return {
        'mean_logit_shift': round(delta, 4),
        'pct_adjusted_down': round(n_lower / len(cond) * 100, 1),
        'actual_rate_pct': round(sum(y for _, y in cond) / len(cond) * 100, 1),
        'brier_uniform_shift': brier(shifted),
    }


def _verdict(bc, bb, sn):
    """기준선과 '일괄 이동 귀무모형' 을 모두 이겨야 실력으로 본다."""
    if bc is None or not bb:
        return '판정 불가'
    if bc >= bb:
        return '조건부가 기준선에 못 미침 — 누적되면 폐기 검토'
    bu = (sn or {}).get('brier_uniform_shift')
    if bu is None:
        return '조건부가 기준선을 이김'
    if bc < bu:
        return '조건부가 기준선과 일괄이동 귀무모형을 모두 이김 — 종목별 구별이 있다'
    return ('조건부가 기준선은 이겼으나 일괄이동 귀무모형은 못 이김 '
            '— 이 회차의 우세는 수준 이동일 뿐 실력의 근거가 아니다')


def reliability(pairs):
    bins = ((0, .2), (.2, .35), (.35, .5), (.5, .65), (.65, .8), (.8, 1.01))
    out = []
    for lo, hi in bins:
        s = [(p, y) for p, y in pairs if lo <= p < hi]
        if not s:
            continue
        row = {'bin': '%d~%d%%' % (lo * 100, hi * 100), 'n': len(s),
               'pred': round(sum(p for p, _ in s) / len(s) * 100, 1),
               'actual': round(sum(y for _, y in s) / len(s) * 100, 1)}
        if len(s) < MIN_BIN:
            row['noisy'] = True
        out.append(row)
    return out


def _hl(a):
    """actuals 항목에서 고가/저가를 꺼낸다. 구/신 키를 모두 받는다."""
    hi = a.get('hi', a.get('next_hi'))
    lo = a.get('lo', a.get('next_lo'))
    return hi, lo


def score_probe(entry, actuals):
    """고정거리 프로브 — 레벨 유무와 무관하게 전 종목이 채점된다(1세션)."""
    cond, base = [], []
    for it in entry.get('items', []):
        a = actuals.get(it['code'])
        pb = it.get('p_probe')
        if not a or not pb:
            continue
        hi, lo = _hl(a)
        if hi is None or lo is None:
            continue
        for blk in pb.values():
            up = 1 if hi >= blk['up_level'] else 0
            dn = 1 if lo <= blk['dn_level'] else 0
            cond += [(blk['up'] / 100, up), (blk['dn'] / 100, dn)]
            base += [(blk['up_base'] / 100, up), (blk['dn_base'] / 100, dn)]
    bc, bb = brier(cond), brier(base)
    sn = shift_null(cond, base)
    bu = (sn or {}).get('brier_uniform_shift')
    return {
        'n': len(cond),
        'brier_conditional': bc,
        'brier_distance_only': bb,
        'skill_vs_baseline_pct': round((bb - bc) / bb * 100, 2) if bc is not None and bb else None,
        'shift_null': sn,
        'skill_vs_uniform_shift_pct': round((bu - bc) / bu * 100, 2) if bc is not None and bu else None,
        'verdict': _verdict(bc, bb, sn),
        'reliability': reliability(cond),
    }


def close_open_calls(ledger, actuals, session_date,
                     hkey='horizon_sessions', ekey='sessions_elapsed'):
    """만기 도래분을 종결한다. 만기 전이면 경과 세션만 올리고 open으로 남긴다.

    주봉 원장도 같은 로직으로 닫는다(hkey/ekey 만 'horizon_weeks'/'weeks_elapsed' 로 바꾼다).
    구현을 복사하지 않는 이유는 v6.1 감사에서 배운 것과 같다 — 같은 로직을 두 군데 두면
    반드시 어긋난다. 주봉 콜을 일봉 원장에 넣으면 하루마다 만기가 깎여 1~3'일'만에 닫힌다.
    """
    closed, still_open, scored_pairs, base_pairs = [], [], [], []
    no_data = []
    for c in ledger.get('active', []):
        a = actuals.get(c['code'])
        hi, lo = _hl(a) if a else (None, None)
        if hi is None or lo is None:
            # 로스터에서 빠졌거나 값이 없는 콜은 **닫지 않는다**(2026-09-05 수정).
            # 예전에는 status='no_data' 로 종결해 채점 없이 사라졌는데, 성적이 나쁜 종목을
            # 로스터에서 빼면 표본이 저절로 좋아지는 구조였다. 열어 두고 세어서 보고한다.
            c['no_data_sessions'] = c.get('no_data_sessions', 0) + 1
            no_data.append('%s/%s' % (c.get('name', c.get('code')), c.get('dir')))
            still_open.append(c)
            continue
        c[ekey] = c.get(ekey, 0) + 1
        # 실제로 반영한 세션을 남긴다 — 회차를 건너뛰면 여기 날짜가 비어 증거가 된다
        c.setdefault('sessions_seen', []).append(session_date)
        c.setdefault('run_hi', hi)
        c.setdefault('run_lo', lo)
        c['run_hi'] = max(c['run_hi'], hi)
        c['run_lo'] = min(c['run_lo'], lo)
        touched = (c['run_hi'] >= c['level']) if c['dir'] == 'up' else (c['run_lo'] <= c['level'])
        if touched:
            c['status'] = 'touched'
            c['touched_on'] = session_date
            closed.append(c)
        elif c[ekey] >= c.get(hkey, 1):
            c['status'] = 'expired'
            c['expired_on'] = session_date
            closed.append(c)
        else:
            still_open.append(c)
        # 만기에 도달한 건만 확률 채점에 넣는다(중도 종결은 편향)
        # **쌍으로만 넣는다**(2026-09-05 수정) — 한쪽만 있으면 두 리스트 길이가 어긋나
        # shift_null 이 조용히 None 이 되고, 귀무모형 판정이 사라진 줄도 모르게 된다.
        if c['status'] in ('touched', 'expired'):
            y = 1 if c['status'] == 'touched' else 0
            if c.get('p') is not None and c.get('p_base') is not None:
                scored_pairs.append((c['p'] / 100, y))
                base_pairs.append((c['p_base'] / 100, y))
    ledger['active'] = still_open
    assert len(scored_pairs) == len(base_pairs)
    bc, bb = brier(scored_pairs), brier(base_pairs)
    sn = shift_null(scored_pairs, base_pairs)
    bu = (sn or {}).get('brier_uniform_shift')
    return {
        'shift_null': sn,
        'skill_vs_uniform_shift_pct': round((bu - bc) / bu * 100, 2) if bc is not None and bu else None,
        'verdict': _verdict(bc, bb, sn),
        'closed': len(closed),
        'still_open': len(still_open),
        'no_data_open': len(no_data),
        'no_data_calls': sorted(set(no_data))[:20],
        'touched': sum(1 for c in closed if c['status'] == 'touched'),
        'expired': sum(1 for c in closed if c['status'] == 'expired'),
        'brier_conditional': bc,
        'brier_distance_only': bb,
        'rows': [{k: c.get(k) for k in
                  ('opened', 'code', 'name', 'dir', 'level', 'dist_sigma',
                   hkey, 'p', 'p_base', 'status')} for c in closed],
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    write = '--write' in sys.argv
    session = None
    if '--session' in sys.argv:
        session = sys.argv[sys.argv.index('--session') + 1]
    if not args:
        print('usage: score_touch.py <actuals.json> [--session YYYY-MM-DD] [--write]')
        sys.exit(1)

    actuals = json.load(open(args[0], encoding='utf-8'))
    d = json.load(open(PRED, encoding='utf-8'))
    entry = d['entries'][-1]

    # 날짜 가드 — 엉뚱한 회차를 조용히 채점하는 사고를 막는다
    expected = entry.get('next_session')
    if not session:
        print('[경고] --session 이 없다. 회차의 next_session(%s)으로 간주한다 — '
              '거래일을 건너뛴 채점이면 그 세션의 고저가 도달 판정에서 통째로 빠진다.' % expected)
    if session and expected and session != expected:
        print('[중단] 채점 대상 회차의 next_session은 %s인데 --session %s가 들어왔다.' % (expected, session))
        print('       직전 회차를 채점하려는 것이 맞는지 확인할 것. 신규 entry를 먼저 추가했다면 순서가 잘못됐다.')
        sys.exit(2)
    if entry.get('scored') is not None:
        print('[중단] 마지막 entry(%s)는 이미 채점됐다. 신규 entry 추가 전에 채점해야 한다.' % entry['asof'])
        sys.exit(2)

    res = {'asof': entry['asof'], 'scored_on': session or expected,
           'model': tm.META['version'],
           'probe': score_probe(entry, actuals),
           'open_calls': close_open_calls(d.setdefault('open_calls', {'active': []}), actuals,
                                          session or expected),
           '_caveat': ('회차 내 관측은 독립이 아니다(같은 날·같은 시장). 한 회차 Brier 차이로 '
                       '결론 내지 말고 누적 10회차 이후에 판단한다.')}

    print(json.dumps({k: v for k, v in res.items() if k != 'open_calls'}, ensure_ascii=False, indent=1))
    print(json.dumps({'open_calls': {k: v for k, v in res['open_calls'].items() if k != 'rows'}},
                     ensure_ascii=False, indent=1))

    if write:
        entry['scored'] = res
        from json_io import dump_predictions
        dump_predictions(d, PRED)
        print('\n기록 완료 — %s entry.scored' % entry['asof'])
    return res


if __name__ == '__main__':
    main()

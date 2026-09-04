# 수집한 원자료로 v6.1 항목(일봉 + 주봉)을 만든다 — 로스터 증설용
#
# 왜 있나 (2026-08-22): 8/21 회차에 8종목을 덧붙이면서 레벨 선정·확률 계산을 손으로 하면
#   반드시 틀린다(0.5σ 하한, 3σ 상한, N겹 계산, 세션수-표 일치). 전부 코드로 한다.
#   확률은 문서에서 베끼지 않고 scripts/touch_model.py 를 import 해서 낸다(v6 사고의 원인).
#
# 입력 — 스크래치패드의 metrics_daily.json · metrics_weekly.json · <code>.json · w_<code>.json
# 출력 — items_new.json (predictions.json 의 entry.items 에 붙일 형태 + 원장 등록분)

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_model as tm

SCR = sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else '.'
# 종목은 --names "코드:이름,코드:이름" 으로 받는다. 하드코딩하면 다음 증설 때 또 고쳐야 한다.
NAMES = (dict(x.split(':') for x in sys.argv[sys.argv.index('--names') + 1].split(','))
         if '--names' in sys.argv else
         {'403870': 'HPSP', '214450': '파마리서치', '241710': '코스메카코리아',
          '196170': '알테오젠', '039490': '키움증권', '003230': '삼양식품',
          '002380': 'KCC', '192820': '코스맥스'})
OPENED = sys.argv[sys.argv.index('--date') + 1] if '--date' in sys.argv else '2026-08-21'
SESSIONS = 3          # 기본 지평. 0.5σ 미만 근접 레벨은 2세션으로 줄인다(기존 회차 관행)


def load(name):
    p = os.path.join(SCR, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def pick_level(close, atr, zones, lines, direction):
    """존(3σ 이내)과 라인(0.5σ 이상) 중 **가까운 쪽**을 고른다.

    존은 경계를 레벨로 쓴다(위쪽이면 zone low, 아래쪽이면 zone high).
    종가를 품는 존이 여러 개면 가장 좁은 것을 쓴다 — 동점 규칙을 정해 두지 않으면
    회차마다 결과가 달라진다.
    """
    cands = []
    for hi, lo in zones or []:
        if lo <= close <= hi:                      # 종가가 존 안이면 경계를 레벨로
            lvl = hi if direction == 'up' else lo
        else:
            lvl = lo if direction == 'up' else hi
        if direction == 'up' and lvl <= close:
            continue
        if direction == 'dn' and lvl >= close:
            continue
        d = abs(lvl - close) / atr
        if d <= 3.0:
            cands.append((d, lvl, 'zone', hi - lo))
    for lv in lines or []:
        if direction == 'up' and lv <= close:
            continue
        if direction == 'dn' and lv >= close:
            continue
        d = abs(lv - close) / atr
        if 0.5 <= d <= 3.0:                        # 0.5σ 미만은 노이즈라 쓰지 않는다
            cands.append((d, lv, 'line', 0))
    if not cands:
        return None
    cands.sort(key=lambda x: (round(x[0], 6), x[3]))
    d, lvl, src, _ = cands[0]
    # 레벨은 정수 원으로 맞춘다 — 수정주가에서 온 소수점 레벨(333,076.59)은 호가로
    # 존재하지 않고, 리포트·원장·채점기가 서로 다른 반올림을 하면 값이 갈린다.
    lvl = int(round(lvl))          # float 로 두면 표기(7,750)와 값(7750.0)이 갈려 검사기가 잡는다
    d = abs(lvl - close) / atr
    n = 0
    if src == 'line':
        n = sum(1 for lv in lines if abs(lv - lvl) <= 0.15 * atr)
    return {'level': lvl, 'dist_sigma': round(d, 3), 'src': src, 'stack': n}


def main():
    md = load('metrics_daily.json')
    mw = load('metrics_weekly.json')
    idx = {'P': md['KOSPI']['chg'], 'Q': md['KOSDAQ']['chg']}
    items, calls, wcalls, wrows = [], [], [], []

    for code in sorted(NAMES):
        m = md[code]
        atr, close = float(m['atr']), float(m['close'])
        zl = load('%s.json' % code) or {}
        up = pick_level(close, atr, zl.get('zones'), zl.get('lines'), 'up')
        dn = pick_level(close, atr, zl.get('zones'), zl.get('lines'), 'dn')
        exc = tm.excess_return(m['chg'], idx[m['mkt']], m['beta'])
        bdg, sig = tm.badge(exc, m['atrpct'])
        mi = {'volx': m['volx'], 'rngatr': m['rngatr'], 'atrpct': m['atrpct'],
              'atr_bars': m['bars'], 'atr_method': 'wilder14'}

        pt = {}
        # 지평은 **항목당 하나**다. 방향별로 따로 정하면 위·아래가 0.5σ 를 사이에 두고
        # 갈릴 때 item['horizon'] 과 p_touch 의 세션 수가 어긋난다(2026-08-24 삼양식품).
        near = min([s['dist_sigma'] for s in (up, dn) if s] or [9.9])
        sess = 2 if near < 0.5 else SESSIONS
        for d, sel in (('up', up), ('dn', dn)):
            if not sel:
                continue
            pr = tm.predict(sel['dist_sigma'], d, mi, sess)
            pr['level'] = sel['level']
            pr['src'] = sel['src']
            pt[d] = pr
            calls.append({'opened': OPENED, 'code': code, 'name': NAMES[code], 'dir': d,
                          'level': sel['level'], 'dist_sigma': sel['dist_sigma'],
                          'horizon_sessions': sess, 'expiry_after_sessions': sess,
                          'p': pr['p'], 'p_base': pr['p_base'], 'sessions_elapsed': 0,
                          'status': 'open', 'model_inputs': mi})

        probe = {}
        for tag, k in (('0p5', 0.5), ('1p0', 1.0)):
            pu, pd = tm.predict(k, 'up', mi, 1), tm.predict(k, 'dn', mi, 1)
            probe[tag] = {'up': pu['p'], 'dn': pd['p'], 'up_base': pu['p_base'],
                          'dn_base': pd['p_base'],
                          'up_level': int(round(close + k * atr)),
                          'dn_level': int(round(close - k * atr))}

        main_dir = 'up' if (up and (not dn or up['dist_sigma'] <= dn['dist_sigma'])) else 'dn'
        it = {'code': code, 'name': NAMES[code],
              'market': 'KOSPI' if m['mkt'] == 'P' else 'KOSDAQ',
              'close': int(close), 'atr': int(atr), 'chg': m['chg'],
              'line_provenance': 'fresh',
              'resist': up['level'] if up else None,
              'support': dn['level'] if dn else None,
              'src': (up or dn or {}).get('src'),
              'sigma': [up['dist_sigma'] if up else None, dn['dist_sigma'] if dn else None],
              'call': ('up_test' if main_dir == 'up' else 'down_test') if pt else 'no_level',
              'distance_sigma': pt[main_dir]['dist_sigma'] if pt else None,
              'horizon': '2~3세션' if (pt and pt[main_dir]['horizon_sessions'] == 3) else '1~2세션',
              'prior': tm.base_p(pt[main_dir]['dist_sigma'], main_dir,
                                 pt[main_dir]['horizon_sessions']) if pt else None,
              'direction_prob': 0.5, 'expected_fret': 0.0,
              'prob_reason': '검정 통과 신호 없음 — 무정보 기본값',
              'conf': 'mid',
              'note': '신규 편입. 초과 %+.2f%%p(β%.2f) · 배지 %s(%.2fσ) · 거래량 %.2f배'
                      % (exc, m['beta'], bdg, sig, m['volx']),
              'model_inputs': mi, 'p_touch': pt, 'p_probe': probe,
              'excess': exc, 'badge': bdg, 'badge_sigma': sig,
              'clsloc': m['clsloc'], 'volx': m['volx'], 'streak': m['streak'],
              'hi': m['hi'], 'lo': m['lo'], 'vol': m['vol']}
        items.append(it)

        # ── 주봉 ─────────────────────────────────────────────────────────────
        w = mw[code]
        wz = load('w_%s.json' % code) or {}
        watr = float(w['watr'])
        wu = pick_level(close, watr, wz.get('zones'), wz.get('lines'), 'up')
        wd = pick_level(close, watr, wz.get('zones'), wz.get('lines'), 'dn')
        wmi = {'wrngatr': w['wrngatr'], 'watrpct': w['watrpct'], 'watr_bars': w['bars'],
               'atr_method': 'wilder14_1W'}
        wpt = {}
        WEEKS = 3          # 기존 회차 규격과 동일한 '2~3주' 지평
        if w['bars'] < tm.MIN_WEEK_BARS:
            wrows.append({'code': code, 'name': NAMES[code], 'atr_insufficient': True})
        else:
            for d, sel in (('up', wu), ('dn', wd)):
                if not sel:
                    continue
                pr = tm.predict_w(sel['dist_sigma'], d, wmi, WEEKS)
                pr['level'] = sel['level']
                pr['src'] = sel['src']
                pr['lap'] = 1
                wpt[d] = pr
                wcalls.append({'opened': OPENED, 'code': code, 'name': NAMES[code],
                               'dir': d, 'level': sel['level'],
                               'dist_sigma': sel['dist_sigma'], 'horizon_weeks': WEEKS,
                               'expiry_after_weeks': WEEKS, 'p': pr['p'],
                               'p_base': pr['p_base'], 'weeks_elapsed': 0,
                               'status': 'open', 'model_inputs': wmi})
            wprobe = {}
            # 프로브는 **1주** 확률이다(2026-09-04 수정). score_probe 는 다음 한 기간의
            # 고저로만 채점하는데 여기서 3주 확률을 넣어 두는 바람에, 주봉 프로브는
            # 회차마다 체계적으로 과대평가됐다(8/28 회차 65~80% 구간 예측 67.1% 대 실제 18.8%).
            # 일봉 프로브는 처음부터 1세션이라 같은 문제가 없었다.
            for tag, k in (('0p5', 0.5), ('1p0', 1.0)):
                pu = tm.predict_w(k, 'up', wmi, 1)
                pdn = tm.predict_w(k, 'dn', wmi, 1)
                wprobe[tag] = {'up': pu['p'], 'dn': pdn['p'], 'up_base': pu['p_base'],
                               'dn_base': pdn['p_base'],
                               'up_level': int(round(close + k * watr)),
                               'dn_level': int(round(close - k * watr))}
            wmain = 'up' if (wu and (not wd or wu['dist_sigma'] <= wd['dist_sigma'])) else 'dn'
            wrows.append({'code': code, 'name': NAMES[code],
                          'market': 'KOSPI' if m['mkt'] == 'P' else 'KOSDAQ',
                          'timeframe': '1W', 'close': int(close), 'atr': int(watr),
                          'wchg': w['wchg'],
                          'resist': wu['level'] if wu else None,
                          'support': wd['level'] if wd else None,
                          'src': (wu or wd or {}).get('src'),
                          'sigma': [wu['dist_sigma'] if wu else None,
                                    wd['dist_sigma'] if wd else None],
                          'call': ('up_test' if wmain == 'up' else 'down_test') if wpt else 'no_level',
                          'distance_sigma': wpt[wmain]['dist_sigma'] if wpt else None,
                          'horizon': '2~3주',
                          'prior': tm.base_p_w(wpt[wmain]['dist_sigma'], wmain, WEEKS) if wpt else None,
                          'direction_prob': 0.5, 'expected_fret': 0.0,
                          'prob_reason': '검정 통과 신호 없음 — 무정보 기본값',
                          'conf': 'low', 'atr_insufficient': None,
                          'note': '신규 편입. 주간 %+.2f%% · 4주 %+.1f%% · 12주 %+.1f%% · 12주위치 %d%% · 연속 %d주'
                                  % (w['wchg'], w['m4'], w['m12'], w['pos12'], w['wstreak']),
                          'model_inputs': wmi, 'p_touch': wpt, 'p_probe': wprobe,
                          'm4': w['m4'], 'm12': w['m12'], 'pos12': w['pos12'],
                          'wstreak': w['wstreak'], 'watrpct': w['watrpct']})

    out = {'items': items, 'open_calls': calls, 'weekly_calls': wcalls, 'weekly_rows': wrows}
    with open(os.path.join(SCR, 'items_new.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('항목 %d · 일봉 레벨콜 %d · 주봉 레벨콜 %d' % (len(items), len(calls), len(wcalls)))
    for it in items:
        print('  %-8s %-7s 종가 %9s · 저항 %10s(%.2fσ) · 지지 %10s(%.2fσ) · %s %.2fσ'
              % (it['code'], it['name'], format(it['close'], ','),
                 format(it['resist'], ',') if it['resist'] else '없음',
                 it['sigma'][0] or 0,
                 format(it['support'], ',') if it['support'] else '없음',
                 it['sigma'][1] or 0, it['badge'], it['badge_sigma']))
    return 0


if __name__ == '__main__':
    sys.exit(main())

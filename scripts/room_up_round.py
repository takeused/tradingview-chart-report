# 회차마다 「위쪽 여유」 표본을 하나씩 늘리고, 찬 칸이 있으면 바로 검정한다
#
# 왜 있나 (2026-09-22): 소급 수집(24회차 × 300종목 · 6시간)은 끝났다. 이제는 회차마다
#   그날 것 하나만 더하면 된다 — 리플레이가 필요 없으므로 20분쯤이다.
#   손으로 세 단계를 기억해서 돌리면 언젠가 빠뜨린다. 한 명령으로 묶는다.
#
# 세 단계
#   1) 그날 광역 수집(300종목) — **리플레이 없이** 실시간 차트로 받는다
#   2) 시가 파일 갱신 — 이게 빠지면 **달력이 어제까지라 최근 회차가 검정에 못 들어간다.**
#      회차를 늘리는 것과 그 회차를 쓸 수 있게 되는 것은 다르다(2026-09-22에 혼동했다).
#   3) 검정 실행 + **칸별 표본 수 점검** — 8 이상인 칸만 판정 가능하다
#
# 사용법
#   python scripts/room_up_round.py --date 2026-09-23
#   python scripts/room_up_round.py --check          # 수집 없이 표본 수만 센다

import argparse, asyncio, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
WIDE = os.path.join(ROOT, 'data', 'room_up_wide')
sys.path.insert(0, HERE)

MIN_N = 8          # stat() 이 요구하는 최소 표본. 이보다 적으면 검정 자체가 불가


def ev(expr):
    import cdp_fetch
    return asyncio.run(cdp_fetch.evaluate(expr))


def replay_off():
    """리플레이가 켜져 있으면 끈다 — 켜진 채로 받으면 과거 봉을 오늘로 적는다."""
    try:
        on = ev("(function(){var r=window.TradingViewApi._replayApi;"
                "var v=r&&r.isReplayStarted&&r.isReplayStarted();"
                "return String((v&&v.value)?v.value():v);})()")
    except Exception as e:
        raise SystemExit('TradingView 에 붙지 못했다 — %s' % e)
    if str(on).lower() == 'true':
        ev("(function(){var r=window.TradingViewApi._replayApi;"
           "try{r.stopReplay();}catch(e){};try{r.hideReplayToolbar();}catch(e){};return 1;})()")
        time.sleep(2)
        print('  리플레이를 껐다')


def last_bar():
    return ev("(function(){var b=window.TradingViewApi.activeChart().getSeries().data().bars();"
              "var t=null; b.each(function(i,v){t=v[0]; return false;});"
              "var z=new Date(t*1000); return z.getUTCFullYear()+'-'+"
              "('0'+(z.getUTCMonth()+1)).slice(-2)+'-'+('0'+z.getUTCDate()).slice(-2);})()")


def run(args, label):
    print('  %s …' % label, flush=True)
    r = subprocess.run([sys.executable, '-u'] + args, cwd=ROOT,
                       env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                       capture_output=True)
    out = r.stdout.decode('utf-8', 'replace')
    if r.returncode != 0:
        print(out[-2000:])
        print(r.stderr.decode('utf-8', 'replace')[-1000:])
        raise SystemExit('%s 실패' % label)
    return out


def cells():
    """창 × 지평 별 표본 수를 센다. 8 이상이어야 판정 가능하다."""
    import study_room_up as sr
    pred = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    bars, order = sr.load_bars(os.path.join(WIDE, 'ohlc300.json'))
    cal = sr.sessions(order)
    rnds = sr.rounds_wide(WIDE, pred)
    cost = sr.round_trip_cost()
    out = []
    for label, rr in (('전체 창', rnds),
                      ('규격 고정 후', [x for x in rnds if x[0] >= sr.SPLIT_FIXED_FROM])):
        for h in sr.HORIZONS:
            per = [len(sr.one_run(rr, bars, cal, h, off, cost)[0]) for off in range(h)]
            out.append({'label': label, 'h': h, 'n': max(per) if per else 0,
                        'per': per, 'ok': (max(per) if per else 0) >= MIN_N})
    return cal, rnds, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date')
    ap.add_argument('--check', action='store_true', help='수집 없이 표본 수만 센다')
    a = ap.parse_args()

    before = {(c['label'], c['h']): c['ok'] for c in cells()[2]} if not a.check else {}

    if not a.check:
        if not a.date:
            raise SystemExit('--date 를 준다 (없으면 어느 회차를 받는지 알 수 없다)')
        print('1) 광역 수집 — %s (리플레이 없이)' % a.date)
        replay_off()
        lb = last_bar()
        if lb != a.date:
            raise SystemExit('차트의 마지막 봉이 %s 다 — %s 회차를 받을 수 없다. '
                             '장 마감 뒤에 돌리거나 날짜를 확인하라' % (lb, a.date))
        p = os.path.join(WIDE, 'round_dates.json')
        dates = json.load(open(p, encoding='utf-8'))
        if a.date not in dates:
            json.dump(sorted(set(dates + [a.date])), open(p, 'w', encoding='utf-8'))
            print('  회차 목록에 추가 (%d개)' % (len(dates) + 1))
        if os.path.exists(os.path.join(WIDE, 'room_%s.json' % a.date)):
            print('  이미 수집됨 — 건너뜀')
        else:
            print(run([os.path.join(HERE, 'collect_wide.py'),
                       '--dates', p, '--universe', os.path.join(WIDE, 'universe300.json'),
                       '--out', WIDE, '--only', a.date,
                       '--progress', os.path.join(WIDE, 'progress.log')],
                      '수집(300종목 · 약 20분)').strip().splitlines()[-1])

        print('2) 시가 갱신 — 이게 빠지면 최근 회차가 검정에 못 들어간다')
        tmp = os.path.join(WIDE, 'ohlc300_new.json')
        run([os.path.join(HERE, 'collect_ohlc.py'),
             '--universe', os.path.join(WIDE, 'universe300.json'), '--out', tmp],
            '시가 수집(약 17분)')
        g = json.load(open(tmp, encoding='utf-8'))
        bad = [c for c, s in g.get('sym', {}).items() if s.split(':')[-1] != c]
        if bad:
            raise SystemExit('심볼 불일치 %s — 갱신하지 않았다' % bad[:5])
        if len(g['data']) < 250:
            raise SystemExit('종목이 %d개뿐이다 — 갱신하지 않았다' % len(g['data']))
        shutil.copy(tmp, os.path.join(WIDE, 'ohlc300.json'))
        print('  시가 갱신 완료 — %d종목' % len(g['data']))

    cal, rnds, cs = cells()
    print()
    print('달력 마지막 %s · 유효 회차 %d (%s ~ %s)'
          % (cal[-1], len(rnds), rnds[0][0], rnds[-1][0]))
    print('%-12s %-4s %-14s %s' % ('창', 'h', '오프셋별 표본', '판정'))
    opened = []
    for c in cs:
        mark = '가능' if c['ok'] else '부족 %d' % (MIN_N - c['n'])
        if c['ok'] and not before.get((c['label'], c['h']), True):
            mark += '  ← 이번 회차에 열렸다'
            opened.append(c)
        print('%-12s %-4d %-14s %s' % (c['label'], c['h'], c['per'], mark))
    print()
    if opened:
        print('=' * 60)
        print('새로 열린 칸이 %d개 — 검정을 돌린다' % len(opened))
        print('=' * 60)
    print(run([os.path.join(HERE, 'study_room_up.py'),
               '--ohlc', os.path.join(WIDE, 'ohlc300.json'), '--wide', WIDE,
               '--json', os.path.join(WIDE, 'result.json')], '검정'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

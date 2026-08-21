# 모의매매 원장 — 전략의 포지션을 비용 차감 원화 손익으로 채점한다
#
# 왜 있나 (2026-08-21 신설): 제1원칙은 "주식 투자로 돈을 버는 것"이다. 그런데 v6 까지의
#   채점 대상은 Brier(확률 보정)였고 **Brier 개선은 0원이다.** 이 원장은 목적함수를
#   원화 손익으로 옮기고, 다음 셋을 항상 함께 기록한다.
#     1) 왕복 비용 (수수료 + 슬리피지 + 매도 거래세)
#     2) 같은 기간 **동일가중 보유 벤치마크** — 이걸 안 빼면 강세장을 실력으로 오인한다
#        (실측: TS 모멘텀 5일 원시 +1.26%(t=6.16) → 벤치 차감 -0.02%(t=-0.09))
#     3) 승률이 아니라 **거래당 기대값**. 승률과 손익은 별개다.
#
# 사용법
#   python scripts/paper_ledger.py open <positions.json> --date YYYY-MM-DD [--panel weekly]
#   python scripts/paper_ledger.py mark [--date YYYY-MM-DD] [--panel weekly]
#   python scripts/paper_ledger.py cancel --reason "사유" [--strategy 이름]
#   python scripts/paper_ledger.py report
#
#   신호 다음 봉이 아직 없으면 pending 으로 남고, 패널 갱신 후 mark 에서 진입가가 채워진다.
#
#   positions.json = {"strategy":"이름", "horizon_days":5, "codes":["005930", ...],
#                     "note":"근거"}
#   진입가는 **다음 거래일 시가**를 쓴다(신호일 종가로 진입하면 룩어헤드다).

import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_io
from backtest import COST, round_trip_cost

LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'paper_trades.json')


def _panel_path(which):
    """주봉 전략은 주봉 패널로 채점해야 한다 — 봉 단위가 섞이면 지평이 뒤틀린다."""
    if not which:
        return panel_io.PANEL
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data',
                        'panel_%s.csv' % which)


def _blank():
    return {
        '_readme': ('모의매매 원장. 전략 포지션을 비용 차감 원화 손익으로 채점하고 '
                    '동일가중 보유 벤치마크를 항상 병기한다. 제1원칙(돈을 버는 것)에 '
                    '직접 연결된 유일한 채점 지표다.'),
        '_cost_model': dict(COST, round_trip_pct=round_trip_cost(),
                            note='실제 요율은 본인 계좌 기준으로 확인할 것'),
        '_execution': '신호 t일 종가 → 진입 t+1일 시가 → 만기 시가 청산',
        '_metrics': '승률이 아니라 거래당 기대값·벤치마크 초과·최대낙폭·비용비중으로 본다',
        'trades': [],
    }


def load():
    if os.path.exists(LEDGER):
        return json.load(open(LEDGER, encoding='utf-8'))
    return _blank()


def save(d):
    json.dump(d, open(LEDGER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def _next_open(P, code, date):
    """date 다음 거래일의 시가와 그 날짜."""
    if date not in P.di:
        later = [d for d in P.dates if d > date]
        if not later:
            return None, None
        t = P.di[later[0]]
    else:
        t = P.di[date] + 1
    if t >= P.T:
        return None, None
    o = P.o.get(code, [None] * P.T)[t]
    return (o, P.dates[t]) if o else (None, None)


def cmd_open(args):
    """포지션을 등록한다.

    신호 다음 봉이 아직 없으면(= 오늘 신호를 냈으면) **pending** 으로 남긴다.
    이게 없으면 원장은 과거 채우기만 되고 전진 추적이 안 된다 — 단계 1의 목적을 못 한다.
    """
    pos = json.load(open(args[0], encoding='utf-8'))
    date = args[args.index('--date') + 1] if '--date' in args else None
    if not date:
        raise SystemExit('--date YYYY-MM-DD (신호일) 가 필요하다')
    panel = args[args.index('--panel') + 1] if '--panel' in args else None
    P = panel_io.load(_panel_path(panel))
    d = load()
    n, pend = 0, 0
    for code in pos['codes']:
        px, edate = _next_open(P, code, date)
        tr = {
            'id': len(d['trades']) + 1, 'strategy': pos['strategy'], 'code': code,
            'signal_date': date, 'entry_date': edate, 'entry_px': px,
            'horizon_days': pos['horizon_days'], 'side': pos.get('side', 'long'),
            'panel': panel or 'daily',
            'status': 'open' if px else 'pending', 'note': pos.get('note', ''),
        }
        d['trades'].append(tr)
        n += 1
        if px is None:
            pend += 1
    save(d)
    print('등록 %d건 (전략 %s · 지평 %d봉) — 진입확정 %d · 대기(pending) %d'
          % (n, pos['strategy'], pos['horizon_days'], n - pend, pend))
    if pend:
        print('  ※ 다음 봉이 아직 없다. 패널을 갱신한 뒤 mark 를 돌리면 진입가가 채워진다.')


def cmd_mark(args):
    date = args[args.index('--date') + 1] if '--date' in args else None
    panel = args[args.index('--panel') + 1] if '--panel' in args else None
    P = panel_io.load(_panel_path(panel))
    d = load()
    cost = round_trip_cost()

    # 1) 대기 건에 진입가가 생겼으면 승격시킨다
    promoted = 0
    for tr in d['trades']:
        if tr['status'] != 'pending':
            continue
        px, edate = _next_open(P, tr['code'], tr['signal_date'])
        if px:
            tr.update(entry_px=px, entry_date=edate, status='open')
            promoted += 1

    # 2) 만기 도래분 청산
    closed = 0
    for tr in d['trades']:
        if tr['status'] != 'open':
            continue
        if tr['entry_date'] not in P.di:
            continue
        t0 = P.di[tr['entry_date']]
        t1 = t0 + tr['horizon_days']
        if t1 >= P.T or (date and P.dates[t1] > date):
            continue
        ex = P.o[tr['code']][t1]
        if ex is None:
            continue
        gross = (ex / tr['entry_px'] - 1) * 100
        if tr['side'] == 'short':
            gross = -gross
        # 같은 구간 동일가중 보유 벤치마크
        bs = []
        for c in P.stocks:
            a, b = P.o[c][t0], P.o[c][t1]
            if a and b:
                bs.append((b / a - 1) * 100)
        bench = sum(bs) / len(bs) if bs else 0.0
        # 저장값끼리 정합적이어야 한다 — excess 를 반올림 전 값에서 따로 구하면
        # 레코드 안에서 excess != net - bench 가 되어 나중에 대조가 깨진다.
        g = round(gross, 4)
        cst = round(cost, 4)
        net = round(g - cst, 4)
        bm = round(bench, 4)
        tr.update(status='closed', exit_date=P.dates[t1], exit_px=ex,
                  gross_pct=g, cost_pct=cst, net_pct=net, bench_pct=bm,
                  excess_net_pct=round(net - bm, 4))
        closed += 1
    save(d)
    op = sum(1 for t in d['trades'] if t['status'] == 'open')
    pd_ = sum(1 for t in d['trades'] if t['status'] == 'pending')
    print('승격 %d건 · 청산 %d건 · 미결 %d건 · 대기 %d건' % (promoted, closed, op, pd_))


def _agg(trs):
    if not trs:
        return None
    net = [t['net_pct'] for t in trs]
    exc = [t['excess_net_pct'] for t in trs]
    n = len(net)
    mn = sum(net) / n
    mx = sum(exc) / n
    # 시간순 누적 곡선의 최대낙폭
    eq, peak, dd = 1.0, 1.0, 0.0
    for t in sorted(trs, key=lambda x: x['exit_date']):
        eq *= (1 + t['net_pct'] / 100)
        peak = max(peak, eq)
        dd = min(dd, eq / peak - 1)
    gross_sum = sum(abs(t['gross_pct']) for t in trs)
    cost_sum = sum(t['cost_pct'] for t in trs)
    return {
        'n': n, 'net_mean': round(mn, 4), 'excess_mean': round(mx, 4),
        'win_pct': round(sum(1 for x in net if x > 0) / n * 100, 1),
        'excess_win_pct': round(sum(1 for x in exc if x > 0) / n * 100, 1),
        'cum_net_pct': round((eq - 1) * 100, 2),
        'max_dd_pct': round(dd * 100, 2),
        'cost_share_pct': round(cost_sum / gross_sum * 100, 1) if gross_sum else None,
    }


def cmd_report(_args):
    d = load()
    trs = [t for t in d['trades'] if t['status'] == 'closed']
    op = [t for t in d['trades'] if t['status'] == 'open']
    pdg = [t for t in d['trades'] if t['status'] == 'pending']
    print('모의매매 원장 — 청산 %d건 · 미결 %d건 · 대기 %d건 · 왕복비용 가정 %.2f%%'
          % (len(trs), len(op), len(pdg), round_trip_cost()))
    print(d['_execution'])
    if not trs:
        print('\n청산된 거래가 없다. open → mark 순서로 쌓은 뒤 다시 본다.')
        return
    print('')
    print('%-22s %5s %10s %11s %8s %10s %9s %9s'
          % ('전략', 'n', '순손익/건%', '벤치초과/건%', '승률%', '누적순%', '최대낙폭%', '비용비중%'))
    print('-' * 92)
    for name in sorted({t['strategy'] for t in trs}) + ['(전체)']:
        sub = trs if name == '(전체)' else [t for t in trs if t['strategy'] == name]
        a = _agg(sub)
        print('%-22s %5d %10.3f %11.3f %8.1f %10.2f %9.2f %9s'
              % (name, a['n'], a['net_mean'], a['excess_mean'], a['win_pct'],
                 a['cum_net_pct'], a['max_dd_pct'],
                 a['cost_share_pct'] if a['cost_share_pct'] is not None else '-'))
    print('-' * 92)
    a = _agg(trs)
    print('판정 — 벤치마크 초과가 거래당 %+.3f%%%s'
          % (a['excess_mean'],
             ' (양수: 계속 관찰)' if a['excess_mean'] > 0 else ' (음수: 이 전략은 돈을 못 번다)'))
    print('※ 승률 %.1f%% 는 참고값이다. 판정 기준은 승률이 아니라 벤치마크 초과 기대값이다.'
          % a['win_pct'])


def cmd_cancel(args):
    """미진입(pending) 건을 사유와 함께 취소한다.

    가설을 기록해 놓고 진입 전에 그 가설이 깨지는 일이 있다. 조용히 지우면 원장이
    '맞은 것만 남는' 기록이 된다. 취소 사유를 남겨 둔다.
    """
    strat = args[args.index('--strategy') + 1] if '--strategy' in args else None
    why = args[args.index('--reason') + 1] if '--reason' in args else ''
    if not why:
        raise SystemExit('--reason "취소 사유" 가 필요하다')
    d = load()
    n = 0
    for tr in d['trades']:
        if tr['status'] != 'pending':
            continue
        if strat and tr['strategy'] != strat:
            continue
        tr.update(status='cancelled', cancel_reason=why)
        n += 1
    save(d)
    print('취소 %d건 — %s' % (n, why))


def main():
    if len(sys.argv) < 2:
        print(__doc__ or '')
        print('usage: paper_ledger.py open|mark|report ...')
        sys.exit(1)
    cmd, args = sys.argv[1], sys.argv[2:]
    {'open': cmd_open, 'mark': cmd_mark, 'report': cmd_report,
     'cancel': cmd_cancel}[cmd](args)


if __name__ == '__main__':
    main()

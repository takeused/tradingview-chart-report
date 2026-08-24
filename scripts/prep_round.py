# 회차 수집물을 build_items.py 입력 형태로 조립한다 — 존은 새로, 라인은 이월 규칙대로
#
# 왜 있나 (2026-08-24, 4회차): 존은 매 회차 다시 받지만 라인은 종목당 500개라 이월한다.
#   이월 규칙이 손으로 하면 어긋나므로(가격 대비 올바른 쪽인지, 1σ 이상 움직였는지)
#   코드로 굳힌다. 1σ 이상 움직인 종목은 --fresh 로 새 라인을 넣어 준다.
#
# 입력 — 스크래치패드의 metrics_daily.json · zones_<일자>.json · betas.json
#        (선택) lines_fresh.json = {"005930": [ ... ], ...}
# 출력 — 스크래치패드의 <code>.json = {"zones": [[hi,lo],...], "lines": [...]}
#        metrics_daily.json 에 beta·bars 를 채워 넣는다.

import argparse, json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--bars', type=int, default=150)
    a = ap.parse_args()

    md = json.load(open(os.path.join(a.dir, 'metrics_daily.json'), encoding='utf-8'))
    zones = json.load(open(os.path.join(a.dir, 'zones_%s.json' % a.date), encoding='utf-8'))
    betas = json.load(open(os.path.join(a.dir, 'betas.json'), encoding='utf-8'))
    fp = os.path.join(a.dir, 'lines_fresh.json')
    fresh = json.load(open(fp, encoding='utf-8')) if os.path.exists(fp) else {}

    pred = json.load(open(os.path.join(ROOT, 'data', 'predictions.json'), encoding='utf-8'))
    prev = {i['code']: i for i in pred['entries'][-1]['items']}

    carried, refreshed, dropped = 0, 0, []
    for code, m in md.items():
        if code in ('KOSPI', 'KOSDAQ'):
            continue
        m['beta'] = betas[code]['beta']
        m['bars'] = a.bars
        close = float(m['close'])

        if code in fresh:
            lines = fresh[code]
            refreshed += 1
        else:
            # 이월 — 직전 회차에 라인에서 뽑은 레벨만 후보로 남긴다.
            # 가격 대비 올바른 쪽이 아니게 됐으면 버린다(저항은 위, 지지는 아래).
            lines = []
            p = prev.get(code, {})
            for d, lv in (('up', p.get('resist')), ('dn', p.get('support'))):
                src = (p.get('p_touch', {}).get(d) or {}).get('src')
                if lv is None or src != 'line':
                    continue
                if (d == 'up' and lv > close) or (d == 'dn' and lv < close):
                    lines.append(lv)
                else:
                    dropped.append('%s %s %s' % (p.get('name', code), d, lv))
            carried += 1

        json.dump({'zones': zones.get(code, []), 'lines': sorted(lines)},
                  open(os.path.join(a.dir, '%s.json' % code), 'w', encoding='utf-8'))

    json.dump(md, open(os.path.join(a.dir, 'metrics_daily.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('라인 신규 %d종목 · 이월 %d종목' % (refreshed, carried))
    if dropped:
        print('이월 폐기(가격이 넘어감) — ' + ', '.join(dropped))
    return 0


if __name__ == '__main__':
    sys.exit(main())

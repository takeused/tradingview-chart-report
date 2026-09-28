# 존·라인 수집물을 종목별 파일로 나누고 **라인 출처를 파일에 박는다**
#
# 왜 있나 (2026-09-10): 2026-09-04 에 수집을 CDP 직결로 바꾸면서 라인을 매 회차 전 종목
#   새로 읽게 됐는데, **나누는 단계가 스크래치패드 스크립트로만 존재**했다. 그래서
#   `make_entry.py` 는 라인이 새것인지를 스크래치패드의 `lines_fresh.json` **파일 존재**로
#   판정했고, 그 파일을 만들지 않은 회차에 36종목이 전부 'carry' 로 찍혔다
#   (2026-09-10 회차에 실제로 발생 — validate_predictions 가 "넥스틴 1.25σ 움직였는데
#   라인을 이월했다"로 잡았다). **없는 파일이 거짓을 만든 것이다.**
#
#   그래서 출처를 **라인을 담고 있는 그 파일에** 함께 적는다(`line_src`). 라인과 출처가
#   같은 파일에 있으면 "수집은 새로 했는데 기록은 이월"이라는 거짓말이 불가능해진다.
#   이월 경로(`prep_round.py`)도 같은 키를 적는다.
#
# 입력 — 스크래치패드의 graphics_daily.json / graphics_weekly.json (수집 원자료)
#        metrics_daily.json (종가 — 스케일 검사용)
# 출력 — <code>.json (일봉) 또는 w_<code>.json (주봉) = {zones, lines, line_src:'fresh'}
#        일봉이면 zones_<일자>.json 도 함께 쓴다
#
# 사용법
#   python scripts/split_graphics.py --dir <스크래치> --kind daily --date 2026-09-10

import argparse, json, os, statistics, sys

BOX = 'Smart Money Concepts [LuxAlgo]'
LINE = 'Swing Structure (HH/HL/LH/LL) + S/R'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--kind', required=True, choices=['daily', 'weekly'])
    ap.add_argument('--date', required=True)
    ap.add_argument('--accept-empty', action='store_true',
                    help='비었거나 빠진 종목이 정말 비어 있음을 직접 확인했을 때만')
    a = ap.parse_args()

    S = a.dir
    g = json.load(open(os.path.join(S, 'graphics_%s.json' % a.kind), encoding='utf-8'))['data']
    md = json.load(open(os.path.join(S, 'metrics_daily.json'), encoding='utf-8'))
    pre = 'w_' if a.kind == 'weekly' else ''

    mismatch, scale, zones_all = [], [], {}
    for code, v in g.items():
        # 심볼 대조가 **진짜 검사**다(2026-09-03 파마리서치 사고). 어긋나면 멈춘다 —
        # 다른 종목의 존·라인으로 확률을 내면 그 회차가 통째로 거짓이 된다.
        if v['sym_actual'].split(':')[-1] != code:
            mismatch.append((code, v['sym_actual']))
            continue

        zones = list(v['boxes'].get(BOX, []))
        lines = sorted(v['lines'].get(LINE, []))
        zones_all[code] = zones

        # 가격 스케일 검사는 **버리는 필터가 아니라 참고용 경고**다. 몇 배 오른 종목은
        # 정상적으로 옛 스윙 라인이 종가의 5%쯤에 있어서 오탐이 흔하다(주봉은 특히).
        vals = [x for z in zones for x in z] + lines
        if vals:
            med = statistics.median(vals) / float(md[code]['close'])
            if not (0.2 <= med <= 5.0):
                scale.append((code, round(med, 4)))

        json.dump({'zones': zones, 'lines': lines, 'line_src': 'fresh'},
                  open(os.path.join(S, '%s%s.json' % (pre, code)), 'w', encoding='utf-8'))

    # 로스터 종목이 수집물에 없거나 박스·라인이 비었으면 멈춘다 (2026-09-28).
    # 빠진 종목은 여기서 파일이 안 써지는데, build_items 는 파일이 없으면 {} 로 읽어
    # "레벨 없음"을 만들고, 같은 스크래치패드에 옛 회차 파일이 남아 있으면 **그걸 읽는다.**
    # 그날 배럴·넥스틴의 박스가 0개로 들어와 레벨이 양쪽 다 사라졌다.
    roster = [c for c, _, _ in json.load(open(os.path.join(S, 'roster.json'),
                                              encoding='utf-8'))['roster']]
    bad = []
    for code in roster:
        v = g.get(code)
        if v is None:
            bad.append((code, '수집물에 없음'))
        elif not v['boxes'].get(BOX) or not v['lines'].get(LINE):
            bad.append((code, '박스 %d · 라인 %d' % (len(v['boxes'].get(BOX, [])),
                                                  len(v['lines'].get(LINE, [])))))
    if bad and not a.accept_empty:
        print('비었거나 빠진 종목 — %s' % bad)
        print('  수집기가 못 읽은 것일 가능성이 크다(없는 것과 구별이 안 된다). '
              '다시 받거나, MCP 로 직접 확인해 정말 비어 있으면 --accept-empty 로 진행')
        return 1
    # 받아들이기로 했으면, 수집물에 없는 종목의 **옛 파일은 지운다** — 남겨 두면 그걸 읽는다.
    for code, why in bad:
        p = os.path.join(S, '%s%s.json' % (pre, code))
        if why == '수집물에 없음' and os.path.exists(p):
            os.remove(p)
            print('옛 파일 삭제 — %s' % os.path.basename(p))

    if a.kind == 'daily':
        json.dump(zones_all, open(os.path.join(S, 'zones_%s.json' % a.date), 'w',
                                  encoding='utf-8'))

    print('%s — 종목 %d · 존 %d · 라인 %d (전 종목 fresh)'
          % (a.kind, len(zones_all), sum(len(z) for z in zones_all.values()),
             sum(len(json.load(open(os.path.join(S, '%s%s.json' % (pre, c)),
                                    encoding='utf-8'))['lines']) for c in zones_all)))
    if scale:
        print('스케일 경고(오탐 흔함 — 심볼 대조가 통과했으면 대개 정상): %s' % scale)
    if mismatch:
        print('심볼 불일치 — 수집이 다른 종목을 읽었다: %s' % mismatch)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

# bars_daily.json 의 종가로 120일 수익률을 뽑아 daily_raw.json(베타 입력)을 만든다
#
# 왜 있나 (2026-09-17): 이 스크립트는 회차마다 스크래치패드에 복사돼 돌던 드라이버였다.
#   9/4 에 수집을 CDP 직결로 바꾸면서 생긴 구멍 그대로다 — `prep_round.py`(이월 경로)는
#   버전 관리 안에 있고 새 경로의 조립 단계만 밖에 있었다. 밖에 있는 코드는 회차마다
#   사람이 기억해서 옮겨야 하고, 기억이 빠지면 조용히 옛 사본이 돈다.
#   `split_graphics.py`(2026-09-10)가 같은 이유로 들어왔다.
#
#   옮기면서 **머리말의 거짓말도 고쳤다.** 옛 주석은 "metrics_daily 에 beta·bars 를 채운다"고
#   적혀 있었는데 실제로는 채우지 않는다(beta 는 `calc_betas.py` 가 낸 뒤 따로 합쳐야 한다).
#   beta 를 여기서 채울 수는 없다 — `calc_betas.py` 가 이 스크립트의 산출물을 입력으로 쓴다.
#
# 입력 — <dir>/bars_daily.json(= {code: [[time, close], ...]}) · <dir>/metrics_daily.json
# 출력 — <dir>/daily_raw.json = {"metrics": {code: {"mkt": …, "rets": [120개]}}}
#
# 사용법
#   python scripts/mkraw.py --dir <스크래치>
#   이어서  python scripts/calc_betas.py <스크래치>  로 betas.json 을 낸다.

import argparse, json, os

N = 121          # 종가 121개 = 수익률 120개. 베타 창과 같아야 한다


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    a = ap.parse_args()

    bars = json.load(open(os.path.join(a.dir, 'bars_daily.json'), encoding='utf-8'))
    md = json.load(open(os.path.join(a.dir, 'metrics_daily.json'), encoding='utf-8'))

    metrics, short = {}, []
    for code, b in bars.items():
        cl = [r[1] for r in b][-N:]
        rets = [(cl[i] - cl[i - 1]) / cl[i - 1] for i in range(1, len(cl))]
        # 창이 짧으면 베타가 조용히 다른 창에서 나온다 — 세어서 보고한다.
        if len(rets) < N - 1:
            short.append((code, len(rets)))
        metrics[code] = {'mkt': md[code]['mkt'], 'rets': rets}

    json.dump({'metrics': metrics},
              open(os.path.join(a.dir, 'daily_raw.json'), 'w', encoding='utf-8'))
    print('daily_raw %d종목 · rets %d' % (len(metrics), N - 1))
    if short:
        print('창 미달(베타가 짧은 창에서 나온다): %s' % short)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

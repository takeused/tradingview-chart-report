# 시총 상위 N 종목 유니버스를 만든다 (TradingView 스크리너)
#
# ⚠️ 유니버스 룩어헤드 — 반드시 읽을 것
#   이 목록은 **오늘 기준** 시총 상위다. 과거 구간 백테스트에 쓰면 "그동안 커진 종목"이
#   처음부터 유니버스에 들어가 있게 된다. 하필 **모멘텀(과거 상승 종목 매수)** 검정에는
#   가짜 수익을 만들어내는 최악의 조합이다.
#   - 초과수익은 **같은 유니버스의 동일가중 벤치마크** 대비로 재므로 수준 편향은 상당 부분
#     상쇄되지만, '오른 종목이 목록에 있다'는 패턴 편향은 남는다.
#   - 그래서 `study_momentum.py` 는 시총 계층(1~100 / 101~200 / 201~300)별로도 쪼개 본다.
#     편향이 원인이라면 **하위 계층(커져서 편입된 쪽)에서 효과가 훨씬 크게** 나온다.
#   - 근본 해결은 시점별(point-in-time) 유니버스이며 KRX 등 다른 소스가 필요하다.
#
# 사용법
#   python scripts/build_universe.py [--top 300] [--out data/universe_top300.csv]

import csv, os, sys

import requests

SCAN = 'https://scanner.tradingview.com/korea/scan'
HDR = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://www.tradingview.com',
       'Referer': 'https://www.tradingview.com/'}


def fetch(n):
    body = {
        'filter': [
            {'left': 'market_cap_basic', 'operation': 'nempty'},
            {'left': 'is_primary', 'operation': 'equal', 'right': True},
            {'left': 'typespecs', 'operation': 'has', 'right': ['common']},
        ],
        'options': {'lang': 'ko'},
        'markets': ['korea'],
        'symbols': {'query': {'types': ['stock']}, 'tickers': []},
        'columns': ['name', 'description', 'market_cap_basic', 'close', 'volume', 'exchange'],
        'sort': {'sortBy': 'market_cap_basic', 'sortOrder': 'desc'},
        'range': [0, n],
    }
    r = requests.post(SCAN, json=body, timeout=30, headers=HDR)
    r.raise_for_status()
    return r.json()


def main():
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 300
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data',
                     'universe_top%d.csv' % top)
    j = fetch(top + 60)          # 여유분 — 아래에서 거른다
    rows = []
    for x in j.get('data', []):
        code, desc, mcap, close, vol, exch = x['d'][:6]
        if not code or len(code) != 6 or not code.isdigit():
            continue
        if exch not in ('KRX',):
            pass                  # 한국 시장은 전부 KRX 로 온다
        mkt = 'KOSDAQ' if (x.get('s', '').startswith('KOSDAQ')) else None
        rows.append({'code': code, 'name': desc or '', 'market_cap': int(mcap or 0),
                     'close': close or 0, 'volume': int(vol or 0),
                     'value_krw': int((close or 0) * (vol or 0)), 'market': mkt or ''})
    rows = rows[:top]
    for i, r in enumerate(rows, 1):
        r['mcap_rank'] = i
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['mcap_rank', 'code', 'name', 'market',
                                          'market_cap', 'close', 'volume', 'value_krw'])
        w.writeheader()
        w.writerows(rows)
    thin = [r for r in rows if r['value_krw'] < 1_000_000_000]
    print('유니버스 %d종목 → %s' % (len(rows), out))
    print('전체 후보 %s개 중 시총 상위 %d' % (j.get('totalCount'), top))
    print('일 거래대금 10억 미만: %d종목 (슬리피지 가정 0.05%%가 낙관적일 수 있다)' % len(thin))
    print('※ 이 목록은 오늘 기준이다. 과거 백테스트에는 유니버스 룩어헤드가 들어간다 — '
          '파일 상단 주석 참조.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

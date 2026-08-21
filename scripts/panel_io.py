# 일봉 패널 CSV 를 읽어 날짜축이 정렬된 배열로 만든다
#
# 패널은 원격이 PUBLIC 이라 추적하지 않는다(.gitignore). 없으면 재수집 절차를 안내한다.

import csv, os

PANEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'panel_daily.csv')

HOWTO = """data/panel_daily.csv 가 없다. 재생성 절차 —
  1) 런처로 TradingView 를 띄운다 (start-tradingview.ps1)
  2) ui_evaluate 로 60종목 + 지수 2개의 일봉을 window.__PF 에 적재한다
     (reference/collect.md 의 1단계 스크립트, 반환 배열은 [time,open,high,low,close,volume])
  3) python scripts/cdp_fetch.py "<CSV 로 직렬화하는 표현식>" data/panel_daily.csv
     — ui_evaluate 로 꺼내면 18,600행이 대화 컨텍스트에 들어간다. 반드시 cdp_fetch 를 쓴다."""


class Panel(object):
    """날짜축이 정렬된 패널. px[code][t] 형태로 접근한다."""

    def __init__(self, rows):
        self.dates = sorted({r['date'] for r in rows})
        self.di = {d: i for i, d in enumerate(self.dates)}
        T = len(self.dates)
        self.codes, self.mkt = [], {}
        by = {}
        for r in rows:
            by.setdefault(r['code'], []).append(r)
            self.mkt[r['code']] = r['mkt']
        self.o, self.h, self.l, self.c, self.v = {}, {}, {}, {}, {}
        for code, rs in by.items():
            self.codes.append(code)
            for name, key in (('o', 'open'), ('h', 'high'), ('l', 'low'),
                              ('c', 'close'), ('v', 'volume')):
                arr = [None] * T
                for r in rs:
                    val = r[key]
                    arr[self.di[r['date']]] = float(val) if val != '' else None
                getattr(self, name)[code] = arr
        self.codes.sort()
        self.stocks = [c for c in self.codes if self.mkt[c] != 'INDEX']
        self.T = T

    def ret_oo(self, code, t, h):
        """익일 시가 진입 → h일 뒤 시가 청산. 종가 신호로 종가에 넣는 룩어헤드를 막는다."""
        o = self.o[code]
        if t + 1 + h >= self.T:
            return None
        a, b = o[t + 1], o[t + 1 + h]
        if a is None or b is None or a <= 0:
            return None
        return (b / a - 1.0) * 100.0


def load(path=PANEL):
    if not os.path.exists(path):
        raise SystemExit(HOWTO)
    with open(path, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    return Panel(rows)

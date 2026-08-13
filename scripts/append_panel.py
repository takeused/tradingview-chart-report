# 매 회차 종목일 관측을 data/panel.csv 에 누적해 지표 예측력 검정용 표본을 쌓는 스크립트
"""
사용법:
    python scripts/append_panel.py <calc모듈경로> <기준일 YYYY-MM-DD>

calc 모듈은 STK(dict)과 IDX(dict)를 노출해야 한다.
  STK[code] = dict(name, mkt, bars=[[고,저,종,거래량], ...])
  IDX = {"KOSPI": 등락%, "KOSDAQ": 등락%}

동작:
  1) 각 종목의 '오늘'(bars[-1]) 관측을 feature와 함께 append
  2) 직전 회차 행들의 fret/fup(다음날 결과)을 이번 종가로 채운다
중복 방지: (date, code) 키가 이미 있으면 건너뛴다.
"""
import csv, os, sys, importlib.util

COLS = ["date","code","name","mkt","close","atr","atrpct","vol_ratio","ret1","ret3",
        "clsloc","rngr","streak","excess","badge_sigma","fret","fup"]

def load(path):
    spec = importlib.util.spec_from_file_location("calcmod", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["calcmod"] = m
    spec.loader.exec_module(m)
    return m

def atr14(bars):
    trs = []
    for i in range(1, len(bars)):
        h, l, c = bars[i][0], bars[i][1], bars[i][2]
        pc = bars[i-1][2]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    last = trs[-14:]
    return sum(last)/len(last) if last else 0

def build_rows(STK, IDX, date):
    rows = []
    for code, d in STK.items():
        b = d["bars"]
        if len(b) < 21: continue   # vol20(21봉)·ret3(4봉)·atr14(15봉) 최소 요건
        H, L, C, V = b[-1]
        pc = b[-2][2]
        a = atr14(b)
        if a <= 0: continue
        v20 = sum(x[3] for x in b[-21:-1]) / 20
        chg = (C-pc)/pc*100
        excess = chg - IDX[d["mkt"]]
        streak = 0
        for k in range(len(b)-1, 0, -1):
            up = b[k][2] > b[k-1][2]
            if streak == 0: streak = 1 if up else -1
            elif (streak > 0) == up: streak += 1 if up else -1
            else: break
        rows.append({
            "date": date, "code": code, "name": d["name"], "mkt": d["mkt"],
            "close": C, "atr": round(a), "atrpct": round(a/C*100, 2),
            "vol_ratio": round(V/v20, 3) if v20 else "",
            "ret1": round((C-pc)/a, 3),
            "ret3": round((C-b[-4][2])/a, 3),
            "clsloc": round((C-L)/(H-L), 3) if H > L else 0.5,
            "rngr": round((H-L)/a, 3),
            "streak": streak,
            "excess": round(excess, 2),
            "badge_sigma": round(excess/(a/C*100), 2),
            "fret": "", "fup": "",
        })
    return rows

def main(calc_path, date):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "data", "panel.csv")
    m = load(calc_path)
    new = build_rows(m.STK, m.IDX, date)

    old = []
    if os.path.exists(out):
        with open(out, encoding="utf-8", newline="") as f:
            old = list(csv.DictReader(f))

    have = {(r["date"], r["code"]) for r in old}
    added = [r for r in new if (r["date"], r["code"]) not in have]

    # 직전 회차 행의 결과(fret/fup)를 오늘 종가로 채운다
    today_close = {r["code"]: r["close"] for r in new}
    prev_dates = sorted({r["date"] for r in old})
    filled = 0
    if prev_dates:
        last = prev_dates[-1]
        for r in old:
            if r["date"] == last and r["fret"] == "" and r["code"] in today_close:
                c0 = float(r["close"]); a0 = float(r["atr"]); c1 = today_close[r["code"]]
                r["fret"] = round((c1-c0)/a0, 3)
                r["fup"] = 1 if c1 > c0 else 0
                filled += 1

    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(old + added)

    total = len(old) + len(added)
    scored = sum(1 for r in old + added if r["fret"] not in ("", None))
    print(f"{date}: {len(added)}행 추가 · 직전 회차 {filled}행 결과 채움")
    print(f"누적 {total}행 (결과 확정 {scored}행) → {out}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2])

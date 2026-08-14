# v6.1 도달확률 모델 — 확률표·조건부 보정의 단일 진실 원천(SSOT)
#
# 왜 모듈로 뽑았나: v6 최초 구현에서 확률표는 '단순평균 ATR'로 만들고 리포트·예측은
#   'Wilder ATR'을 쓰는 불일치가 있었다(관측당 평균 8.9% 차이). 정의가 여러 곳에
#   흩어져 있으면 반드시 어긋난다. 적용기와 채점기가 이 모듈만 쓰도록 강제한다.
#
# 규격 (2026-08-14 v6.1)
#   - ATR: Wilder(14). 실행방법.md 규격과 일치.
#   - 표본: 60종목 x 300봉 = 16,320 관측 (2025-05~2026-08)
#   - 지평: 1 / 2 / 3 세션 각각 별도 표. horizon과 반드시 같은 표를 쓴다.
#   - 조건부 계수는 2-폴드 평균값. 개별 폴드 계수는 거래량·레인지가 상관돼 불안정해서,
#     평균 계수가 양쪽 폴드에서 단일 폴드 계수보다 좋았다(+1.17% / +0.98%).

import math

# 거리 그리드. 0.0은 정의상 100%(이미 그 자리)라 보간 앵커로 쓴다.
GRID = [0.0, 0.05, 0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 1.00, 1.25, 1.50]

# 지평별 기저 도달확률(%) — Wilder ATR 기준
TABLE = {
    1: {'up': [100.0, 82.9, 79.1, 64.9, 51.1, 43.0, 35.6, 26.9, 16.8, 10.7, 7.3],
        'dn': [100.0, 78.6, 74.8, 61.4, 47.5, 39.1, 31.5, 22.1, 11.9, 6.6, 3.6]},
    2: {'up': [100.0, 88.2, 85.5, 75.2, 63.9, 57.2, 50.5, 42.0, 30.3, 21.8, 16.0],
        'dn': [100.0, 83.9, 81.0, 71.3, 60.2, 53.0, 45.7, 36.2, 24.3, 15.5, 9.7]},
    3: {'up': [100.0, 90.8, 88.6, 80.2, 70.9, 65.0, 59.1, 50.9, 39.5, 29.8, 23.2],
        'dn': [100.0, 86.8, 84.4, 76.1, 67.1, 60.9, 54.3, 45.3, 32.9, 23.2, 15.7]},
}

# 조건부 보정 계수 (2-폴드 평균). 1세션 적합이며 2~3세션에도 같은 계수를 쓰되,
# 지평이 길수록 조건부의 설명력이 줄어드는 것으로 보여 감쇠를 건다.
COEF = {'vol': 0.169, 'rng': 0.379, 'atrpct': -0.173}
HORIZON_DAMP = {1: 1.0, 2: 0.7, 3: 0.5}

CLIP = {'vol': (-1.5, 1.5), 'rng': (-1.5, 2.5)}

META = {
    'version': 'v6.1',
    'atr': 'Wilder(14)',
    'n_obs': 16320,
    'sample': '60종목 x 300봉 (2025-05~2026-08)',
    'holdout_gain_pct': 1.0,
    'note': ('2-폴드 교차검증에서 평균 계수가 양쪽 폴드 모두에서 단일 폴드 계수보다 우수했다'
             '(+1.17% / +0.98%). 개선폭은 약 1.0%로 작다 — 기저 표가 대부분의 일을 한다.'),
}


def horizon_sessions(label):
    """horizon 문자열을 세션 수로 정규화한다. 라벨과 표가 어긋나면 채점이 통째로 틀어진다."""
    if label is None:
        return 1
    s = str(label)
    if '2~3' in s or '3세션' in s:
        return 3
    if '1~2' in s or '2세션' in s:
        return 2
    return 1


def base_p(dist_sigma, direction, sessions=1):
    """거리 단독 기저 확률(%). 이것이 조건부가 이겨야 할 기준선이다."""
    if dist_sigma is None:
        return None
    tab = TABLE[sessions]['up' if direction == 'up' else 'dn']
    d = max(0.0, float(dist_sigma))
    if d >= GRID[-1]:
        return tab[-1]
    for i in range(len(GRID) - 1):
        if GRID[i] <= d <= GRID[i + 1]:
            w = (d - GRID[i]) / (GRID[i + 1] - GRID[i])
            return round(tab[i] + (tab[i + 1] - tab[i]) * w, 1)
    return tab[-1]


def _clip(v, lohi):
    return max(lohi[0], min(lohi[1], v))


def cond_p(dist_sigma, direction, vol_ratio, rng_over_atr, atr_pct, sessions=1):
    """변동성 상태를 반영한 조건부 확률(%). 입력이 없으면 기저값으로 안전하게 되돌아간다."""
    p0 = base_p(dist_sigma, direction, sessions)
    if p0 is None:
        return None
    p = min(99.8, max(0.2, p0)) / 100.0
    lg = math.log(p / (1 - p))
    damp = HORIZON_DAMP.get(sessions, 1.0)
    if vol_ratio and vol_ratio > 0:
        lg += damp * COEF['vol'] * _clip(math.log(vol_ratio), CLIP['vol'])
    if rng_over_atr is not None:
        lg += damp * COEF['rng'] * _clip(rng_over_atr - 1, CLIP['rng'])
    if atr_pct and atr_pct > 0:
        lg += damp * COEF['atrpct'] * math.log(atr_pct / 5.0)
    return round(100 / (1 + math.exp(-lg)), 1)


def predict(dist_sigma, direction, metrics, sessions=1):
    """조건부와 기준선을 함께 돌려준다. 항상 쌍으로 기록해야 실력 판정이 가능하다."""
    if dist_sigma is None:
        return None
    return {
        'p': cond_p(dist_sigma, direction, metrics.get('volx'),
                    metrics.get('rngatr'), metrics.get('atrpct'), sessions),
        'p_base': base_p(dist_sigma, direction, sessions),
        'dist_sigma': round(float(dist_sigma), 3),
        'dir': direction,
        'horizon_sessions': sessions,
    }


def beta_adj(beta_120d):
    """베타는 120일 추정이라 잡음이 크다. 1로 30% 축소해서 쓴다."""
    if beta_120d is None:
        return 1.0
    return round(1 + 0.7 * (beta_120d - 1), 3)


def excess_return(chg_pct, index_chg_pct, beta_120d=None):
    return round(chg_pct - beta_adj(beta_120d) * index_chg_pct, 3)


def badge(excess_pct, atr_pct):
    """방향 배지 — 절대 등락이 아니라 위험조정 초과수익으로 판정한다."""
    if not atr_pct:
        return '중립', 0.0
    sig = round(excess_pct / atr_pct, 2)
    return ('강세' if sig >= 0.5 else '약세' if sig <= -0.5 else '중립'), sig

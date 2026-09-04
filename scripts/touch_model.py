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
GRID = [0.0, 0.05, 0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 1.00, 1.25, 1.50,
        1.75, 2.00, 2.25, 2.50, 3.00]   # 2026-09-05 확장 — 상한 3.0σ 까지 실측으로 채웠다

# 지평별 기저 도달확률(%) — Wilder ATR 기준
TABLE = {
    1: {'up': [100.0, 82.9, 79.1, 64.9, 51.1, 43.0, 35.6, 26.9, 16.8, 10.7, 7.3,
               4.6, 3.1, 2.2, 1.8, 1.0],
        'dn': [100.0, 78.6, 74.8, 61.4, 47.5, 39.1, 31.5, 22.1, 11.9, 6.6, 3.6,
               2.3, 1.5, 1.1, 0.7, 0.3]},
    2: {'up': [100.0, 88.2, 85.5, 75.2, 63.9, 57.2, 50.5, 42.0, 30.3, 21.8, 16.0,
               11.4, 8.2, 6.1, 4.7, 3.0],
        'dn': [100.0, 83.9, 81.0, 71.3, 60.2, 53.0, 45.7, 36.2, 24.3, 15.5, 9.7,
               6.9, 4.4, 3.1, 2.2, 1.2]},
    3: {'up': [100.0, 90.8, 88.6, 80.2, 70.9, 65.0, 59.1, 50.9, 39.5, 29.8, 23.2,
               17.5, 13.3, 10.3, 8.1, 5.3],
        'dn': [100.0, 86.8, 84.4, 76.1, 67.1, 60.9, 54.3, 45.3, 32.9, 23.2, 15.7,
               11.2, 7.7, 5.5, 3.9, 2.1]},
}

# 조건부 보정 계수 (2-폴드 평균). 1세션 적합이며 2~3세션에도 같은 계수를 쓰되,
# 지평이 길수록 조건부의 설명력이 줄어드는 것으로 보여 감쇠를 건다.
COEF = {'vol': 0.169, 'rng': 0.379, 'atrpct': -0.173}
HORIZON_DAMP = {1: 1.0, 2: 0.7, 3: 0.5}

CLIP = {'vol': (-1.5, 1.5), 'rng': (-1.5, 2.5)}

META = {
    'version': 'v6.2',
    'grid_max_sigma': 3.0,
    'grid_extended': ('2026-09-05 — 격자가 1.5σ 에서 끝나 그 밖을 전부 1.5σ 값으로 돌려주고 '
                      '있었다. 레벨 상한이 3.0σ 이므로 종결 원장 521건 중 150건(1.5σ 초과)이 '
                      '예측 평균 17.2% 대 실제 4.0% 로 과대평가됐다. 같은 패널로 재서 '
                      '1.75/2.00/2.25/2.50/3.00 을 붙였다. 1.5σ 이하 값은 바꾸지 않았다 — '
                      '재현 오차 ±0.9%p 안에서 기존 격자를 그대로 재현했다.'),
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
    """거리 단독 기저 확률(%). 이것이 조건부가 이겨야 할 기준선이다.

    격자 밖(3.0σ 초과)은 마지막 값을 그대로 돌려준다. 레벨 상한이 3.0σ 이므로
    정상 경로에서는 나오지 않지만, 나온다면 그 확률은 **상한값이라 과대**다.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# 주봉 모델 (v6.1-W, 2026-08-21 보정)
#
# 왜 별도 표인가: 일봉 표를 주봉에 그대로 쓰면 틀린다. 같은 σ 거리에서 주봉 도달률이
#   **위쪽만 체계적으로 높다** — 0.5σ 1기간에서 위 44.9%(일봉 43.0) · 아래 38.9%(일봉 39.1),
#   0.05σ 에서는 위 89.8%(82.9) · 아래 87.0%(78.6) 로 벌어진다. 아래쪽은 거의 일치한다.
#   자(ATR)를 바꿔 놓고 표를 그대로 쓰는 것이 v6 를 깨뜨린 바로 그 실수라 표를 새로 만들었다.
#
# 표본: 60종목 유니버스 중 주봉 140개 이상인 57종목, 관측 9,905건 (ATR 창 120주 이상).
#   에이피알·달바글로벌·웨이비스는 상장 이력이 짧아 보정에서 제외했다.
#   관측은 겹치는 창을 쓰므로 서로 독립이 아니다 — 표준오차는 명목치보다 크다.
#
# 조건부: **거래량 배수는 주봉에서 무효다.** 폴드·지평마다 부호까지 뒤집혔다
#   (1주 +0.074/+0.005, 2주 −0.006/−0.063, 3주 −0.029/−0.076). 일봉의 연속일수·국면과
#   같은 취급으로 조건에서 뺐다. 남은 둘(레인지, ATR%)은 폴드 간 부호·크기가 안정적이다.
#   계수는 2-폴드 평균이며, 양쪽 폴드 모두에서 단일 폴드 계수보다 좋았다(일봉과 같은 패턴).
#   정직한 홀드아웃 개선폭 — 1주 1.53~1.82% · 2주 0.93~1.33% · 3주 0.73~1.02%.

TABLE_W = {
    1: {'up': [100.0, 89.8, 85.1, 68.8, 53.5, 44.9, 37.6, 28.8, 18.8, 12.6, 8.3,
               5.6, 4.1, 3.0, 2.3, 1.3],
        'dn': [100.0, 87.0, 82.2, 64.1, 48.3, 38.9, 31.0, 22.0, 12.0, 6.6, 3.5,
               2.0, 1.1, 0.7, 0.4, 0.2]},
    2: {'up': [100.0, 93.3, 90.0, 78.6, 67.2, 60.2, 53.7, 44.8, 33.4, 25.1, 18.6,
               14.0, 10.7, 8.2, 6.5, 4.3],
        'dn': [100.0, 90.7, 87.2, 73.8, 61.9, 54.0, 46.6, 37.7, 24.5, 15.2, 9.7,
               6.0, 3.6, 2.2, 1.3, 0.6]},
    3: {'up': [100.0, 94.8, 92.1, 83.0, 73.6, 67.6, 62.0, 53.9, 43.1, 34.2, 27.1,
               21.7, 17.6, 14.2, 11.7, 7.9],
        'dn': [100.0, 92.7, 89.7, 78.7, 68.6, 61.6, 54.9, 46.6, 33.6, 23.3, 15.8,
               10.5, 6.7, 4.0, 2.7, 1.1]},
}

# 지평별로 따로 적합했다. 일봉처럼 감쇠를 곱하지 않는다 — 감쇠는 1기간 계수를 재활용할 때의
# 근사이고, 주봉은 세 지평을 각각 적합할 표본이 있었다.
COEF_W = {
    1: {'rng': 0.5106, 'atrpct': -0.1966},
    2: {'rng': 0.4122, 'atrpct': -0.1627},
    3: {'rng': 0.3690, 'atrpct': -0.1385},
}

REF_ATRPCT_W = 7.87      # 패널 주봉 ATR% 중앙값. 일봉의 5% 에 대응하는 정규화 기준점
MIN_WEEK_BARS = 120      # 이보다 짧으면 Wilder 시드가 남아 표와 어긋난다(일봉 120봉 규칙과 같은 근거)

META_W = {
    'version': 'v6.2-W',
    'grid_max_sigma': 3.0,
    'grid_extended': ('2026-09-05 — 일봉과 같은 이유로 1.75~3.00σ 를 붙였다. '
                      'panel_weekly 로 기존 격자를 ±0.2%p 안에서 재현한 뒤 확장했다.'),
    'atr': 'Wilder(14) on 1W',
    'n_obs': 9905,
    'n_symbols': 57,
    'sample': '60종목 유니버스 중 주봉 140개 이상 57종목 (2026-08-21 보정)',
    'holdout_gain_pct': '1주 1.53~1.82 / 2주 0.93~1.33 / 3주 0.73~1.02',
    'dropped': '거래량 배수 — 폴드·지평 간 부호 반전으로 무효 판정',
    'note': ('관측이 겹치는 창이라 독립이 아니다. 일봉 표와 달리 위쪽이 체계적으로 높다.'
             '분기마다 재보정하고 관측수·기간을 병기한다.'),
}


def horizon_weeks(label):
    """주봉 horizon 라벨을 주 수로 정규화한다. 라벨과 표가 어긋나면 채점이 통째로 틀어진다."""
    if label is None:
        return 1
    s = str(label)
    if '2~3' in s or '3주' in s:
        return 3
    if '1~2' in s or '2주' in s:
        return 2
    return 1


def base_p_w(dist_sigma, direction, weeks=1):
    """주봉 거리 단독 기저 확률(%). 주봉 ATR 로 잰 거리여야 한다."""
    if dist_sigma is None:
        return None
    tab = TABLE_W[weeks]['up' if direction == 'up' else 'dn']
    d = max(0.0, float(dist_sigma))
    if d >= GRID[-1]:
        return tab[-1]
    for i in range(len(GRID) - 1):
        if GRID[i] <= d <= GRID[i + 1]:
            w = (d - GRID[i]) / (GRID[i + 1] - GRID[i])
            return round(tab[i] + (tab[i + 1] - tab[i]) * w, 1)
    return tab[-1]


def cond_p_w(dist_sigma, direction, rng_over_atr, atr_pct, weeks=1):
    """주봉 조건부 확률(%). 거래량은 주봉에서 무효라 입력으로 받지 않는다."""
    p0 = base_p_w(dist_sigma, direction, weeks)
    if p0 is None:
        return None
    p = min(99.8, max(0.2, p0)) / 100.0
    lg = math.log(p / (1 - p))
    c = COEF_W[weeks]
    if rng_over_atr is not None:
        lg += c['rng'] * _clip(rng_over_atr - 1, CLIP['rng'])
    if atr_pct and atr_pct > 0:
        lg += c['atrpct'] * math.log(atr_pct / REF_ATRPCT_W)
    return round(100 / (1 + math.exp(-lg)), 1)


def predict_w(dist_sigma, direction, metrics, weeks=1):
    """주봉 조건부와 기준선을 쌍으로 돌려준다. metrics 는 wrngatr · watrpct 를 쓴다."""
    if dist_sigma is None:
        return None
    return {
        'p': cond_p_w(dist_sigma, direction, metrics.get('wrngatr'),
                      metrics.get('watrpct'), weeks),
        'p_base': base_p_w(dist_sigma, direction, weeks),
        'dist_sigma': round(float(dist_sigma), 3),
        'dir': direction,
        'horizon_weeks': weeks,
    }

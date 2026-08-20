# 문서와 코드가 어긋나지 않았는지 검사한다 — 커밋 전 validate_predictions.py 와 함께 돌린다
#
# 왜 있나: 3라운드 확인에서 실제로 드리프트가 났다. SKILL.md는 "규격 충돌 시 실행방법.md가
#   우선"이라고 선언하는데 정작 실행방법.md는 ATR을 60봉이라 하고 스킬은 120봉이라 했다.
#   선언된 우선순위를 따르면 틀린 값을 쓰게 된다. 상수는 코드(touch_model.py)가 진실이고
#   문서는 그 설명일 뿐인데, 설명이 낡으면 다음 세션이 낡은 값을 쓴다.

import io, json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_model as tm

SKILL = os.path.join(ROOT, '.claude', 'skills', 'tradingview-report', 'SKILL.md')
CONST = os.path.join(ROOT, '.claude', 'skills', 'tradingview-report', 'reference', 'v6-constants.md')
COLLECT = os.path.join(ROOT, '.claude', 'skills', 'tradingview-report', 'reference', 'collect.md')
METHOD = os.path.join(ROOT, '실행방법.md')
PRED = os.path.join(ROOT, 'data', 'predictions.json')


def read(p):
    return io.open(p, encoding='utf-8').read() if os.path.exists(p) else ''


def main():
    skill, const, collect, method = read(SKILL), read(CONST), read(COLLECT), read(METHOD)
    pred = json.load(open(PRED, encoding='utf-8'))
    fail = []

    def need(cond, msg):
        if not cond:
            fail.append(msg)

    # 1) 계수 — 코드가 진실, 문서에 같은 값이 적혀 있어야 한다
    for k, v in tm.COEF.items():
        need(str(abs(v)) in const, '계수 %s=%s 가 v6-constants.md 에 없다' % (k, v))

    # 2) 확률표 대표값
    for h, d, expect in ((1, 'up', 43.0), (2, 'up', 57.2), (3, 'up', 65.0),
                         (1, 'dn', 39.1), (3, 'dn', 60.9)):
        got = tm.base_p(0.5, d, h)
        need(abs(got - expect) < 0.05, '모듈 표 변경됨: %d세션 %s 0.5σ = %s (문서 기준 %s)' % (h, d, got, expect))
        need(str(expect) in const, '%d세션 %s 0.5σ 값 %s 가 v6-constants.md 에 없다' % (h, d, expect))

    # 3) 지평 감쇠
    need(tm.HORIZON_DAMP == {1: 1.0, 2: 0.7, 3: 0.5}, '감쇠 계수가 바뀌었는데 문서 확인 필요')

    # 4) 규격이 SSOT(실행방법.md)와 스킬 양쪽에 있어야 한다 — 한쪽만 고치면 우선순위 규칙상 사고가 난다
    for kw, label in (('120봉', 'ATR 120봉 규격'),
                      ('model_inputs', '모델 입력 기록 규칙'),
                      ('가장 좁은', '존 동점 규칙'),
                      ('1σ 이상 움직였으면', '라인 이월 유효성 규칙'),
                      # 2026-08-20 감사 산물 — 한쪽만 적혀 있으면 다음 세션이 규칙을 모른다
                      ('line_provenance', '라인 출처 기록 규칙'),
                      ('일괄이동 귀무모형', '일괄이동 귀무모형 판정 규칙'),
                      ('check_report.py', '리포트-데이터 대조 단계')):
        need(kw in skill, '%s 가 SKILL.md 에 없다' % label)
        need(kw in method, '%s 가 실행방법.md 에 없다' % label)

    # 4-b) 코드가 실제로 그 규칙을 구현하고 있는가 — 문서만 고치고 코드를 안 고치는 반대 드리프트
    val = read(os.path.join(ROOT, 'scripts', 'validate_predictions.py'))
    sc = read(os.path.join(ROOT, 'scripts', 'score_touch.py'))
    need('line_provenance' in val, 'validate_predictions.py 에 라인 이월 검사가 없다')
    need('MIN_ATR_BARS' in val, 'validate_predictions.py 에 ATR 창 검사가 없다')
    need('MIN_LINE_SIGMA' in val, 'validate_predictions.py 에 라인 0.5σ 하한 검사가 없다')
    need('shift_null' in sc, 'score_touch.py 에 일괄이동 귀무모형이 없다')
    need(os.path.exists(os.path.join(ROOT, 'scripts', 'check_report.py')),
         'scripts/check_report.py 가 없다')

    # 5) 구 규격에 폐기 표시가 붙어 있어야 한다
    need('⛔' in method and '최소 120봉' in method, '실행방법.md 의 구 ATR(60봉) 규격에 폐기 표시가 없다')
    need(pred['_metrics_v2']['atr'].startswith('[2026-08-14 개정'),
         'predictions.json _metrics_v2.atr 에 폐기 표시가 없다')

    # 6) 수집 스크립트가 120봉을 받는가
    need('slice(-120)' in collect, 'collect.md 가 120봉을 받지 않는다')

    # 7) 스킬이 코드를 SSOT로 지시하는가
    need('touch_model.py' in skill, 'SKILL.md 가 touch_model.py 를 SSOT로 지시하지 않는다')
    need('validate_predictions.py' in skill, 'SKILL.md 에 검증 단계가 없다')

    # 8) 버전 표기
    need('phase: v6.1' in skill, 'SKILL.md frontmatter phase 가 v6.1 이 아니다')
    need('model_v6_1' in pred['_scoring'], 'predictions.json 에 model_v6_1 규격이 없다')

    print('문서-코드 동기화 검사 — 실패 %d건 (모델 %s)' % (len(fail), tm.META['version']))
    for f in fail:
        print('  [불일치] ' + f)
    if not fail:
        print('통과')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()

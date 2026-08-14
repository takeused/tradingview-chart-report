# predictions.json 직렬화 — items를 한 줄씩 유지해 diff 가독성을 지킨다
#
# json.dump(indent=1)을 그냥 쓰면 items 원소가 전부 여러 줄로 펼쳐져 diff가 4배로 부푼다
# (실측: 1,303줄이면 될 변경이 4,231줄이 됐다).

import json
import shutil


def dump_predictions(d, path, backup=False):
    if backup:
        shutil.copyfile(path, path + '.bak')
    ph = {}
    for idx, e in enumerate(d.get('entries', [])):
        key = '@@ITEMS_%d@@' % idx
        ph[key] = e['items']
        e['items'] = key
    try:
        s = json.dumps(d, ensure_ascii=False, indent=1)
        for key, items in ph.items():
            lines = [' ' * 8 + json.dumps(it, ensure_ascii=False) for it in items]
            s = s.replace('"%s"' % key, '[\n' + ',\n'.join(lines) + '\n' + ' ' * 6 + ']', 1)
    finally:
        # 예외가 나도 원본 구조를 되돌려 놓는다
        for idx, e in enumerate(d.get('entries', [])):
            k = '@@ITEMS_%d@@' % idx
            if isinstance(e.get('items'), str) and e['items'] == k:
                e['items'] = ph[k]
    open(path, 'w', encoding='utf-8', newline='').write(s + '\n')


def load_predictions(path):
    return json.load(open(path, encoding='utf-8'))

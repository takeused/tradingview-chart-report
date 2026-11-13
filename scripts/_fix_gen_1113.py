# _gen_patch_1113.py 의 문장 ② 치환을 "11/13 세션" 전역 치환보다 앞으로 옮기는 일회성 보정
import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_gen_patch_1113.py')
s = open(p, encoding='utf-8').read()
a = s.index('rep("아직 만기가 안 된')
b = s.index('# 4) 각주')
blk = s[a:b]
s = s[:a] + s[b:]
k = s.index('src = src.replace("11/13 세션"')
s = s[:k] + blk + s[k:]
open(p, 'w', encoding='utf-8').write(s)
print('fixed')

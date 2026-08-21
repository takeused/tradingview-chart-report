# TradingView 페이지에서 대용량 결과를 CDP로 직접 받아 파일에 쓴다
#
# 왜 있나: ui_evaluate 로 18,600행(60종목 x 300봉)을 받으면 결과가 통째로 대화 컨텍스트에
#   들어가 ~25만 토큰을 먹는다. CDP WebSocket 으로 직접 받으면 컨텍스트 비용이 0이다.
#   수집 자체는 지금까지처럼 ui_evaluate 로 window.__PF 에 적재해 두고,
#   '꺼내는 단계'만 이 스크립트로 한다.
#
# 사용법
#   python scripts/cdp_fetch.py "<자바스크립트 표현식>" <출력파일>
#   표현식은 문자열을 반환해야 한다(JSON 또는 CSV).

import asyncio, json, sys

import requests
import websockets


def target_ws(port=9222):
    """차트 페이지 타깃의 WebSocket 주소를 찾는다."""
    r = requests.get('http://localhost:%d/json/list' % port, timeout=5).json()
    pages = [t for t in r if t.get('type') == 'page' and 'tradingview.com' in t.get('url', '')]
    if not pages:
        raise SystemExit('TradingView 차트 페이지를 못 찾았다. 런처로 띄웠는지 확인할 것.')
    return pages[0]['webSocketDebuggerUrl']


async def evaluate(expr, port=9222):
    url = target_ws(port)
    # 18,600행 CSV 가 한 프레임으로 오므로 상한을 넉넉히 잡는다
    async with websockets.connect(url, max_size=256 * 1024 * 1024) as ws:
        await ws.send(json.dumps({
            'id': 1, 'method': 'Runtime.evaluate',
            'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': True},
        }))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get('id') == 1:
                res = msg.get('result', {})
                if 'exceptionDetails' in res:
                    raise SystemExit('페이지 예외: %s' % json.dumps(res['exceptionDetails'])[:500])
                return res.get('result', {}).get('value')


def main():
    if len(sys.argv) < 3:
        print('usage: cdp_fetch.py "<expr>" <out_file>')
        sys.exit(1)
    expr, out = sys.argv[1], sys.argv[2]
    val = asyncio.run(evaluate(expr))
    if val is None:
        raise SystemExit('표현식이 값을 돌려주지 않았다(문자열을 반환해야 한다).')
    if not isinstance(val, str):
        val = json.dumps(val, ensure_ascii=False)
    with open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(val)
    print('%s — %d bytes, %d lines' % (out, len(val), val.count('\n') + 1))


if __name__ == '__main__':
    main()

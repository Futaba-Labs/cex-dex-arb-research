import json
import asyncio
import requests
import websockets
import aioprocessing

from typing import List
from decimal import Decimal


# Binance USDM-Futures orderbook stream
async def stream_binance_usdm_orderbook(symbols: List[str],
                                        event_queue: aioprocessing.AioQueue,
                                        debug: bool = False):
    try:
        if debug:
            print(f"Connecting to Binance...")
            print(f"Symbols: {symbols}")
        
        # WebSocket接続を試行
        ws_urls = [
            'wss://fstream.binance.com/ws/',
            'wss://fstream.binance.com/stream/',
            'wss://stream.binance.com:9443/ws/'
        ]
        
        for ws_url in ws_urls:
            try:
                if debug:
                    print(f"Trying WebSocket URL: {ws_url}")
                
                async with websockets.connect(ws_url, 
                                           ping_interval=20,
                                           ping_timeout=20) as ws:
                    
                    # シンボル名の正規化 - ETH/USDT -> ETHUSDT
                    params = []
                    for s in symbols:
                        # ETH/USDT -> ETHUSDT (大文字に変換)
                        symbol = s.replace("/", "").upper()
                        # 正しいストリーム名形式: ethusdt@depth5@100ms
                        stream_name = f'{symbol.lower()}@depth5@100ms'
                        params.append(stream_name)
                    
                    if debug:
                        print(f"Normalized symbols: {[s.replace("/", "").upper() for s in symbols]}")
                        print(f"WebSocket params: {params}")
                    
                    subscription = {
                        'method': 'SUBSCRIBE',
                        'params': params,
                        'id': 1,
                    }
                    
                    if debug:
                        print(f"Sending subscription: {subscription}")
                    
                    await ws.send(json.dumps(subscription))
                    
                    if debug:
                        print("Waiting for subscription response...")
                    
                    response = await ws.recv()
                    
                    if debug:
                        print(f"Subscription response: {response}")
                    
                    # 接続確認
                    response_data = json.loads(response)
                    if 'result' not in response_data:
                        if debug:
                            print(f"Warning: Unexpected response format: {response_data}")
                        # エラーでない場合も続行を試行
                        if 'error' in response_data:
                            raise Exception(f"Binance subscription error: {response_data}")

                    if debug:
                        print("Successfully subscribed to Binance WebSocket")

                    while True:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=15)
                            data = json.loads(msg)
                            
                            # データの検証
                            if 's' not in data or 'b' not in data or 'a' not in data:
                                if debug:
                                    print(f"Skipping invalid message: {data}")
                                continue
                            
                            orderbook = {
                                'source': 'cex',
                                'type': 'orderbook',
                                'exchange': 'binance',
                                'symbol': data['s'],
                                'bids': [[Decimal(d[0]), Decimal(d[1])] for d in data['b']],
                                'asks': [[Decimal(d[0]), Decimal(d[1])] for d in data['a']],
                            }
                            
                            if not debug:
                                event_queue.put(orderbook)
                            else:
                                print(orderbook)
                                
                        except asyncio.TimeoutError:
                            if debug:
                                print("Binance stream timeout, sending ping...")
                            await ws.ping()
                    
                    # 接続が成功したらループを抜ける
                    break
                    
            except Exception as e:
                if debug:
                    print(f"Failed to connect to {ws_url}: {e}")
                continue
        
        # WebSocket接続が失敗した場合、REST APIを使用
        if debug:
            print("WebSocket connection failed, trying REST API...")
        
        # REST APIを使用したオーダーブック取得
        while True:
            try:
                for symbol in symbols:
                    # シンボル名の正規化
                    normalized_symbol = symbol.replace("/", "").upper()
                    
                    # Binance REST APIを使用してオーダーブックを取得
                    url = f"https://fapi.binance.com/fapi/v1/depth?symbol={normalized_symbol}&limit=5"
                    
                    if debug:
                        print(f"Fetching orderbook from: {url}")
                    
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    if 'bids' in data and 'asks' in data:
                        orderbook = {
                            'source': 'cex',
                            'type': 'orderbook',
                            'exchange': 'binance',
                            'symbol': normalized_symbol,
                            'bids': [[Decimal(d[0]), Decimal(d[1])] for d in data['bids']],
                            'asks': [[Decimal(d[0]), Decimal(d[1])] for d in data['asks']],
                        }
                        
                        if not debug:
                            event_queue.put(orderbook)
                        else:
                            print(orderbook)
                    else:
                        if debug:
                            print(f"Invalid response format: {data}")
                
                # 100ms間隔で更新（WebSocketと同様）
                await asyncio.sleep(0.1)
                
            except Exception as e:
                if debug:
                    print(f"REST API error: {e}")
                await asyncio.sleep(1)  # エラー時は1秒待機
                    
    except Exception as e:
        if debug:
            print(f"Binance stream error: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
        raise e
            
            
# OKX USDM-Futures orderbook stream
# At OKX, they call perpetuals by the name of swaps.
async def stream_okx_usdm_orderbook(symbols: List[str],
                                    event_queue: aioprocessing.AioQueue,
                                    debug: bool = False):
    instruments = requests.get('https://www.okx.com/api/v5/public/instruments?instType=SWAP').json()
    multipliers = {
        d['instId'].replace('USD', 'USDT'): Decimal(d['ctMult']) / Decimal(d['ctVal'])
        for d in instruments['data']
    }
    
    async with websockets.connect('wss://ws.okx.com:8443/ws/v5/public', ping_interval=20, ping_timeout=20) as ws:
        args = [{'channel': 'books5', 'instId': f'{s.replace("/", "-")}-SWAP'} for s in symbols]
        subscription = {
            'op': 'subscribe',
            'args': args,
        }
        await ws.send(json.dumps(subscription))
        _ = await ws.recv()

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=15)
            except asyncio.TimeoutError:
                await ws.ping()
                continue
            data = json.loads(msg)
            multiplier = multipliers[data['arg']['instId']]
            symbol = data['arg']['instId'].replace('-SWAP', '').replace('-', '')
            bids = [[Decimal(d[0]), Decimal(d[1]) * multiplier] for d in data['data'][0]['bids']]
            asks = [[Decimal(d[0]), Decimal(d[1]) * multiplier] for d in data['data'][0]['asks']]
            orderbook = {
                'source': 'cex',
                'type': 'orderbook',
                'exchange': 'okx',
                'symbol': symbol,
                'bids':  bids,
                'asks': asks,
            }
            if not debug:
                event_queue.put(orderbook)
            else:
                print(orderbook)
            
            
if __name__ == '__main__':
    import nest_asyncio
    from functools import partial
    
    from utils import reconnecting_websocket_loop
    
    nest_asyncio.apply()
    
    symbols = ['ETH/USDT']
    
    binance_stream = reconnecting_websocket_loop(
        partial(stream_binance_usdm_orderbook, symbols, None, True),
        tag='binance_stream'
    )
    
    # 両方のストリームを有効化
    okx_stream = reconnecting_websocket_loop(
        partial(stream_okx_usdm_orderbook, symbols, None, True),
        tag='okx_stream'
    )
    
    loop = asyncio.get_event_loop()
    # コルーチンをタスクに変換してからwait
    binance_task = loop.create_task(binance_stream)
    okx_task = loop.create_task(okx_stream)
    
    loop.run_until_complete(asyncio.wait([
        binance_task,
        okx_task,
    ]))

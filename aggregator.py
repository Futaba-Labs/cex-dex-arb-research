import aioprocessing
from decimal import Decimal
from operator import itemgetter
from typing import Any, Dict, List


def aggregate_cex_orderbooks(orderbooks: Dict[str, Dict[str, Any]]) -> Dict[str, List[List[Decimal]]]:
    """
    :param orderbooks:
    {
        'binance': {'source': 'cex', 'type': 'orderbook', ... },
        'okx': {'source': 'cex', 'type': 'orderbook', ... },
    }
    """
    bids, asks = [], []
    
    for exchange, orderbook in orderbooks.items():
        bids.extend([b + [exchange] for b in orderbook['bids']])
        asks.extend([a + [exchange] for a in orderbook['asks']])
    
    bids = sorted(bids, key=itemgetter(0), reverse=True)
    asks = sorted(asks, key=itemgetter(0))
    
    return {'bids': bids, 'asks': asks}
    

async def event_handler(event_queue: aioprocessing.AioQueue):
    orderbooks = {}
    last_pool_updates: Dict[str, Dict[str, Any]] = {}
    
    while True:
        data = await event_queue.coro_get()

        try:
            source = data.get('source')

            if source == 'cex':
                # Only access symbol for CEX events
                symbol = data['symbol']
                if symbol not in orderbooks:
                    orderbooks[symbol] = {}

                orderbooks[symbol][data['exchange']] = data
                multi_orderbook = aggregate_cex_orderbooks(orderbooks[symbol])
                print(multi_orderbook)

            elif source == 'dex':
                etype = data.get('type')
                if etype == 'block':
                    # Light block log
                    print({
                        'type': 'block',
                        'block_number': data.get('block_number'),
                        'base_fee': data.get('base_fee'),
                        'next_base_fee': data.get('next_base_fee'),
                    })
                elif etype == 'pool_update':
                    # Track last pool update per symbol and print
                    sym = data.get('symbol')
                    last_pool_updates[sym] = data
                    print({'type': 'pool_update', 'symbol': sym, 'tick': data.get('tick'), 'liquidity': data.get('liquidity')})

            else:
                # Unknown event source; keep handler alive and log
                print({'type': 'unknown_event', 'event': data})

        except Exception as e:
            # Prevent handler from dying on malformed events
            print({'type': 'event_handler_error', 'error': str(e)})
    
    
if __name__ == '__main__':
    import asyncio
    import nest_asyncio
    from functools import partial
    import os
    from dotenv import load_dotenv
    
    from utils import reconnecting_websocket_loop
    from cex_streams import stream_binance_usdm_orderbook, stream_okx_usdm_orderbook
    from dex_streams import stream_new_blocks, stream_uniswap_v3_events
    from constants import TOKENS, POOLS
    
    nest_asyncio.apply()
    load_dotenv(override=True)
    
    symbols = ['ETH/USDT']
    event_queue = aioprocessing.AioQueue()
    
    # Testing CEX aggregator
    binance_stream = reconnecting_websocket_loop(
        partial(stream_binance_usdm_orderbook, symbols, event_queue, False),
        tag='binance_stream'
    )
    
    okx_stream = reconnecting_websocket_loop(
        partial(stream_okx_usdm_orderbook, symbols, event_queue, False),
        tag='okx_stream'
    )
    
    # DEX streams (Ethereum mainnet)
    HTTP_RPC_URL = os.getenv('HTTP_RPC_URL')
    WS_RPC_URL = os.getenv('WS_RPC_URL')
    new_blocks_stream = reconnecting_websocket_loop(
        partial(stream_new_blocks, WS_RPC_URL, event_queue, False),
        tag='new_blocks_stream'
    )
    uniswap_v3_stream = reconnecting_websocket_loop(
        partial(stream_uniswap_v3_events, HTTP_RPC_URL, WS_RPC_URL, TOKENS, POOLS, event_queue, False),
        tag='uniswap_v3_stream'
    )
    
    event_handler_loop = event_handler(event_queue)
    
    loop = asyncio.get_event_loop()
    # Create tasks before waiting (Python 3.12+ forbids bare coroutines in wait)
    binance_task = loop.create_task(binance_stream)
    okx_task = loop.create_task(okx_stream)
    handler_task = loop.create_task(event_handler_loop)
    new_blocks_task = loop.create_task(new_blocks_stream)
    uniswap_v3_task = loop.create_task(uniswap_v3_stream)

    loop.run_until_complete(asyncio.wait([
        binance_task,
        okx_task,
        handler_task,
        new_blocks_task,
        uniswap_v3_task,
    ]))
    

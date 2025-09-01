import os
import json
import eth_abi
import asyncio
import eth_utils
import websockets
import aioprocessing

from web3 import Web3
from functools import partial
from typing import Any, Dict, List
from multicall import Call, Multicall

from constants import TOKENS, POOLS
from utils import calculate_next_block_base_fee


async def stream_new_blocks(ws_rpc_url: str,
                            event_queue: aioprocessing.AioQueue,
                            debug: bool = False):
    
    async with websockets.connect(ws_rpc_url) as ws:
        if debug:
            print(f"Connecting to WS for new blocks: {ws_rpc_url}")
        subscription = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'eth_subscribe',
            'params': ['newHeads']
        }

        await ws.send(json.dumps(subscription))
        ack = await ws.recv()
        if debug:
            print(f"Subscribed newHeads ack: {ack}")

        WEI = 10 ** 18

        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=60 * 10)
            block = json.loads(msg)['params']['result']
            block_number = int(block['number'], base=16)
            base_fee = int(block['baseFeePerGas'], base=16)
            next_base_fee = calculate_next_block_base_fee(block)
            event = {
                'source': 'dex',
                'type': 'block',
                'block_number': block_number,
                'base_fee': base_fee / WEI,
                'next_base_fee': next_base_fee / WEI,
            }
            if not debug:
                event_queue.put(event)
            else:
                print(event)
            


async def stream_uniswap_v3_events(http_rpc_url: str,
                                   ws_rpc_url: str,
                                   tokens: Dict[str, List[Any]],
                                   pools: List[List[Any]],
                                   event_queue: aioprocessing.AioQueue,
                                   debug: bool = False):
    
    # Web3インスタンスの作成
    w3 = Web3(Web3.HTTPProvider(http_rpc_url))
    
    block_number = w3.eth.get_block_number()
    
    # Uniswap V3 uses slot0() to get current sqrt price and tick
    # We'll also need to get liquidity from the pool
    slot0_signature = 'slot0()((uint160,int24,uint16,uint16,uint16,uint8,bool))'
    liquidity_signature = 'liquidity()(uint128)'
    
    # Filter to V3 pools first
    filtered_pools = [pool for pool in pools if pool['version'] == 3]
    pools = {pool['address'].lower(): pool for pool in filtered_pools}

    # Get initial pool data for V3 pools only
    pool_data = {}
    for pool in filtered_pools:
        try:
            pool_name = f'{pool["exchange"]}_{pool["version"]}_{pool["name"].replace("/", "")}'
            
            # Get slot0 data (sqrt price, tick, etc.)
            contract = w3.eth.contract(
                address=pool['address'],
                abi=[
                    {
                        "inputs": [],
                        "name": "slot0",
                        "outputs": [
                            {"name": "sqrtPriceX96", "type": "uint160"},
                            {"name": "tick", "type": "int24"},
                            {"name": "observationIndex", "type": "uint16"},
                            {"name": "observationCardinality", "type": "uint16"},
                            {"name": "observationCardinalityNext", "type": "uint16"},
                            {"name": "feeProtocol", "type": "uint8"},
                            {"name": "unlocked", "type": "bool"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    },
                    {
                        "inputs": [],
                        "name": "liquidity",
                        "outputs": [{"name": "", "type": "uint128"}],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
            )
            
            slot0 = contract.functions.slot0().call()
            liquidity = contract.functions.liquidity().call()
            
            pool_data[pool_name] = {
                'sqrtPriceX96': slot0[0],
                'tick': slot0[1],
                'liquidity': liquidity
            }
            
            if debug:
                print(f"Initial data for {pool_name}: sqrtPriceX96={slot0[0]}, tick={slot0[1]}, liquidity={liquidity}")
                
        except Exception as e:
            if debug:
                print(f"Error getting data for {pool['address']}: {e}")
            pool_data[pool_name] = {
                'sqrtPriceX96': 0,
                'tick': 0,
                'liquidity': 0
            }
    
    """
    pool_data:
    {
        'uniswap_3_ETHUSDT': {'sqrtPriceX96': 123456789, 'tick': 12345, 'liquidity': 987654321},
        'sushiswap_3_ETHUSDT': {'sqrtPriceX96': 234567890, 'tick': 23456, 'liquidity': 876543210}
    }
    """
    
    # pools dict already prepared above
    
    def _publish(block_number: int,
                 pool: Dict[str, Any],
                 data: List[Any] = []):
        
        exchange = pool['exchange']
        version = pool['version']
        symbol = f'{pool["token0"]}{pool["token1"]}'

        # save to "pool_data" in memory
        symbol_key = f'{exchange}_{version}_{symbol}'
        
        if len(data) == 3:
            # Update pool data with new Swap event data
            pool_data[symbol_key]['sqrtPriceX96'] = data[0]
            pool_data[symbol_key]['tick'] = data[1]
            pool_data[symbol_key]['liquidity'] = data[2]
            
        token_idx = {
            pool['token0']: 0,
            pool['token1']: 1,
        }
        
        decimals = {
            pool['token0']: tokens[pool['token0']][1],
            pool['token1']: tokens[pool['token1']][1],
        }
        
        current_data = pool_data[symbol_key]
        
        pool_update = {
            'source': 'dex',
            'type': 'pool_update',
            'block_number': block_number,
            'exchange': pool['exchange'],
            'version': pool['version'],
            'symbol': symbol,
            'token_idx': token_idx,
            'decimals': decimals,
            'sqrtPriceX96': current_data['sqrtPriceX96'],
            'tick': current_data['tick'],
            'liquidity': current_data['liquidity'],
        }
        
        if not debug:
            event_queue.put(pool_update)
        else:
            print(pool_update)
            
    """
    Send initial pool data so that price can be calculated even if the pool is idle
    """
    for address, pool in pools.items():
        _publish(block_number, pool)

    # Uniswap V3 Swap event signature
    # Ensure 0x-prefixed topic for subscription
    swap_event_selector = w3.keccak(text='Swap(address,address,int256,int256,uint160,uint128,int24)').hex()
    if not swap_event_selector.startswith('0x'):
        swap_event_selector = '0x' + swap_event_selector
    
    async with websockets.connect(ws_rpc_url) as ws:
        if debug:
            print(f"Connecting to WS for Uniswap V3 logs: {ws_rpc_url}")
        subscription = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'eth_subscribe',
            'params': [
                'logs',
                {
                    'address': list(pools.keys()),
                    'topics': [swap_event_selector]
                }
            ]
        }

        await ws.send(json.dumps(subscription))
        ack = await ws.recv()
        if debug:
            print(f"Subscribed logs ack: {ack}")

        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=60 * 10)
            event = json.loads(msg)['params']['result']
            address = event['address'].lower()

            if address in pools:
                block_number = int(event['blockNumber'], base=16)
                pool = pools[address]
                
                # Parse Swap event data (non-indexed parameters only):
                # amount0, amount1, sqrtPriceX96, liquidity, tick
                swap_data = eth_abi.decode(
                    ['int256', 'int256', 'uint160', 'uint128', 'int24'],
                    eth_utils.decode_hex(event['data'])
                )
                
                # Extract relevant data: sqrtPriceX96, tick, liquidity
                sqrtPriceX96 = swap_data[2]
                liquidity = swap_data[3]
                tick = swap_data[4]
                
                _publish(block_number, pool, [sqrtPriceX96, tick, liquidity])
                

if __name__ == '__main__':
    import os
    import nest_asyncio
    from functools import partial
    from dotenv import load_dotenv
    
    from utils import reconnecting_websocket_loop
    
    nest_asyncio.apply()

    load_dotenv(override=True)

    HTTP_RPC_URL = os.getenv('HTTP_RPC_URL')
    WS_RPC_URL = os.getenv('WS_RPC_URL')
    
    new_blocks_stream = reconnecting_websocket_loop(
        partial(stream_new_blocks, WS_RPC_URL, None, True),
        tag='new_blocks_stream'
    )
    
    uniswap_v3_stream = reconnecting_websocket_loop(
        partial(stream_uniswap_v3_events, HTTP_RPC_URL, WS_RPC_URL, TOKENS, POOLS, None, True),
        tag='uniswap_v3_stream'
    )

    loop = asyncio.get_event_loop()

    new_blocks_task = loop.create_task(new_blocks_stream)
    uniswap_v3_task = loop.create_task(uniswap_v3_stream)
    
    loop.run_until_complete(asyncio.wait([
        new_blocks_task,
        uniswap_v3_task,
    ]))

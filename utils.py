import random
import asyncio
import websockets

from typing import Any, Callable, Dict


async def reconnecting_websocket_loop(stream_fn: Callable, tag: str):
    """Run a streaming coroutine with resilient reconnection.

    Any exception triggers a short backoff and a retry, so transient
    decode/timeout errors do not permanently stop the stream.
    """
    backoff = 2
    while True:
        try:
            await stream_fn()
            # If the stream_fn returns normally, restart after short delay
            await asyncio.sleep(backoff)

        except (websockets.ConnectionClosedError, websockets.ConnectionClosedOK) as e:
            print(f'{tag} websocket connection closed: {e}')
            print('Reconnecting...')
            await asyncio.sleep(backoff)

        except asyncio.TimeoutError as e:
            print(f'{tag} websocket timeout: {e}')
            print('Reconnecting...')
            await asyncio.sleep(backoff)

        except Exception as e:
            print(f'An error has occurred with {tag} websocket: {e}')
            print('Reconnecting...')
            await asyncio.sleep(backoff)


def calculate_next_block_base_fee(block: Dict[str, Any]):
    base_fee = int(block['baseFeePerGas'], base=16)
    gas_used = int(block['gasUsed'], base=16)
    gas_limit = int(block['gasLimit'], base=16)

    target_gas_used = gas_limit / 2
    target_gas_used = 1 if target_gas_used == 0 else target_gas_used

    if gas_used > target_gas_used:
        new_base_fee = base_fee + \
            ((base_fee * (gas_used - target_gas_used)) / target_gas_used) / 8
    else:
        new_base_fee = base_fee - \
            ((base_fee * (target_gas_used - gas_used)) / target_gas_used) / 8

    return int(new_base_fee + random.randint(0, 9))

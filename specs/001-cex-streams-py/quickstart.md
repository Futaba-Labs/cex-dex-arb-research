# Quickstart Guide: Connex API Integration

## Prerequisites
- Python 3.11+
- Jupyter notebook
- Connex API credentials (API key)
- Running instance of the arbitrage system

## Quick Validation Steps

### 1. Test Connex Connection
```python
# In Jupyter notebook
import asyncio
import aiohttp

async def test_connex_health():
    """Verify Connex API is accessible"""
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.connex.com/v1/status') as resp:
            assert resp.status == 200
            data = await resp.json()
            print(f"Connex Status: {data['status']}")
            return data['status'] == 'healthy'

# Run test
await test_connex_health()
```

### 2. Test WebSocket Stream
```python
import websockets
import json

async def test_websocket_connection():
    """Test WebSocket connection and subscription"""
    uri = "wss://api.connex.com/ws/v1/market"

    async with websockets.connect(uri) as ws:
        # Subscribe to ETH/USDT orderbook
        subscribe_msg = {
            "id": 1,
            "method": "SUBSCRIBE",
            "params": {
                "symbols": ["ETH/USDT"],
                "channels": ["orderbook"],
                "exchanges": ["binance"],
                "depth": 5
            }
        }

        await ws.send(json.dumps(subscribe_msg))

        # Receive first orderbook snapshot
        response = await ws.recv()
        data = json.loads(response)

        assert data['type'] == 'snapshot'
        assert data['symbol'] == 'ETH/USDT'
        assert 'bids' in data and 'asks' in data

        print(f"✅ Received orderbook for {data['symbol']}")
        print(f"   Best bid: {data['bids'][0]}")
        print(f"   Best ask: {data['asks'][0]}")

        return True

# Run test
await test_websocket_connection()
```

### 3. Test Data Compatibility
```python
from decimal import Decimal
import aioprocessing

async def test_data_compatibility():
    """Verify data format works with existing aggregator"""

    # Import the new Connex streaming function
    from cex_streams import stream_connex_orderbook

    # Import existing aggregator
    from aggregator import MultiOrderbook

    # Setup
    event_queue = aioprocessing.AioQueue()
    symbols = ['ETH/USDT']

    # Start streaming in background
    stream_task = asyncio.create_task(
        stream_connex_orderbook(symbols, event_queue, debug=True)
    )

    # Get first event
    event = await event_queue.coro_get(timeout=5)

    # Validate event structure
    assert event['type'] == 'orderbook'
    assert event['exchange'] in ['binance', 'okx']
    assert event['symbol'] in symbols
    assert 'data' in event

    # Test with aggregator
    multi_ob = MultiOrderbook()
    multi_ob.update(event['exchange'], event['data'])

    # Verify aggregator processed it
    assert multi_ob.get_best_bid() is not None
    assert multi_ob.get_best_ask() is not None

    print(f"✅ Data compatible with aggregator")
    print(f"   Best bid: {multi_ob.get_best_bid()}")
    print(f"   Best ask: {multi_ob.get_best_ask()}")

    # Cleanup
    stream_task.cancel()
    return True

# Run test
await test_data_compatibility()
```

### 4. Performance Test
```python
import time

async def test_latency():
    """Measure end-to-end latency"""

    from cex_streams import stream_connex_orderbook

    latencies = []
    event_queue = aioprocessing.AioQueue()

    # Start streaming
    stream_task = asyncio.create_task(
        stream_connex_orderbook(['ETH/USDT'], event_queue)
    )

    # Measure 10 updates
    for _ in range(10):
        start = time.time()
        event = await event_queue.coro_get(timeout=5)
        latency = (time.time() - start) * 1000  # Convert to ms
        latencies.append(latency)

    # Calculate stats
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    print(f"✅ Latency Test Results:")
    print(f"   Average: {avg_latency:.2f}ms")
    print(f"   Maximum: {max_latency:.2f}ms")
    print(f"   Target: <50ms")

    assert avg_latency < 50, "Latency exceeds target"

    # Cleanup
    stream_task.cancel()
    return True

# Run test
await test_latency()
```

### 5. Full Integration Test
```python
async def test_full_integration():
    """Test complete arbitrage flow with Connex"""

    # Import all components
    from cex_streams import stream_connex_orderbook
    from dex_streams import stream_new_blocks
    from aggregator import MultiOrderbook
    import aioprocessing

    # Setup queues
    event_queue = aioprocessing.AioQueue()

    # Start all streams
    tasks = [
        asyncio.create_task(
            stream_connex_orderbook(['ETH/USDT', 'ETH/USDC'], event_queue)
        ),
        asyncio.create_task(
            stream_new_blocks(WS_RPC_URL, event_queue)
        )
    ]

    # Process events
    multi_ob = MultiOrderbook()
    events_processed = 0

    while events_processed < 20:
        event = await event_queue.coro_get(timeout=10)

        if event['type'] == 'orderbook':
            multi_ob.update(event['exchange'], event['data'])

            # Check spread
            if multi_ob.get_best_bid() and multi_ob.get_best_ask():
                spread = multi_ob.get_best_ask()[0] - multi_ob.get_best_bid()[0]
                print(f"Spread: {spread}")

        events_processed += 1

    print(f"✅ Processed {events_processed} events successfully")

    # Cleanup
    for task in tasks:
        task.cancel()

    return True

# Run test
await test_full_integration()
```

## Validation Checklist

Run each test in order and verify:

- [ ] Connex API is accessible (Test 1)
- [ ] WebSocket connection works (Test 2)
- [ ] Data format is compatible (Test 3)
- [ ] Latency meets requirements (Test 4)
- [ ] Full system integration works (Test 5)

## Success Criteria

All tests must pass with:
- ✅ Successful API connection
- ✅ Real-time data streaming
- ✅ Backward compatibility maintained
- ✅ Latency under 50ms
- ✅ No errors in 20+ events

## Troubleshooting

### Connection Issues
```python
# Check API key
print(f"API Key configured: {bool(os.getenv('CONNEX_API_KEY'))}")

# Test network connectivity
async with aiohttp.ClientSession() as session:
    async with session.get('https://api.connex.com/health') as resp:
        print(f"API reachable: {resp.status == 200}")
```

### Data Format Issues
```python
# Debug event structure
event = await event_queue.coro_get()
import pprint
pprint.pprint(event)

# Verify transformation
from connex_client import ConnexOrderbookAdapter
adapter = ConnexOrderbookAdapter()
legacy_format = adapter.to_legacy_format(event['data'])
print(f"Legacy format: {legacy_format}")
```

### Performance Issues
```python
# Profile the stream
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run streaming for 30 seconds
await asyncio.sleep(30)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

## Next Steps

Once all tests pass:
1. Review generated tasks.md
2. Implement each task in order
3. Run full test suite
4. Monitor production metrics

---
**Quick Test Command**
```bash
jupyter notebook connex-integration-test.ipynb
```

Run all cells to validate the integration end-to-end.
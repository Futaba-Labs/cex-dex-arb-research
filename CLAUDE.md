# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a CEX-DEX arbitrage research template for MEV opportunities across centralized exchanges (CEXs) and decentralized exchanges (DEXs). The project streams real-time orderbook data from CEXs (Binance, OKX) and blockchain events from DEXs (Uniswap V2/V3, Sushiswap).

## Key Commands

### Development
- Run main notebook: `jupyter notebook cex-dex-arb.ipynb`
- Install dependencies: `pip install -r requirements.txt`
- Run spread chart visualization: `python spread_chart.py`

### Running Streams
- CEX streams can be tested: Run examples at bottom of `cex_streams.py`
- DEX streams can be tested: Run examples at bottom of `dex_streams.py`

## Current Development Focus

### Feature: CEX Streams Migration to Connex API (Branch: 001-cex-streams-py)
- **Goal**: Replace direct WebSocket connections with Connex unified API
- **Status**: Design phase complete, ready for implementation
- **Key Changes**:
  - New `connex_client.py` module for Connex API interaction
  - Adapter pattern for backward compatibility
  - Modified `cex_streams.py` to use Connex instead of direct connections

## Architecture

### Core Components

1. **Data Streams**
   - `cex_streams.py`: WebSocket streams for CEX orderbook data (migrating to Connex API)
   - `dex_streams.py`: WebSocket streams for DEX events (Uniswap V3, new blocks)
   - `1inch_streams.py`: 1inch limit orderbook events stream
   - `connex_client.py`: [NEW] Connex API client for unified CEX data access

2. **Aggregation Layer**
   - `aggregator.py`: Merges multiple CEX orderbooks into a MultiOrderbook structure
   - Sorts bids (highest first) and asks (lowest first) across exchanges

3. **Event Processing**
   - Event handlers defined in `cex-dex-arb.ipynb`
   - Processes real-time data through `aioprocessing.AioQueue`
   - Calculates spreads accounting for exchange fees

4. **Visualization**
   - `spread_chart.py`: PyQt6-based real-time chart window
   - Publisher/Subscriber pattern on port 9999

### Data Flow
```
CEX/DEX Streams → Event Queue → Event Handler → Spread Calculation → Chart Publisher
```

### Stream Recovery
All streams wrapped with `reconnecting_websocket_loop` from `utils.py` for automatic reconnection on errors.

## Configuration

### Environment Variables (.env)
- `HTTP_RPC_URL`: HTTP RPC endpoint for blockchain queries
- `WS_RPC_URL`: WebSocket RPC endpoint for real-time blockchain events

### Token/Pool Configuration
- `constants.py`: Defines supported tokens and liquidity pools
- Tokens: ETH, USDT, USDC with addresses and decimals
- Pools: Uniswap V2/V3, Sushiswap pools with fees

### Exchange Fees
Current taker fees (LV 1):
- Binance: 0.04%
- OKX: 0.05%
- Uniswap: 0.3%
- Sushiswap: 0.3%

## Testing Individual Components

### CEX Stream Testing
```python
# At bottom of cex_streams.py, uncomment and run
symbols = ['ETH/USDT']
event_queue = aioprocessing.AioQueue()
asyncio.run(stream_binance_usdm_orderbook(symbols, event_queue, True))
```

### DEX Stream Testing
```python
# At bottom of dex_streams.py, uncomment and run
event_queue = aioprocessing.AioQueue()
asyncio.run(stream_new_blocks(WS_RPC_URL, event_queue, True))
```

## Multi-Threading Architecture
- Main thread: Jupyter notebook execution
- Event handler thread: Processing queue data
- Async tasks: Individual stream coroutines (Binance, OKX, blocks, Uniswap V3)
- Uses `nest_asyncio` to allow nested event loops in Jupyter
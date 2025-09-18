# Data Model Specification

## Overview
Data structures and entities for the Connex API integration with CEX orderbook streaming.

## Core Entities

### 1. ConnexConfig
**Purpose**: Configuration for Connex API connection
**Fields**:
- `api_key`: string - API key for authentication
- `api_secret`: string (optional) - API secret if required
- `base_url`: string - Base URL for Connex API
- `ws_url`: string - WebSocket URL for streaming
- `timeout`: int - Connection timeout in seconds
- `max_retries`: int - Maximum retry attempts

### 2. OrderbookSnapshot
**Purpose**: Represents current state of an orderbook
**Fields**:
- `symbol`: string - Trading pair (e.g., "ETH/USDT")
- `exchange`: string - Exchange name (e.g., "binance", "okx")
- `timestamp`: float - Unix timestamp of snapshot
- `bids`: List[PriceLevel] - Buy orders
- `asks`: List[PriceLevel] - Sell orders
- `sequence`: int (optional) - Sequence number for order tracking

### 3. PriceLevel
**Purpose**: Single price level in orderbook
**Fields**:
- `price`: Decimal - Price level
- `quantity`: Decimal - Volume at this level
- `update_id`: int (optional) - Update identifier

### 4. StreamEvent
**Purpose**: Event emitted to the queue system
**Fields**:
- `type`: string - Event type ("orderbook", "error", "status")
- `exchange`: string - Source exchange
- `symbol`: string - Trading pair
- `data`: dict - Event-specific data
- `timestamp`: float - Event timestamp
- `debug_info`: dict (optional) - Debug information

### 5. ConnexSubscription
**Purpose**: Subscription management for streams
**Fields**:
- `id`: string - Subscription identifier
- `symbols`: List[string] - Subscribed symbols
- `exchanges`: List[string] - Target exchanges
- `stream_type`: string - Type of stream (e.g., "orderbook", "trades")
- `status`: string - "active", "paused", "error"

## State Transitions

### Connection States
```
DISCONNECTED → CONNECTING → CONNECTED → STREAMING
      ↑            ↓           ↓           ↓
      └────────ERROR←──────────┴───────────┘
```

### Subscription States
```
INACTIVE → SUBSCRIBING → ACTIVE → UNSUBSCRIBING → INACTIVE
     ↑          ↓          ↓            ↓
     └────── FAILED ←──────┴────────────┘
```

## Data Flow

### Input Flow
```
Connex API Response → ConnexClient → Adapter → OrderbookSnapshot → StreamEvent → Queue
```

### Transformation Rules
1. **Price Normalization**: All prices as Decimal with 8 decimal places
2. **Symbol Mapping**:
   - Connex format → Standard format (e.g., "ETHUSDT" → "ETH/USDT")
   - Exchange identifiers normalized to lowercase
3. **Timestamp Handling**: Convert all timestamps to Unix epoch (float)
4. **Quantity Scaling**: Handle different decimal precisions per exchange

## Validation Rules

### OrderbookSnapshot
- `bids` must be sorted in descending price order
- `asks` must be sorted in ascending price order
- `timestamp` must be within 60 seconds of current time
- `symbol` must match supported pairs list
- No negative prices or quantities

### ConnexConfig
- `api_key` must be non-empty string
- `timeout` must be between 5 and 300 seconds
- `max_retries` must be between 0 and 10
- URLs must be valid HTTP/HTTPS or WSS protocols

### StreamEvent
- `type` must be one of defined event types
- `timestamp` must be monotonically increasing per stream
- `data` must contain required fields per event type

## Backward Compatibility

### Legacy Format Mapping
Current system expects:
```python
{
    'exchange': str,
    'symbol': str,
    'bids': [[price, quantity], ...],
    'asks': [[price, quantity], ...],
    'timestamp': float
}
```

Adapter transformation:
```python
def to_legacy_format(orderbook: OrderbookSnapshot) -> dict:
    return {
        'exchange': orderbook.exchange,
        'symbol': orderbook.symbol,
        'bids': [[float(level.price), float(level.quantity)]
                 for level in orderbook.bids],
        'asks': [[float(level.price), float(level.quantity)]
                 for level in orderbook.asks],
        'timestamp': orderbook.timestamp
    }
```

## Error Handling

### Error Types
1. **ConnectionError**: Failed to establish connection
2. **AuthenticationError**: Invalid API credentials
3. **SubscriptionError**: Failed to subscribe to stream
4. **DataFormatError**: Unexpected data format from API
5. **RateLimitError**: Exceeded API rate limits

### Error Recovery
- Automatic reconnection with exponential backoff
- Queue buffering during disconnection
- State persistence for recovery
- Fallback to last known good state

## Performance Considerations

### Memory Optimization
- Limit orderbook depth to top 20 levels by default
- Implement circular buffer for event history
- Clear stale data after 5 minutes

### Latency Targets
- Connection establishment: <1 second
- Data transformation: <1ms per orderbook
- Queue insertion: <0.5ms
- End-to-end latency: <50ms

---
**Version**: 1.0.0
**Created**: 2025-01-18
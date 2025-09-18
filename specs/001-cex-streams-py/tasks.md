# Implementation Tasks: CEX Streams Migration to Connex API

**Feature**: CEX Streams Migration to Connex API
**Branch**: `001-cex-streams-py`
**Generated**: 2025-01-18

## Summary
Migrate CEX orderbook streaming from direct WebSocket connections to Connex unified API, maintaining backward compatibility with existing aggregator.

## Task Execution Order

### Phase 1: Setup & Research
These tasks establish the development environment and explore the Connex API.

**T001: Create Jupyter research notebook** [P]
- File: `connex-exploration.ipynb`
- Create notebook with sections for API testing, data format exploration, and integration tests
- Setup imports: asyncio, aiohttp, websockets, json, decimal
- Configure logging for debug output

**T002: Setup environment variables and credentials**
- File: `.env`
- Add CONNEX_API_KEY placeholder
- Add CONNEX_API_SECRET placeholder (if needed)
- Add CONNEX_WS_URL and CONNEX_REST_URL
- Document how to obtain credentials in README

**T003: Test Connex REST API connectivity** [P]
- File: `connex-exploration.ipynb` (Cell 2-3)
- Implement test_connex_health() function
- Test /v1/status endpoint
- Verify authentication headers work
- Log response format and latency

**T004: Test Connex WebSocket connection** [P]
- File: `connex-exploration.ipynb` (Cell 4-5)
- Implement test_websocket_connection() function
- Test subscription to ETH/USDT orderbook
- Capture and analyze message formats
- Document reconnection behavior

### Phase 2: Core Implementation
Create the new Connex client module and data models.

**T005: Implement ConnexConfig data model** [P]
- File: `connex_client.py`
- Create ConnexConfig class with fields from data-model.md
- Add validation for API keys and URLs
- Implement from_env() class method to load from environment
- Add timeout and retry configuration

**T006: Implement OrderbookSnapshot data model** [P]
- File: `connex_client.py`
- Create OrderbookSnapshot, PriceLevel classes
- Implement Decimal handling for prices/quantities
- Add timestamp validation
- Ensure bids/asks sorting logic

**T007: Implement StreamEvent data model** [P]
- File: `connex_client.py`
- Create StreamEvent class for queue events
- Add event type enums ("orderbook", "error", "status")
- Include debug_info field for troubleshooting
- Implement to_dict() for serialization

**T008: Create ConnexOrderbookAdapter**
- File: `connex_client.py`
- Implement transform_to_legacy_format() method
- Map Connex orderbook to existing format expected by aggregator.py
- Handle symbol normalization (ETHUSDT → ETH/USDT)
- Convert price levels to [[price, quantity]] format

**T009: Implement ConnexWebSocketClient**
- File: `connex_client.py`
- Create async WebSocket client class
- Implement connect() with authentication
- Add subscribe() method for symbol subscriptions
- Handle message parsing and event generation
- Implement reconnection logic with exponential backoff

**T010: Implement ConnexRESTClient** [P]
- File: `connex_client.py`
- Create REST client for fallback/initial data
- Implement get_orderbook() method
- Add rate limiting handling
- Include retry logic for failed requests

### Phase 3: Integration
Modify existing code to use Connex and ensure compatibility.

**T011: Create stream_connex_orderbook function**
- File: `cex_streams.py`
- Add new async function stream_connex_orderbook()
- Initialize ConnexWebSocketClient
- Process incoming messages through adapter
- Emit events to queue in existing format
- Add debug logging

**T012: Update cex_streams.py to route through Connex**
- File: `cex_streams.py`
- Modify stream_binance_usdm_orderbook() to use Connex
- Modify stream_okx_orderbook() to use Connex
- Add feature flag to switch between direct/Connex modes
- Maintain backward compatibility

**T013: Add Connex configuration to constants**
- File: `constants.py`
- Add CONNEX_ENABLED flag
- Add supported Connex symbols mapping
- Add Connex-specific configuration constants
- Document migration path

### Phase 4: Testing
Comprehensive testing in Jupyter and unit tests.

**T014: Create adapter unit tests** [P]
- File: `connex-exploration.ipynb` (Testing section)
- Test ConnexOrderbookAdapter transformations
- Verify symbol mapping works correctly
- Test edge cases (empty orderbook, single level)
- Validate decimal precision handling

**T015: Integration test with aggregator**
- File: `connex-exploration.ipynb` (Integration section)
- Import existing aggregator.py
- Stream data through Connex client
- Verify MultiOrderbook processes correctly
- Test spread calculations work

**T016: Performance benchmarking**
- File: `connex-exploration.ipynb` (Performance section)
- Measure end-to-end latency (target <50ms)
- Compare with direct connection baseline
- Test with multiple symbols simultaneously
- Profile memory usage

**T017: WebSocket reconnection test** [P]
- File: `connex-exploration.ipynb` (Reliability section)
- Simulate connection drops
- Verify automatic reconnection
- Test state recovery after disconnect
- Validate no data loss during reconnect

**T018: Full system integration test**
- File: `connex-exploration.ipynb` (E2E section)
- Run complete arbitrage flow with Connex
- Stream from both CEX (via Connex) and DEX
- Verify event queue processing
- Monitor spread calculations
- Run for 100+ events without errors

### Phase 5: Documentation & Polish

**T019: Update documentation** [P]
- File: `README.md`, `CLAUDE.md`
- Document Connex setup process
- Add configuration examples
- Update architecture diagrams
- Include troubleshooting guide

**T020: Add comprehensive logging**
- Files: `connex_client.py`, `cex_streams.py`
- Add debug logs for connection state
- Log all subscriptions and unsubscriptions
- Include performance metrics in logs
- Add error context for debugging

## Parallel Execution Examples

### Group 1: Initial Testing (T001-T004)
Can run in parallel after setup:
```bash
# In separate terminals/cells:
Task T001 "Create Jupyter research notebook"
Task T003 "Test Connex REST API connectivity"
Task T004 "Test Connex WebSocket connection"
```

### Group 2: Data Models (T005-T007, T010)
All data model tasks can run in parallel:
```bash
Task T005 "Implement ConnexConfig data model"
Task T006 "Implement OrderbookSnapshot data model"
Task T007 "Implement StreamEvent data model"
Task T010 "Implement ConnexRESTClient"
```

### Group 3: Testing Tasks (T014, T017, T019)
Independent test files can run in parallel:
```bash
Task T014 "Create adapter unit tests"
Task T017 "WebSocket reconnection test"
Task T019 "Update documentation"
```

## Dependencies & Notes

### Critical Path
1. T002 (credentials) → T003/T004 (API testing)
2. T005-T007 (models) → T008 (adapter) → T009 (WebSocket client)
3. T008-T009 → T011 (stream function) → T012 (integration)
4. T011-T012 → T015-T016 (integration testing)
5. T015-T016 → T018 (full system test)

### File Creation Order
1. `connex-exploration.ipynb` - Research and testing
2. `connex_client.py` - New module with all Connex logic
3. Modify `cex_streams.py` - Integration point
4. Update `constants.py` - Configuration

### Risk Mitigation
- Keep feature flag to fallback to direct connections
- Extensive testing in Jupyter before production
- Monitor latency closely during migration
- Maintain backward compatibility throughout

## Validation Checklist

Before considering implementation complete:
- [ ] All Jupyter test cells pass
- [ ] Latency remains under 50ms
- [ ] No data format breaking changes
- [ ] Aggregator works without modification
- [ ] 100+ events processed without errors
- [ ] Reconnection handling tested
- [ ] Documentation updated

## Quick Commands

```bash
# Start Jupyter for development
jupyter notebook connex-exploration.ipynb

# Run integration test
python -c "import asyncio; from cex_streams import stream_connex_orderbook; asyncio.run(test_integration())"

# Monitor performance
python -c "from connex_client import benchmark; benchmark()"
```

---
**Note**: Tasks marked [P] can be executed in parallel as they work on independent files or sections.
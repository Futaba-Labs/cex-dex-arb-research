TOKENS = {
    'ETH': ['0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', 18],
    'USDT': ['0xdAC17F958D2ee523a2206206994597C13D831ec7', 6],
    'USDC': ['0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 6],
}

columns = ['exchange', 'version', 'name', 'address', 'fee', 'token0', 'token1']

POOLS = [
    # V2 Pools
    ['uniswap', 2, 'ETH/USDT', '0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852', 3000, 'ETH', 'USDT'],
    ['sushiswap', 2, 'ETH/USDT', '0x06da0fd433C1A5d7a4faa01111c044910A184553', 3000, 'ETH', 'USDT'],
    # V3 Pools - Actual Uniswap V3 pool addresses
    ['uniswap', 3, 'USDC/ETH', '0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8', 3000, 'USDC', 'ETH'],  # 0.3% fee tier
    ['uniswap', 3, 'ETH/USDT', '0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36', 500, 'ETH', 'USDT'],   # 0.05% fee tier
    ['uniswap', 3, 'ETH/USDT', '0x11b815efB8f581194ae79006d24E0d814B7697F6', 3000, 'ETH', 'USDT'], # 0.3% fee tier (main ETH/USDT pool)
]

POOLS = [dict(zip(columns, pool)) for pool in POOLS]
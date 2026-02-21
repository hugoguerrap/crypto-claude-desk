#!/usr/bin/env python3
"""
Crypto Exchange CCXT Ultra Server
Multi-exchange data: OHLCV, orderbooks, volume analysis, liquidity, arbitrage.
Uses CCXT with reliable exchanges only - no API keys required.
"""

from fastmcp import FastMCP
import ccxt
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Union
import json
from datetime import datetime, timedelta
import time
import logging

from validators import validate_symbol, validate_exchange, validate_positive_int

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("crypto-exchange-ccxt-ultra")

# Initialize ONLY reliable exchanges (public APIs only)  
EXCHANGES = {
    'binance': ccxt.binance(),      # ⭐ EXCELLENT: 3,817 markets, 326ms
    'kraken': ccxt.kraken(),        # ⭐ EXCELLENT: 1,156 markets, 341ms  
    'bitfinex': ccxt.bitfinex(),    # ⭐ GOOD: 376 markets, 275ms
    'kucoin': ccxt.kucoin(),        # ⭐ GOOD: 1,295 markets, 277ms
    'mexc': ccxt.mexc(),            # ⭐ ACCEPTABLE: 2,994 markets, 833ms
}

# REMOVED PROBLEMATIC EXCHANGES:
# - coinbase: fetchStatus() not supported + NoneType errors
# - bybit: fetchStatus() not supported  
# - huobi: API errors
# - gateio: fetchStatus() not supported
# - okx: Too slow (49+ seconds response time)

# Set all exchanges to sandbox=False and enable rate limiting
for exchange in EXCHANGES.values():
    exchange.sandbox = False
    exchange.rateLimit = 1200

# Arbitrage and liquidity thresholds
MIN_ARBITRAGE_PROFIT_PCT = 0.1       # Minimum 0.1% profit for arbitrage
LOW_LIQUIDITY_USD = 100_000          # Less than $100k = low liquidity warning

# Common timeframes supported by most exchanges
TIMEFRAMES = {
    '1m': '1 minute',
    '3m': '3 minutes', 
    '5m': '5 minutes',
    '15m': '15 minutes',
    '30m': '30 minutes',
    '1h': '1 hour',
    '2h': '2 hours',
    '4h': '4 hours',
    '6h': '6 hours',
    '8h': '8 hours',
    '12h': '12 hours',
    '1d': '1 day',
    '3d': '3 days',
    '1w': '1 week',
    '1M': '1 month'
}

def safe_get_price_data(exchange, symbol):
    """Safely get price data from exchange with error handling"""
    try:
        ticker = exchange.fetch_ticker(symbol)
        return {
            'price': ticker.get('last'),
            'bid': ticker.get('bid'),
            'ask': ticker.get('ask'),
            'volume_24h': ticker.get('baseVolume'),
            'change_24h': ticker.get('percentage'),
            'timestamp': ticker.get('timestamp')
        }
    except Exception as e:
        return {'error': str(e)}

def safe_get_orderbook(exchange, symbol, limit=20):
    """Safely get orderbook data with error handling"""
    try:
        orderbook = exchange.fetch_order_book(symbol, limit)
        return {
            'bids': orderbook.get('bids', [])[:limit],
            'asks': orderbook.get('asks', [])[:limit],
            'timestamp': orderbook.get('timestamp')
        }
    except Exception as e:
        return {'error': str(e)}

def calculate_liquidity_metrics(orderbook_data):
    """Calculate liquidity metrics from orderbook"""
    if 'error' in orderbook_data:
        return {'error': orderbook_data['error']}
    
    bids = orderbook_data.get('bids', [])
    asks = orderbook_data.get('asks', [])
    
    if not bids or not asks:
        return {'error': 'Empty orderbook'}
    
    # Calculate metrics
    best_bid = bids[0][0] if bids else 0
    best_ask = asks[0][0] if asks else 0
    spread = best_ask - best_bid if best_bid and best_ask else 0
    spread_pct = (spread / best_ask * 100) if best_ask else 0
    
    total_bid_volume = sum([bid[1] for bid in bids])
    total_ask_volume = sum([ask[1] for ask in asks])
    
    return {
        'best_bid': best_bid,
        'best_ask': best_ask,
        'spread_usd': round(spread, 2),
        'spread_percentage': round(spread_pct, 4),
        'total_bid_volume': round(total_bid_volume, 5),
        'total_ask_volume': round(total_ask_volume, 5),
        'bid_ask_ratio': round(total_bid_volume / total_ask_volume, 3) if total_ask_volume else 0,
        'top5_bid_depth': round(sum([bid[1] for bid in bids[:5]]), 5),
        'top5_ask_depth': round(sum([ask[1] for ask in asks[:5]]), 5),
        'liquidity_score': round((total_bid_volume + total_ask_volume) / 2, 2)
    }

@mcp.tool()
def get_exchange_prices(symbol: str = "BTC/USDT", exchanges: List[str] = None) -> dict:
    """
    Get current prices from reliable exchanges only.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC/USDT", "ETH/USDT")
        exchanges: List of exchanges to query (default: all reliable ones)
    
    Returns:
        Dictionary with prices from each exchange and aggregated data
    """
    if exchanges is None:
        exchanges = list(EXCHANGES.keys())
    
    # Filter to only available exchanges
    exchanges = [ex for ex in exchanges if ex in EXCHANGES]
    
    results = {}
    errors = []
    
    for exchange_name in exchanges:
        exchange = EXCHANGES[exchange_name]
        try:
            price_data = safe_get_price_data(exchange, symbol)
            if 'error' not in price_data:
                results[exchange_name] = price_data
            else:
                errors.append(f"{exchange_name}: {price_data['error']}")
        except Exception as e:
            errors.append(f"{exchange_name}: {str(e)}")
    
    return {
        'symbol': symbol,
        'exchanges': results,
        'errors': errors if errors else None,
        'total_exchanges': len(results),
        'status': 'success'
    }

@mcp.tool()
def get_arbitrage_opportunities(symbol: str = "BTC/USDT") -> dict:
    """
    Detect arbitrage opportunities across reliable exchanges.
    
    Args:
        symbol: Trading pair symbol to analyze
    
    Returns:
        Arbitrage opportunities with profit calculations
    """
    try:
        results = {}
        prices = []
        
        for exchange_name, exchange in EXCHANGES.items():
            try:
                price_data = safe_get_price_data(exchange, symbol)
                if 'error' not in price_data and price_data.get('price'):
                    results[exchange_name] = price_data
                    prices.append((exchange_name, price_data['price']))
            except Exception as e:
                continue
        
        if len(prices) < 2:
            return {
                'symbol': symbol,
                'error': 'Not enough exchanges with valid data for arbitrage analysis',
                'status': 'error'
            }
        
        # Find arbitrage opportunities
        prices.sort(key=lambda x: x[1])  # Sort by price
        lowest_exchange, lowest_price = prices[0]
        highest_exchange, highest_price = prices[-1]
        
        profit_usd = highest_price - lowest_price
        profit_percentage = (profit_usd / lowest_price) * 100
        
        opportunities = []
        if profit_percentage > MIN_ARBITRAGE_PROFIT_PCT:
            opportunities.append({
                'buy_exchange': lowest_exchange,
                'sell_exchange': highest_exchange,
                'buy_price': lowest_price,
                'sell_price': highest_price,
                'profit_usd': round(profit_usd, 2),
                'profit_percentage': round(profit_percentage, 4)
            })
        
        return {
            'symbol': symbol,
            'opportunities': opportunities,
            'total_opportunities': len(opportunities),
            'exchanges_analyzed': len(prices),
            'price_range': {
                'lowest': {'exchange': lowest_exchange, 'price': lowest_price},
                'highest': {'exchange': highest_exchange, 'price': highest_price}
            },
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'error': f'Arbitrage analysis failed: {str(e)}',
            'status': 'error'
        }

@mcp.tool()
def get_orderbook_data(symbol: str = "BTC/USDT", exchange: str = "binance", limit: int = 20) -> dict:
    """
    Get order book data from a reliable exchange with comprehensive analysis.
    
    Args:
        symbol: Trading pair symbol
        exchange: Exchange name (must be in reliable list)
        limit: Number of bid/ask levels to retrieve
    
    Returns:
        Order book data with liquidity analysis
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    exchange_obj = EXCHANGES[exchange]
    
    try:
        orderbook_data = safe_get_orderbook(exchange_obj, symbol, limit)
        
        if 'error' in orderbook_data:
            return {
                'symbol': symbol,
                'exchange': exchange,
                'error': orderbook_data['error'],
                'status': 'error'
            }
        
        analysis = calculate_liquidity_metrics(orderbook_data)
        
        return {
            'symbol': symbol,
            'exchange': exchange,
            'orderbook': orderbook_data,
            'analysis': analysis,
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def get_exchange_volume(symbol: str = "BTC/USDT", exchanges: List[str] = None) -> dict:
    """
    Get 24h volume comparison across reliable exchanges.
    
    Args:
        symbol: Trading pair symbol
        exchanges: List of exchanges to compare
    
    Returns:
        Volume comparison with market share analysis
    """
    if exchanges is None:
        exchanges = list(EXCHANGES.keys())
    
    exchanges = [ex for ex in exchanges if ex in EXCHANGES]
    
    results = {}
    errors = []
    total_volume_usd = 0
    total_volume_base = 0
    
    for exchange_name in exchanges:
        exchange = EXCHANGES[exchange_name]
        try:
            price_data = safe_get_price_data(exchange, symbol)
            if 'error' not in price_data and price_data.get('price') and price_data.get('volume_24h'):
                volume_base = price_data['volume_24h']
                volume_usd = volume_base * price_data['price']
                
                results[exchange_name] = {
                    'volume_base': volume_base,
                    'volume_quote': volume_usd,
                    'volume_usd': volume_usd,
                    'price': price_data['price'],
                    'trades_count': 0,  # Not available in ticker
                    'market_share_pct': 0  # Will be calculated later
                }
                
                total_volume_usd += volume_usd
                total_volume_base += volume_base
            else:
                error_msg = price_data.get('error', 'No volume data available')
                errors.append(f"{exchange_name}: {error_msg}")
        except Exception as e:
            errors.append(f"{exchange_name}: {str(e)}")
    
    # Calculate market share
    for exchange_name in results:
        if total_volume_usd > 0:
            market_share = (results[exchange_name]['volume_usd'] / total_volume_usd) * 100
            results[exchange_name]['market_share_pct'] = round(market_share, 2)
    
    # Create rankings
    rankings = []
    for exchange_name, data in results.items():
        rankings.append({
            'exchange': exchange_name,
            'volume_usd': round(data['volume_usd'], 2),
            'market_share': f"{data['market_share_pct']}%"
        })
    rankings.sort(key=lambda x: x['volume_usd'], reverse=True)
    
    leading_exchange = rankings[0]['exchange'] if rankings else None
    
    return {
        'symbol': symbol,
        'volume_analysis': {
            'total_volume_usd': round(total_volume_usd, 2),
            'total_volume_base': round(total_volume_base, 4),
            'leading_exchange': leading_exchange,
            'exchange_count': len(results)
        },
        'exchanges': results,
        'rankings': rankings,
        'errors': errors if errors else None,
        'status': 'success'
    }

@mcp.tool()
def get_trading_pairs(exchange: str = "binance") -> dict:
    """
    Get all available trading pairs for a reliable exchange.
    
    Args:
        exchange: Exchange name
    
    Returns:
        List of all trading pairs organized by quote currency
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        markets = exchange_obj.load_markets()
        
        # Organize pairs by quote currency
        pairs_by_quote = {}
        for symbol, market in markets.items():
            if market.get('active', True):  # Only active markets
                quote = market.get('quote', 'OTHER')
                if quote not in pairs_by_quote:
                    pairs_by_quote[quote] = []
                pairs_by_quote[quote].append(symbol)
        
        # Sort pairs within each quote currency
        for quote in pairs_by_quote:
            pairs_by_quote[quote].sort()
        
        # Get top base currencies
        base_currencies = {}
        for symbol, market in markets.items():
            if market.get('active', True):
                base = market.get('base', 'UNKNOWN')
                base_currencies[base] = base_currencies.get(base, 0) + 1
        
        top_base_currencies = dict(sorted(base_currencies.items(), key=lambda x: x[1], reverse=True)[:20])
        
        # Sample major pairs
        major_quotes = ['USDT', 'BTC', 'ETH', 'USD']
        sample_pairs = []
        for quote in major_quotes:
            if quote in pairs_by_quote:
                sample_pairs.extend(pairs_by_quote[quote][:20])
        
        return {
            'exchange': exchange,
            'total_pairs': len([m for m in markets.values() if m.get('active', True)]),
            'pairs_by_quote': pairs_by_quote,
            'top_base_currencies': top_base_currencies,
            'sample_major_pairs': sample_pairs[:20],
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def compare_exchange_prices(symbol: str = "BTC/USDT") -> dict:
    """
    Compare prices across all reliable exchanges with detailed analysis.
    
    Args:
        symbol: Trading pair symbol to compare
    
    Returns:
        Comprehensive price comparison and arbitrage analysis
    """
    try:
        results = {}
        prices = []
        
        for exchange_name, exchange in EXCHANGES.items():
            try:
                price_data = safe_get_price_data(exchange, symbol)
                if 'error' not in price_data and price_data.get('price'):
                    results[exchange_name] = price_data
                    prices.append(price_data['price'])
            except Exception as e:
                results[exchange_name] = {'error': str(e)}
        
        if len(prices) < 2:
            return {
                'symbol': symbol,
                'error': 'Not enough exchanges with valid data for comparison',
                'status': 'error'
            }
        
        # Calculate statistics
        avg_price = np.mean(prices)
        min_price = min(prices)
        max_price = max(prices)
        price_spread = max_price - min_price
        spread_percentage = (price_spread / avg_price) * 100
        
        # Find best exchanges
        best_buy = min(results.items(), key=lambda x: x[1].get('price', float('inf')) if 'error' not in x[1] else float('inf'))
        best_sell = max(results.items(), key=lambda x: x[1].get('price', 0) if 'error' not in x[1] else 0)
        
        return {
            'symbol': symbol,
            'exchanges': results,
            'analysis': {
                'average_price': round(avg_price, 2),
                'min_price': min_price,
                'max_price': max_price,
                'price_spread_usd': round(price_spread, 2),
                'spread_percentage': round(spread_percentage, 4),
                'best_buy_exchange': best_buy[0],
                'best_sell_exchange': best_sell[0],
                'arbitrage_opportunity': round(spread_percentage, 4) > MIN_ARBITRAGE_PROFIT_PCT
            },
            'exchanges_count': len([r for r in results.values() if 'error' not in r]),
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'error': f'Price comparison failed: {str(e)}',
            'status': 'error'
        }

@mcp.tool()
def get_exchange_status(random_string: str = "test") -> dict:
    """
    Check operational status of reliable exchanges only.
    
    Returns:
        Status information for each reliable exchange
    """
    status_results = {}
    
    for exchange_name, exchange in EXCHANGES.items():
        start_time = time.time()
        try:
            # Try to fetch markets to test connectivity
            markets = exchange.load_markets()
            response_time = time.time() - start_time
            
            status_results[exchange_name] = {
                'status': 'operational',
                'response_time_seconds': round(response_time, 3),
                'total_markets': len(markets),
                'api_version': getattr(exchange, 'version', None),
                'rate_limit': exchange.rateLimit,
                'last_check': datetime.now().isoformat()
            }
        except Exception as e:
            response_time = time.time() - start_time
            status_results[exchange_name] = {
                'status': 'error',
                'error': str(e),
                'response_time_seconds': round(response_time, 3),
                'last_check': datetime.now().isoformat()
            }
    
    # Calculate summary
    operational = sum(1 for status in status_results.values() if status['status'] == 'operational')
    total = len(status_results)
    
    # Find fastest exchange
    fastest_exchange = None
    fastest_time = float('inf')
    for name, status in status_results.items():
        if status['status'] == 'operational' and status['response_time_seconds'] < fastest_time:
            fastest_time = status['response_time_seconds']
            fastest_exchange = name
    
    return {
        'exchange_status': status_results,
        'summary': {
            'total_exchanges': total,
            'operational': operational,
            'offline': total - operational,
            'uptime_percentage': round((operational / total) * 100, 1)
        },
        'fastest_exchange': fastest_exchange,
        'status': 'success'
    }

@mcp.tool()
def fetch_ohlcv_data(timeframe: str = "1h", exchange: str = "binance", symbol: str = "BTC/USDT", 
                     since_hours_ago: int = 24, limit: int = 100) -> dict:
    """
    Fetch OHLCV (candlestick) data for technical analysis.
    
    Args:
        timeframe: Timeframe for candles (1m, 5m, 15m, 1h, 4h, 1d, etc.)
        exchange: Exchange name
        symbol: Trading pair symbol
        since_hours_ago: Hours back from now to start fetching
        limit: Maximum number of candles to fetch
    
    Returns:
        OHLCV data with summary statistics
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    if timeframe not in TIMEFRAMES:
        return {
            'error': f'Timeframe {timeframe} not supported. Available: {list(TIMEFRAMES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        
        # Calculate since timestamp
        since_timestamp = int((datetime.now() - timedelta(hours=since_hours_ago)).timestamp() * 1000)
        
        # Fetch OHLCV data
        ohlcv = exchange_obj.fetch_ohlcv(symbol, timeframe, since_timestamp, limit)
        
        if not ohlcv:
            return {
                'symbol': symbol,
                'exchange': exchange,
                'error': 'No OHLCV data available',
                'status': 'error'
            }
        
        # Convert to readable format
        candles = []
        for candle in ohlcv:
            candles.append({
                'timestamp': candle[0],
                'datetime': datetime.fromtimestamp(candle[0] / 1000).strftime('%Y-%m-%dT%H:%M:%S'),
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5]
            })
        
        # Calculate summary statistics
        if len(candles) >= 2:
            first_price = candles[0]['open']
            last_price = candles[-1]['close']
            price_change = last_price - first_price
            price_change_pct = (price_change / first_price) * 100
            
            high_prices = [c['high'] for c in candles]
            low_prices = [c['low'] for c in candles]
            volumes = [c['volume'] for c in candles]
            
            summary = {
                'total_candles': len(candles),
                'period_start': candles[0]['datetime'],
                'period_end': candles[-1]['datetime'],
                'current_price': last_price,
                'price_change': round(price_change, 2),
                'price_change_percentage': round(price_change_pct, 2),
                'highest_price': max(high_prices),
                'lowest_price': min(low_prices),
                'average_volume': round(np.mean(volumes), 2),
                'total_volume': round(sum(volumes), 2)
            }
        else:
            summary = {'total_candles': len(candles)}
        
        return {
            'symbol': symbol,
            'exchange': exchange,
            'timeframe': timeframe,
            'timeframe_description': TIMEFRAMES[timeframe],
            'candles': candles,
            'summary': summary,
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'exchange': exchange,
            'timeframe': timeframe,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def fetch_multiple_timeframes(exchange: str = "binance", symbol: str = "BTC/USDT", 
                             timeframes: List[str] = None) -> dict:
    """
    Fetch OHLCV data for multiple timeframes for comprehensive analysis.
    
    Args:
        exchange: Exchange name
        symbol: Trading pair symbol
        timeframes: List of timeframes to fetch
    
    Returns:
        OHLCV data for multiple timeframes
    """
    if timeframes is None:
        timeframes = ['5m', '15m', '1h', '4h', '1d']
    
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        results = {}
        
        for timeframe in timeframes:
            if timeframe not in TIMEFRAMES:
                continue
                
            try:
                # Fetch last 100 candles for each timeframe
                ohlcv = exchange_obj.fetch_ohlcv(symbol, timeframe, None, 100)
                
                if ohlcv:
                    # Get latest candle info
                    latest = ohlcv[-1]
                    first = ohlcv[0]
                    
                    # Calculate period analysis
                    price_change = latest[4] - first[1]  # close - open
                    price_change_pct = (price_change / first[1]) * 100
                    
                    high_prices = [c[2] for c in ohlcv]
                    low_prices = [c[3] for c in ohlcv]
                    volumes = [c[5] for c in ohlcv]
                    
                    results[timeframe] = {
                        'timeframe_description': TIMEFRAMES[timeframe],
                        'candles_count': len(ohlcv),
                        'latest_candle': {
                            'datetime': datetime.fromtimestamp(latest[0] / 1000).strftime('%Y-%m-%dT%H:%M:%S'),
                            'open': latest[1],
                            'high': latest[2],
                            'low': latest[3],
                            'close': latest[4],
                            'volume': latest[5]
                        },
                        'period_analysis': {
                            'price_change': round(price_change, 2),
                            'price_change_percentage': round(price_change_pct, 2),
                            'highest': max(high_prices),
                            'lowest': min(low_prices),
                            'avg_volume': round(np.mean(volumes), 2)
                        }
                    }
            except Exception as e:
                continue
        
        return {
            'symbol': symbol,
            'exchange': exchange,
            'timeframe_analysis': results,
            'successful_timeframes': len(results),
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def fetch_recent_trades(exchange: str = "binance", symbol: str = "BTC/USDT", limit: int = 50) -> dict:
    """
    Fetch recent trades data for market microstructure analysis.
    
    Args:
        exchange: Exchange name
        symbol: Trading pair symbol
        limit: Number of recent trades to fetch
    
    Returns:
        Recent trades with market sentiment analysis
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        trades = exchange_obj.fetch_trades(symbol, None, limit)
        
        if not trades:
            return {
                'symbol': symbol,
                'exchange': exchange,
                'error': 'No trades data available',
                'status': 'error'
            }
        
        # Convert to readable format
        formatted_trades = []
        buy_volume = 0
        sell_volume = 0
        total_volume = 0
        
        for trade in trades:
            formatted_trade = {
                'id': trade.get('id'),
                'timestamp': trade.get('timestamp'),
                'datetime': datetime.fromtimestamp(trade['timestamp'] / 1000).strftime('%Y-%m-%dT%H:%M:%S.%f'),
                'price': trade.get('price'),
                'amount': trade.get('amount'),
                'side': trade.get('side'),
                'cost': trade.get('cost', trade.get('price', 0) * trade.get('amount', 0))
            }
            formatted_trades.append(formatted_trade)
            
            # Calculate volume by side
            volume = trade.get('amount', 0)
            total_volume += volume
            
            if trade.get('side') == 'buy':
                buy_volume += volume
            else:
                sell_volume += volume
        
        # Calculate market sentiment
        buy_pressure = (buy_volume / total_volume * 100) if total_volume > 0 else 0
        sell_pressure = (sell_volume / total_volume * 100) if total_volume > 0 else 0
        
        # Determine market sentiment
        if buy_pressure > 60:
            sentiment = "bullish"
        elif sell_pressure > 60:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        # Calculate price trend
        if len(formatted_trades) >= 2:
            first_price = formatted_trades[0]['price']
            last_price = formatted_trades[-1]['price']
            if last_price > first_price:
                price_trend = "bullish"
            elif last_price < first_price:
                price_trend = "bearish"
            else:
                price_trend = "neutral"
            
            price_volatility = abs(last_price - first_price) / first_price * 100
        else:
            price_trend = "neutral"
            price_volatility = 0
        
        # Calculate time span
        if len(formatted_trades) >= 2:
            time_span = (formatted_trades[-1]['timestamp'] - formatted_trades[0]['timestamp']) / 1000 / 60  # minutes
        else:
            time_span = 0
        
        analysis = {
            'total_trades': len(formatted_trades),
            'total_volume': round(total_volume, 4),
            'buy_volume': round(buy_volume, 4),
            'sell_volume': round(sell_volume, 4),
            'buy_pressure_pct': round(buy_pressure, 2),
            'sell_pressure_pct': round(sell_pressure, 2),
            'market_sentiment': sentiment,
            'price_trend': price_trend,
            'price_volatility_pct': round(price_volatility, 4),
            'latest_price': formatted_trades[-1]['price'] if formatted_trades else 0,
            'time_span_minutes': round(time_span, 1)
        }
        
        return {
            'symbol': symbol,
            'exchange': exchange,
            'trades': formatted_trades,
            'analysis': analysis,
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def get_exchange_markets_info(exchange: str = "binance") -> dict:
    """
    Get comprehensive markets information for a reliable exchange.
    
    Args:
        exchange: Exchange name
    
    Returns:
        Comprehensive market information and statistics
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        markets = exchange_obj.load_markets()
        
        # Count market types
        spot_count = 0
        futures_count = 0
        options_count = 0
        active_count = 0
        
        base_currencies = {}
        quote_currencies = {}
        
        for symbol, market in markets.items():
            if market.get('active', True):
                active_count += 1
            
            # Count market types
            if market.get('type') == 'spot':
                spot_count += 1
            elif market.get('type') in ['future', 'swap']:
                futures_count += 1
            elif market.get('type') == 'option':
                options_count += 1
            else:
                spot_count += 1  # Default to spot
            
            # Count currencies
            base = market.get('base', 'UNKNOWN')
            quote = market.get('quote', 'UNKNOWN')
            
            base_currencies[base] = base_currencies.get(base, 0) + 1
            quote_currencies[quote] = quote_currencies.get(quote, 0) + 1
        
        # Get top currencies
        top_base = dict(sorted(base_currencies.items(), key=lambda x: x[1], reverse=True)[:20])
        top_quote = dict(sorted(quote_currencies.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Get exchange capabilities
        has_capabilities = {
            'has_fetchOHLCV': getattr(exchange_obj, 'has', {}).get('fetchOHLCV', False),
            'has_fetchTrades': getattr(exchange_obj, 'has', {}).get('fetchTrades', False),
            'has_fetchOrderBook': getattr(exchange_obj, 'has', {}).get('fetchOrderBook', False),
            'has_fetchTicker': getattr(exchange_obj, 'has', {}).get('fetchTicker', False),
            'has_fetchTickers': getattr(exchange_obj, 'has', {}).get('fetchTickers', False)
        }
        
        # Get timeframes
        timeframes = getattr(exchange_obj, 'timeframes', {})
        
        # Get fees structure
        fees = getattr(exchange_obj, 'fees', {})
        trading_fees = fees.get('trading', {})
        funding_fees = fees.get('funding', {})
        
        return {
            'exchange': exchange,
            'markets_summary': {
                'total_markets': len(markets),
                'active_markets': active_count,
                'inactive_markets': len(markets) - active_count
            },
            'market_types': {
                'spot': spot_count,
                'futures': futures_count,
                'options': options_count
            },
            'currencies': {
                'base_currencies': top_base,
                'quote_currencies': top_quote,
                'total_base_currencies': len(base_currencies),
                'total_quote_currencies': len(quote_currencies)
            },
            'fees_structure': {
                'trading': trading_fees,
                'funding': funding_fees
            },
            'exchange_info': {
                **has_capabilities,
                'timeframes': timeframes,
                'rate_limit': exchange_obj.rateLimit
            },
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def get_all_tickers(exchange: str = "binance", quote_currency: str = "USDT", limit: int = 50) -> dict:
    """
    Get all tickers for a reliable exchange filtered by quote currency.
    
    Args:
        exchange: Exchange name
        quote_currency: Quote currency to filter by
        limit: Maximum number of tickers to return
    
    Returns:
        Filtered tickers with market overview
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        tickers = exchange_obj.fetch_tickers()
        
        # Filter by quote currency
        filtered_tickers = {}
        for symbol, ticker in tickers.items():
            if symbol.endswith(f'/{quote_currency}') or symbol.endswith(f':{quote_currency}'):
                if ticker.get('last') is not None:  # Only include tickers with valid price
                    filtered_tickers[symbol] = ticker
        
        # Sort by volume and limit
        sorted_tickers = dict(sorted(filtered_tickers.items(), 
                                   key=lambda x: x[1].get('quoteVolume', 0), 
                                   reverse=True)[:limit])
        
        # Calculate market overview
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for ticker in sorted_tickers.values():
            change = ticker.get('percentage', 0)
            if change > 0:
                positive_count += 1
            elif change < 0:
                negative_count += 1
            else:
                neutral_count += 1
        
        # Determine market sentiment
        total_count = len(sorted_tickers)
        if positive_count > negative_count:
            sentiment = "bullish"
        elif negative_count > positive_count:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        # Get top performers
        gainers = dict(sorted(filtered_tickers.items(), 
                            key=lambda x: x[1].get('percentage', 0), 
                            reverse=True)[:5])
        
        losers = dict(sorted(filtered_tickers.items(), 
                           key=lambda x: x[1].get('percentage', 0))[:5])
        
        return {
            'exchange': exchange,
            'quote_currency': quote_currency,
            'tickers': sorted_tickers,
            'market_overview': {
                'total_pairs': total_count,
                'positive_change': positive_count,
                'negative_change': negative_count,
                'neutral_change': neutral_count,
                'market_sentiment': sentiment
            },
            'top_performers': {
                'gainers': gainers,
                'losers': losers
            },
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def analyze_volume_patterns(exchange: str = "binance", symbol: str = "BTC/USDT", 
                           timeframe: str = "1h", periods: int = 24) -> dict:
    """
    Analyze volume patterns and anomalies.
    
    Args:
        exchange: Exchange name
        symbol: Trading pair symbol
        timeframe: Timeframe for analysis
        periods: Number of periods to analyze
    
    Returns:
        Volume pattern analysis with anomaly detection
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        ohlcv = exchange_obj.fetch_ohlcv(symbol, timeframe, None, periods)
        
        if len(ohlcv) < 10:
            return {
                'symbol': symbol,
                'exchange': exchange,
                'error': 'Not enough data for volume analysis',
                'status': 'error'
            }
        
        # Extract volume and price data
        volumes = [candle[5] for candle in ohlcv]
        closes = [candle[4] for candle in ohlcv]
        
        # Calculate volume statistics
        avg_volume = np.mean(volumes)
        max_volume = max(volumes)
        min_volume = min(volumes)
        volume_std = np.std(volumes)
        
        # Calculate volume-price correlation
        correlation = np.corrcoef(volumes, closes)[0, 1] if len(volumes) > 1 else 0
        
        # Detect volume spikes (> 2 standard deviations above mean)
        volume_spikes = []
        for i, volume in enumerate(volumes):
            if volume > avg_volume + (2 * volume_std):
                candle = ohlcv[i]
                price_change = ((candle[4] - candle[1]) / candle[1]) * 100 if candle[1] > 0 else 0
                
                volume_spikes.append({
                    'period': i,
                    'datetime': datetime.fromtimestamp(candle[0] / 1000).strftime('%Y-%m-%dT%H:%M:%S'),
                    'volume': volume,
                    'volume_ratio': round(volume / avg_volume, 2),
                    'price': candle[4],
                    'price_change': round(price_change, 2)
                })
        
        # Analyze volume trend
        if len(volumes) >= 2:
            recent_avg = np.mean(volumes[-5:])  # Last 5 periods
            earlier_avg = np.mean(volumes[:5])   # First 5 periods
            volume_trend_ratio = recent_avg / earlier_avg if earlier_avg > 0 else 1
            
            if volume_trend_ratio > 1.2:
                volume_trend = "increasing"
            elif volume_trend_ratio < 0.8:
                volume_trend = "decreasing"
            else:
                volume_trend = "stable"
        else:
            volume_trend = "insufficient_data"
            volume_trend_ratio = 1
        
        # Price-volume divergence analysis
        price_change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100 if closes[0] > 0 else 0
        volume_change_pct = ((volumes[-1] - volumes[0]) / volumes[0]) * 100 if volumes[0] > 0 else 0
        
        if price_change_pct > 2 and volume_change_pct < -10:
            divergence_signal = "bearish"  # Price up, volume down
        elif price_change_pct < -2 and volume_change_pct < -10:
            divergence_signal = "bullish"  # Price down, volume down (potential reversal)
        else:
            divergence_signal = "neutral"
        
        return {
            'symbol': symbol,
            'exchange': exchange,
            'timeframe': timeframe,
            'periods_analyzed': len(volumes),
            'volume_statistics': {
                'average_volume': round(avg_volume, 2),
                'max_volume': round(max_volume, 2),
                'min_volume': round(min_volume, 2),
                'volume_volatility': round(volume_std, 2),
                'volume_range_ratio': round(max_volume / min_volume, 2) if min_volume > 0 else 0
            },
            'volume_analysis': {
                'volume_trend': volume_trend,
                'volume_price_correlation': round(correlation, 3),
                'volume_anomalies_count': len(volume_spikes),
                'recent_vs_earlier_volume': round(volume_trend_ratio, 2)
            },
            'volume_spikes': volume_spikes,
            'price_volume_divergence': {
                'signal': divergence_signal,
                'price_change_pct': round(price_change_pct, 2),
                'volume_change_pct': round(volume_change_pct, 2)
            },
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

@mcp.tool()
def get_cross_exchange_liquidity(symbol: str = "BTC/USDT", exchanges: List[str] = None) -> dict:
    """
    Analyze liquidity across multiple reliable exchanges.
    
    Args:
        symbol: Trading pair symbol
        exchanges: List of exchanges to analyze
    
    Returns:
        Cross-exchange liquidity analysis
    """
    if exchanges is None:
        exchanges = list(EXCHANGES.keys())
    
    exchanges = [ex for ex in exchanges if ex in EXCHANGES]
    
    liquidity_data = {}
    successful_exchanges = 0
    failed_exchanges = 0
    total_liquidity = 0
    
    for exchange_name in exchanges:
        try:
            exchange_obj = EXCHANGES[exchange_name]
            
            # Get ticker for volume
            ticker = exchange_obj.fetch_ticker(symbol)
            
            # Get orderbook for liquidity
            orderbook = exchange_obj.fetch_order_book(symbol, 10)
            
            if ticker and orderbook:
                # Calculate liquidity metrics
                bids = orderbook.get('bids', [])
                asks = orderbook.get('asks', [])
                
                if bids and asks:
                    bid_liquidity = sum([bid[0] * bid[1] for bid in bids])  # Price * Volume
                    ask_liquidity = sum([ask[0] * ask[1] for ask in asks])
                    total_exchange_liquidity = bid_liquidity + ask_liquidity
                    
                    liquidity_data[exchange_name] = {
                        'price': ticker.get('last'),
                        'volume_24h': ticker.get('baseVolume'),
                        'liquidity_metrics': {
                            'bid_liquidity_usd': round(bid_liquidity, 2),
                            'ask_liquidity_usd': round(ask_liquidity, 2),
                            'total_liquidity_usd': round(total_exchange_liquidity, 2),
                            'liquidity_ratio': round(bid_liquidity / ask_liquidity, 3) if ask_liquidity > 0 else 0
                        },
                        'spread_analysis': {
                            'best_bid': bids[0][0],
                            'best_ask': asks[0][0],
                            'spread_usd': round(asks[0][0] - bids[0][0], 2),
                            'spread_percentage': round(((asks[0][0] - bids[0][0]) / asks[0][0]) * 100, 4)
                        },
                        'order_book_depth': {
                            'bid_levels': len(bids),
                            'ask_levels': len(asks),
                            'total_bid_volume': sum([bid[1] for bid in bids]),
                            'total_ask_volume': sum([ask[1] for ask in asks])
                        }
                    }
                    
                    total_liquidity += total_exchange_liquidity
                    successful_exchanges += 1
                else:
                    liquidity_data[exchange_name] = {'error': 'Empty orderbook'}
                    failed_exchanges += 1
            else:
                liquidity_data[exchange_name] = {'error': 'No ticker or orderbook data'}
                failed_exchanges += 1
                
        except Exception as e:
            liquidity_data[exchange_name] = {'error': str(e)}
            failed_exchanges += 1
    
    # Find best exchanges
    valid_exchanges = {k: v for k, v in liquidity_data.items() if 'error' not in v}
    
    if valid_exchanges:
        best_liquidity = max(valid_exchanges.items(), 
                           key=lambda x: x[1]['liquidity_metrics']['total_liquidity_usd'])
        
        best_spread = min(valid_exchanges.items(), 
                         key=lambda x: x[1]['spread_analysis']['spread_percentage'])
        
        avg_spread = np.mean([v['spread_analysis']['spread_percentage'] for v in valid_exchanges.values()])
        
        return {
            'symbol': symbol,
            'exchanges_analyzed': exchanges,
            'liquidity_data': liquidity_data,
            'cross_exchange_analysis': {
                'successful_exchanges': successful_exchanges,
                'failed_exchanges': failed_exchanges,
                'best_liquidity_exchange': best_liquidity[0],
                'best_spread_exchange': best_spread[0],
                'total_liquidity_all_exchanges': round(total_liquidity, 2),
                'average_spread_percentage': round(avg_spread, 4)
            },
            'recommendations': {
                'best_for_large_orders': best_liquidity[0],
                'best_for_tight_spreads': best_spread[0],
                'liquidity_warning': total_liquidity < LOW_LIQUIDITY_USD
            },
            'status': 'success'
        }
    else:
        return {
            'symbol': symbol,
            'exchanges_analyzed': exchanges,
            'error': 'No valid liquidity data from any exchange',
            'status': 'error'
        }

@mcp.tool()
def get_market_depth_analysis(exchange: str = "binance", symbol: str = "BTC/USDT", 
                             depth_levels: int = 50) -> dict:
    """
    Deep market microstructure analysis.
    
    Args:
        exchange: Exchange name
        symbol: Trading pair symbol
        depth_levels: Number of orderbook levels to analyze
    
    Returns:
        Comprehensive market depth analysis
    """
    if exchange not in EXCHANGES:
        return {
            'error': f'Exchange {exchange} not available. Available: {list(EXCHANGES.keys())}',
            'status': 'error'
        }
    
    try:
        exchange_obj = EXCHANGES[exchange]
        orderbook = exchange_obj.fetch_order_book(symbol, depth_levels)
        
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        if not bids or not asks:
            return {
                'symbol': symbol,
                'exchange': exchange,
                'error': 'Empty orderbook',
                'status': 'error'
            }
        
        # Calculate mid price
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2
        
        # Calculate total volumes
        total_bid_volume = sum([bid[1] for bid in bids])
        total_ask_volume = sum([ask[1] for ask in asks])
        
        # Order book imbalance
        imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)
        
        # Analyze depth at different price levels
        depth_analysis = {}
        price_levels = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0]  # Percentage levels
        
        for level_pct in price_levels:
            level_price_up = mid_price * (1 + level_pct / 100)
            level_price_down = mid_price * (1 - level_pct / 100)
            
            bid_volume_at_level = sum([bid[1] for bid in bids if bid[0] >= level_price_down])
            ask_volume_at_level = sum([ask[1] for ask in asks if ask[0] <= level_price_up])
            
            total_volume_at_level = bid_volume_at_level + ask_volume_at_level
            imbalance_at_level = (bid_volume_at_level - ask_volume_at_level) / total_volume_at_level if total_volume_at_level > 0 else 0
            
            depth_analysis[f"{level_pct}%"] = {
                'bid_volume': round(bid_volume_at_level, 4),
                'ask_volume': round(ask_volume_at_level, 4),
                'total_volume': round(total_volume_at_level, 4),
                'imbalance': round(imbalance_at_level, 3)
            }
        
        # Volume weighted average prices
        bid_vwap = sum([bid[0] * bid[1] for bid in bids]) / total_bid_volume if total_bid_volume > 0 else 0
        ask_vwap = sum([ask[0] * ask[1] for ask in asks]) / total_ask_volume if total_ask_volume > 0 else 0
        
        # Price impact analysis for different order sizes
        order_sizes = [1, 5, 10, 25, 50]  # BTC amounts
        price_impact = {}
        
        for size in order_sizes:
            # Calculate buy impact (market buy order)
            remaining_size = size
            total_cost = 0
            for ask in asks:
                if remaining_size <= 0:
                    break
                volume_to_take = min(remaining_size, ask[1])
                total_cost += volume_to_take * ask[0]
                remaining_size -= volume_to_take
            
            avg_buy_price = total_cost / size if size > 0 else 0
            buy_impact = ((avg_buy_price - mid_price) / mid_price) * 100 if mid_price > 0 else 0
            
            # Calculate sell impact (market sell order)
            remaining_size = size
            total_proceeds = 0
            for bid in bids:
                if remaining_size <= 0:
                    break
                volume_to_take = min(remaining_size, bid[1])
                total_proceeds += volume_to_take * bid[0]
                remaining_size -= volume_to_take
            
            avg_sell_price = total_proceeds / size if size > 0 else 0
            sell_impact = ((mid_price - avg_sell_price) / mid_price) * 100 if mid_price > 0 else 0
            
            price_impact[f"{size}_BTC"] = {
                'buy_impact_pct': round(buy_impact, 3),
                'sell_impact_pct': round(sell_impact, 3),
                'avg_buy_price': round(avg_buy_price, 2),
                'avg_sell_price': round(avg_sell_price, 2)
            }
        
        # Market microstructure indicators
        liquidity_score = total_bid_volume + total_ask_volume
        
        if abs(imbalance) > 0.3:
            market_balance = "bid_heavy" if imbalance > 0 else "ask_heavy"
        else:
            market_balance = "balanced"
        
        if liquidity_score > 50:
            depth_quality = "high"
        elif liquidity_score > 20:
            depth_quality = "medium"
        else:
            depth_quality = "low"
        
        return {
            'symbol': symbol,
            'exchange': exchange,
            'mid_price': round(mid_price, 2),
            'order_book_summary': {
                'total_bid_volume': round(total_bid_volume, 4),
                'total_ask_volume': round(total_ask_volume, 4),
                'order_book_imbalance': round(imbalance, 3),
                'bid_levels': len(bids),
                'ask_levels': len(asks)
            },
            'depth_by_price_level': depth_analysis,
            'volume_weighted_levels': {
                'bid_vwap': round(bid_vwap, 2),
                'ask_vwap': round(ask_vwap, 2),
                'vwap_spread': round(ask_vwap - bid_vwap, 2)
            },
            'price_impact_analysis': price_impact,
            'market_microstructure': {
                'liquidity_score': round(liquidity_score, 2),
                'market_balance': market_balance,
                'depth_quality': depth_quality
            },
            'status': 'success'
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'exchange': exchange,
            'error': str(e),
            'status': 'error'
        }

# Add health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for the optimized server"""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "status": "healthy",
        "server": "crypto-exchange-ccxt-ultra",
        "exchanges": list(EXCHANGES.keys()),
        "total_exchanges": len(EXCHANGES),
        "total_tools": 16,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    mcp.run() 
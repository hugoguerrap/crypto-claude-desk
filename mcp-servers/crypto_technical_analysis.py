#!/usr/bin/env python3
"""
Crypto Technical Analysis MCP Server - CCXT Version
Advanced cryptocurrency technical analysis and indicators.
14 specialized tools with CCXT data - no API keys required.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import requests
import numpy as np
import pandas as pd
import ccxt
from fastmcp import FastMCP

from validators import validate_symbol, validate_positive_int

# Initialize FastMCP server
mcp = FastMCP("Crypto Technical Analysis CCXT")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CCXT exchanges for data fetching (reliable ones)
EXCHANGES = {
    'binance': ccxt.binance(),
    'kraken': ccxt.kraken(),
    'bitfinex': ccxt.bitfinex(),
    'kucoin': ccxt.kucoin()
}

# Fallback data sources
DATA_SOURCES = {
    'coingecko': 'https://api.coingecko.com/api/v3/coins/{}/ohlc?vs_currency=usd&days={}',
}

def safe_fetch_ohlcv_data(symbol: str, days: int = 100, timeframe: str = '1d') -> Optional[pd.DataFrame]:
    """Fetch OHLCV data using CCXT exchanges with CoinGecko fallback"""
    try:
        # First try CCXT exchanges
        symbol_ccxt = f"{symbol.upper()}/USDT"
        
        for exchange_name, exchange in EXCHANGES.items():
            try:
                logger.info(f"Trying {exchange_name} for {symbol_ccxt}")
                
                # Calculate since timestamp (days ago)
                since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
                
                # Fetch OHLCV data
                ohlcv = exchange.fetch_ohlcv(symbol_ccxt, timeframe, since=since, limit=days)
                
                if ohlcv and len(ohlcv) > 10:
                    # Convert to DataFrame
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    
                    # Ensure all numeric columns are float
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    # Remove any NaN rows
                    df = df.dropna()
                    
                    if len(df) >= 10:
                        logger.info(f"Successfully fetched {len(df)} candles from {exchange_name}")
                        return df
                        
            except Exception as e:
                logger.warning(f"Failed to fetch from {exchange_name}: {str(e)}")
                continue
        
        # Fallback to CoinGecko if CCXT fails
        logger.info("CCXT failed, trying CoinGecko fallback")
        return fetch_coingecko_fallback(symbol, days)
        
    except Exception as e:
        logger.error(f"Error in safe_fetch_ohlcv_data: {str(e)}")
        return None

def fetch_coingecko_fallback(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Fallback to CoinGecko for OHLCV data"""
    try:
        # CoinGecko format: BTC -> bitcoin
        coin_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'ADA': 'cardano',
            'SOL': 'solana', 'DOT': 'polkadot', 'LINK': 'chainlink',
            'MATIC': 'matic-network', 'DOGE': 'dogecoin', 'AVAX': 'avalanche-2',
            'ATOM': 'cosmos', 'XRP': 'ripple', 'LTC': 'litecoin'
        }
        coin_id = coin_map.get(symbol.upper(), symbol.lower())
        url = DATA_SOURCES['coingecko'].format(coin_id, min(days, 180))
        
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                # CoinGecko returns [timestamp, open, high, low, close]
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['volume'] = 1000000  # Default volume for calculations
                df = df.sort_values('timestamp').reset_index(drop=True)
                
                # Ensure all numeric columns are float
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Remove any NaN rows
                df = df.dropna()
                
                if len(df) > 10:
                    return df
                    
        # Final fallback to simple price data
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if 'prices' in data and len(data['prices']) > 0:
                prices = data['prices']
                volumes = data.get('total_volumes', [[p[0], 1000000] for p in prices])
                
                df = pd.DataFrame(prices, columns=['timestamp', 'close'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['volume'] = [v[1] if len(v) > 1 else 1000000 for v in volumes[:len(df)]]
                
                # Create OHLC from close prices (approximation)
                df['open'] = df['close'].shift(1).fillna(df['close'])
                df['high'] = df[['open', 'close']].max(axis=1) * 1.001  # Small variation
                df['low'] = df[['open', 'close']].min(axis=1) * 0.999   # Small variation
                
                # Ensure all numeric columns are float
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                df = df.dropna()
                
                if len(df) > 10:
                    return df
                    
    except Exception as e:
        logger.error(f"CoinGecko fallback failed: {str(e)}")
        
    return None

@mcp.tool()
def calculate_rsi(symbol: str = "BTC", period: int = 14, days: int = 100) -> Dict[str, Any]:
    """
    Calculate Relative Strength Index (RSI) for cryptocurrency
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH, etc.)
        period: RSI calculation period (default 14)
        days: Historical data days to fetch
        
    Returns:
        RSI values with overbought/oversold signals
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < period + 1:
            return {"error": f"Insufficient data for {symbol}. Need at least {period + 1} data points."}
            
        close_prices = df['close'].astype(float)
        
        # Calculate price changes
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Calculate RSI
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = float(rsi.iloc[-1])
        
        # Determine signal
        if current_rsi > 70:
            signal = "OVERBOUGHT"
        elif current_rsi < 30:
            signal = "OVERSOLD"
        elif current_rsi > 50:
            signal = "BULLISH"
        else:
            signal = "BEARISH"
            
        # RSI trend
        recent_rsi = rsi.tail(5).dropna()
        rsi_trend = "FLAT"
        if len(recent_rsi) >= 3:
            if recent_rsi.iloc[-1] > recent_rsi.iloc[-3]:
                rsi_trend = "RISING"
            elif recent_rsi.iloc[-1] < recent_rsi.iloc[-3]:
                rsi_trend = "FALLING"
        
        return {
            "symbol": symbol,
            "current_rsi": round(current_rsi, 2),
            "rsi_signal": signal,
            "period": period,
            "overbought_threshold": 70,
            "oversold_threshold": 30,
            "rsi_trend": rsi_trend,
            "recent_rsi_values": [round(x, 2) for x in recent_rsi.tail(5).tolist()],
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("RSI calculation failed")
        return {"error": f"RSI calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def calculate_macd(symbol: str = "BTC", fast: int = 12, slow: int = 26, signal: int = 9, days: int = 100) -> Dict[str, Any]:
    """
    Calculate MACD (Moving Average Convergence Divergence) indicator
    
    Args:
        symbol: Cryptocurrency symbol
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line EMA period (default 9)
        days: Historical data days
        
    Returns:
        MACD values with buy/sell signals
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < slow + signal:
            return {"error": f"Insufficient data for {symbol}. Need at least {slow + signal} data points."}
            
        close_prices = df['close'].astype(float)
        
        # Calculate EMAs
        ema_fast = close_prices.ewm(span=fast).mean()
        ema_slow = close_prices.ewm(span=slow).mean()
        
        # Calculate MACD line
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line
        signal_line = macd_line.ewm(span=signal).mean()
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        current_macd = float(macd_line.iloc[-1])
        current_signal = float(signal_line.iloc[-1])
        current_histogram = float(histogram.iloc[-1])
        
        # Determine signals
        if current_macd > current_signal:
            macd_signal = "BULLISH"
        else:
            macd_signal = "BEARISH"
            
        # Check for crossovers
        crossover_signal = "NONE"
        if len(histogram) >= 2:
            if histogram.iloc[-2] < 0 and current_histogram > 0:
                crossover_signal = "BULLISH_CROSSOVER"
            elif histogram.iloc[-2] > 0 and current_histogram < 0:
                crossover_signal = "BEARISH_CROSSOVER"
        
        # Histogram trend
        histogram_trend = "FLAT"
        if len(histogram) >= 3:
            if current_histogram > histogram.iloc[-3]:
                histogram_trend = "RISING"
            elif current_histogram < histogram.iloc[-3]:
                histogram_trend = "FALLING"
        
        return {
            "symbol": symbol,
            "macd_line": round(current_macd, 6),
            "signal_line": round(current_signal, 6),
            "histogram": round(current_histogram, 6),
            "macd_signal": macd_signal,
            "crossover_signal": crossover_signal,
            "parameters": {"fast": fast, "slow": slow, "signal": signal},
            "histogram_trend": histogram_trend,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("MACD calculation failed")
        return {"error": f"MACD calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def calculate_bollinger_bands(symbol: str = "BTC", period: int = 20, std_dev: float = 2.0, days: int = 100) -> Dict[str, Any]:
    """
    Calculate Bollinger Bands for volatility analysis
    
    Args:
        symbol: Cryptocurrency symbol
        period: Moving average period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)
        days: Historical data days
        
    Returns:
        Bollinger Bands with volatility and position analysis
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < period:
            return {"error": f"Insufficient data for {symbol}. Need at least {period} data points."}
            
        close_prices = df['close'].astype(float)
        current_price = float(close_prices.iloc[-1])
        
        # Calculate moving average (middle band)
        middle_band = close_prices.rolling(window=period).mean()
        
        # Calculate standard deviation
        std = close_prices.rolling(window=period).std()
        
        # Calculate upper and lower bands
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        current_upper = float(upper_band.iloc[-1])
        current_middle = float(middle_band.iloc[-1])
        current_lower = float(lower_band.iloc[-1])
        
        # Calculate position within bands (0-100%)
        band_width = current_upper - current_lower
        position_in_bands = ((current_price - current_lower) / band_width) * 100
        
        # Calculate band width percentage
        band_width_pct = (band_width / current_middle) * 100
        
        # Determine signal
        if current_price > current_upper:
            bb_signal = "OVERBOUGHT"
        elif current_price < current_lower:
            bb_signal = "OVERSOLD"
        elif current_price > current_middle:
            bb_signal = "BULLISH"
        else:
            bb_signal = "BEARISH"
            
        # Detect squeeze (low volatility)
        squeeze_detected = band_width_pct < 5.0
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "upper_band": round(current_upper, 2),
            "middle_band": round(current_middle, 2),
            "lower_band": round(current_lower, 2),
            "position_in_bands": round(position_in_bands, 1),
            "band_width": round(band_width, 2),
            "volatility_pct": round(band_width_pct, 2),
            "bb_signal": bb_signal,
            "parameters": {"period": period, "std_dev": std_dev},
            "squeeze_detected": squeeze_detected,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Bollinger Bands calculation failed")
        return {"error": f"Bollinger Bands calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def detect_chart_patterns(symbol: str = "BTC", days: int = 60) -> Dict[str, Any]:
    """
    Detect common chart patterns using price analysis
    
    Args:
        symbol: Cryptocurrency symbol
        days: Days of historical data to analyze
        
    Returns:
        Detected patterns with confidence levels
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < 20:
            return {"error": f"Insufficient data for {symbol}. Need at least 20 data points."}
            
        close_prices = df['close'].astype(float)
        high_prices = df['high'].astype(float)
        low_prices = df['low'].astype(float)
        
        patterns_detected = []
        current_price = float(close_prices.iloc[-1])
        
        # Simple pattern detection algorithms
        
        # 1. Double Top/Bottom Detection
        peaks = []
        troughs = []
        
        for i in range(5, len(high_prices) - 5):
            # Peak detection
            if (high_prices.iloc[i] > high_prices.iloc[i-5:i].max() and 
                high_prices.iloc[i] > high_prices.iloc[i+1:i+6].max()):
                peaks.append((i, high_prices.iloc[i]))
                
            # Trough detection  
            if (low_prices.iloc[i] < low_prices.iloc[i-5:i].min() and
                low_prices.iloc[i] < low_prices.iloc[i+1:i+6].min()):
                troughs.append((i, low_prices.iloc[i]))
        
        # Check for double tops
        if len(peaks) >= 2:
            last_two_peaks = peaks[-2:]
            price_diff = abs(last_two_peaks[0][1] - last_two_peaks[1][1])
            if price_diff < last_two_peaks[0][1] * 0.03:  # Within 3%
                patterns_detected.append({
                    "pattern": "DOUBLE_TOP",
                    "confidence": "MEDIUM",
                    "signal": "BEARISH",
                    "description": "Two peaks at similar levels detected"
                })
        
        # Check for double bottoms
        if len(troughs) >= 2:
            last_two_troughs = troughs[-2:]
            price_diff = abs(last_two_troughs[0][1] - last_two_troughs[1][1])
            if price_diff < last_two_troughs[0][1] * 0.03:  # Within 3%
                patterns_detected.append({
                    "pattern": "DOUBLE_BOTTOM",
                    "confidence": "MEDIUM", 
                    "signal": "BULLISH",
                    "description": "Two troughs at similar levels detected"
                })
        
        # 2. Triangle Patterns (simplified)
        recent_highs = high_prices.tail(20)
        recent_lows = low_prices.tail(20)
        
        # Descending triangle (lower highs, horizontal support)
        if len(recent_highs) >= 10:
            high_slope = np.polyfit(range(len(recent_highs)), recent_highs, 1)[0]
            low_variance = recent_lows.var()
            
            if high_slope < 0 and low_variance < (recent_lows.mean() * 0.01) ** 2:
                patterns_detected.append({
                    "pattern": "DESCENDING_TRIANGLE",
                    "confidence": "LOW",
                    "signal": "BEARISH",
                    "description": "Lower highs with horizontal support"
                })
        
        # 3. Head and Shoulders (very simplified)
        if len(peaks) >= 3:
            last_three_peaks = peaks[-3:]
            if (last_three_peaks[1][1] > last_three_peaks[0][1] and 
                last_three_peaks[1][1] > last_three_peaks[2][1]):
                patterns_detected.append({
                    "pattern": "HEAD_AND_SHOULDERS",
                    "confidence": "LOW",
                    "signal": "BEARISH", 
                    "description": "Potential head and shoulders pattern"
                })
        
        # Calculate key levels
        support_level = low_prices.tail(20).min()
        resistance_level = high_prices.tail(20).max()
        
        # Determine price position
        if current_price < support_level * 1.02:
            price_position = "AT_SUPPORT"
        elif current_price > resistance_level * 0.98:
            price_position = "AT_RESISTANCE"
        elif current_price < (support_level + resistance_level) / 2:
            price_position = "BELOW_SUPPORT"
        else:
            price_position = "ABOVE_SUPPORT"
        
        return {
            "symbol": symbol,
            "patterns_detected": patterns_detected,
            "total_patterns": len(patterns_detected),
            "current_price": current_price,
            "key_levels": {
                "support": round(float(support_level), 2),
                "resistance": round(float(resistance_level), 2),
                "price_position": price_position
            },
            "analysis_period_days": days,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Chart pattern detection failed")
        return {"error": f"Chart pattern detection failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def calculate_moving_averages(symbol: str = "BTC", periods: List[int] = None, days: int = 250) -> Dict[str, Any]:
    """
    Calculate multiple moving averages and trend analysis

    Args:
        symbol: Cryptocurrency symbol
        periods: List of MA periods to calculate (default [20, 50, 200])
        days: Historical data days

    Returns:
        Moving averages with trend and crossover analysis
    """
    if periods is None:
        periods = [20, 50, 200]
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < max(periods):
            return {"error": f"Insufficient data for {symbol}. Need at least {max(periods)} data points."}
            
        close_prices = df['close'].astype(float)
        current_price = float(close_prices.iloc[-1])
        
        ma_results = {}
        crossover_signals = []
        
        # Calculate each moving average
        for period in periods:
            if len(close_prices) >= period:
                ma = close_prices.rolling(window=period).mean()
                current_ma = float(ma.iloc[-1])
                
                # Trend analysis
                ma_trend = "FLAT"
                if len(ma) >= 5:
                    recent_ma = ma.tail(5).values
                    slope = np.polyfit(range(len(recent_ma)), recent_ma, 1)[0]
                    if slope > current_ma * 0.001:
                        ma_trend = "RISING"
                    elif slope < -current_ma * 0.001:
                        ma_trend = "FALLING"
                
                ma_results[f"MA{period}"] = {
                    "value": round(current_ma, 2),
                    "trend": ma_trend,
                    "price_above": current_price > current_ma,
                    "distance_pct": round((current_price - current_ma) / current_ma * 100, 2)
                }
        
        # Check for crossovers between MAs
        sorted_periods = sorted(periods)
        for i in range(len(sorted_periods) - 1):
            fast_period = sorted_periods[i]
            slow_period = sorted_periods[i + 1]
            
            if (f"MA{fast_period}" in ma_results and f"MA{slow_period}" in ma_results):
                fast_ma = ma_results[f"MA{fast_period}"]["value"]
                slow_ma = ma_results[f"MA{slow_period}"]["value"]
                
                if fast_ma > slow_ma:
                    crossover_signals.append({
                        "type": "BULLISH",
                        "description": f"MA{fast_period} above MA{slow_period}",
                        "strength": "STRONG" if fast_ma > slow_ma * 1.02 else "WEAK"
                    })
                else:
                    crossover_signals.append({
                        "type": "BEARISH", 
                        "description": f"MA{fast_period} below MA{slow_period}",
                        "strength": "STRONG" if fast_ma < slow_ma * 0.98 else "WEAK"
                    })
        
        # Overall trend assessment
        bullish_signals = sum(1 for signal in crossover_signals if signal["type"] == "BULLISH")
        bearish_signals = sum(1 for signal in crossover_signals if signal["type"] == "BEARISH")
        
        if bullish_signals > bearish_signals:
            overall_trend = "BULLISH"
        elif bearish_signals > bullish_signals:
            overall_trend = "BEARISH"
        else:
            overall_trend = "NEUTRAL"
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "moving_averages": ma_results,
            "crossover_signals": crossover_signals,
            "overall_trend": overall_trend,
            "periods_calculated": len(ma_results),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Moving averages calculation failed")
        return {"error": f"Moving averages calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def get_support_resistance(symbol: str = "BTC", days: int = 90) -> Dict[str, Any]:
    """
    Identify key support and resistance levels
    
    Args:
        symbol: Cryptocurrency symbol
        days: Historical data days to analyze
        
    Returns:
        Support and resistance levels with strength analysis
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < 20:
            return {"error": f"Insufficient data for {symbol}. Need at least 20 data points."}
            
        high_prices = df['high'].astype(float)
        low_prices = df['low'].astype(float)
        close_prices = df['close'].astype(float)
        current_price = float(close_prices.iloc[-1])
        
        # Find pivot points
        def find_pivots(prices, window=5):
            pivots = []
            for i in range(window, len(prices) - window):
                if all(prices.iloc[i] >= prices.iloc[i-window:i+window+1]):
                    pivots.append((i, float(prices.iloc[i]), 'HIGH'))
                elif all(prices.iloc[i] <= prices.iloc[i-window:i+window+1]):
                    pivots.append((i, float(prices.iloc[i]), 'LOW'))
            return pivots
        
        high_pivots = find_pivots(high_prices)
        low_pivots = find_pivots(low_prices)
        
        # Cluster similar price levels
        def cluster_levels(pivots, tolerance=0.02):
            if not pivots:
                return []
                
            levels = []
            pivot_prices = [p[1] for p in pivots]
            
            for price in pivot_prices:
                # Find similar prices within tolerance
                similar_prices = [p for p in pivot_prices if abs(p - price) / price < tolerance]
                
                if len(similar_prices) >= 2:  # At least 2 touches
                    avg_price = sum(similar_prices) / len(similar_prices)
                    strength = len(similar_prices)
                    
                    # Avoid duplicates
                    if not any(abs(level['price'] - avg_price) / avg_price < tolerance/2 for level in levels):
                        levels.append({
                            'price': round(avg_price, 2),
                            'strength': strength,
                            'touches': len(similar_prices)
                        })
            
            return sorted(levels, key=lambda x: x['strength'], reverse=True)
        
        resistance_levels = cluster_levels(high_pivots)
        support_levels = cluster_levels(low_pivots)
        
        # Filter levels near current price
        nearby_resistance = [r for r in resistance_levels if r['price'] > current_price]
        nearby_support = [s for s in support_levels if s['price'] < current_price]
        
        # Get closest levels
        next_resistance = min(nearby_resistance, key=lambda x: x['price']) if nearby_resistance else None
        next_support = max(nearby_support, key=lambda x: x['price']) if nearby_support else None
        
        # Calculate distances
        resistance_distance = ((next_resistance['price'] - current_price) / current_price * 100) if next_resistance else None
        support_distance = ((current_price - next_support['price']) / current_price * 100) if next_support else None
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "resistance_levels": resistance_levels[:5],  # Top 5
            "support_levels": support_levels[:5],  # Top 5
            "next_resistance": next_resistance,
            "next_support": next_support,
            "resistance_distance_pct": round(resistance_distance, 2) if resistance_distance else None,
            "support_distance_pct": round(support_distance, 2) if support_distance else None,
            "total_resistance_levels": len(resistance_levels),
            "total_support_levels": len(support_levels),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Support/Resistance calculation failed")
        return {"error": f"Support/Resistance calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def calculate_fibonacci_levels(symbol: str = "BTC", trend: str = "up", days: int = 60) -> Dict[str, Any]:
    """
    Calculate Fibonacci retracement levels
    
    Args:
        symbol: Cryptocurrency symbol
        trend: Trend direction ('up' for uptrend, 'down' for downtrend)
        days: Days to look back for high/low points
        
    Returns:
        Fibonacci retracement levels with current position
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < 10:
            return {"error": f"Insufficient data for {symbol}. Need at least 10 data points."}
            
        high_prices = df['high'].astype(float)
        low_prices = df['low'].astype(float)
        close_prices = df['close'].astype(float)
        current_price = float(close_prices.iloc[-1])
        
        # Find swing high and low
        if trend.lower() == "up":
            swing_low = float(low_prices.min())
            swing_high = float(high_prices.max())
        else:
            swing_high = float(high_prices.max())
            swing_low = float(low_prices.min())
        
        # Calculate Fibonacci levels
        price_range = swing_high - swing_low
        
        fib_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        fib_levels = {}
        
        for ratio in fib_ratios:
            if trend.lower() == "up":
                level = swing_high - (price_range * ratio)
            else:
                level = swing_low + (price_range * ratio)
                
            fib_levels[f"Fib_{ratio}"] = {
                "level": round(level, 2),
                "ratio": ratio,
                "distance_pct": round(abs(current_price - level) / current_price * 100, 2)
            }
        
        # Find current position
        current_position = "UNKNOWN"
        closest_level = None
        min_distance = float('inf')
        
        for level_name, level_data in fib_levels.items():
            distance = abs(current_price - level_data["level"])
            if distance < min_distance:
                min_distance = distance
                closest_level = level_name
                
        # Determine if price is between levels
        sorted_levels = sorted(fib_levels.items(), key=lambda x: x[1]["level"])
        
        for i in range(len(sorted_levels) - 1):
            lower_level = sorted_levels[i][1]["level"]
            upper_level = sorted_levels[i + 1][1]["level"]
            
            if lower_level <= current_price <= upper_level:
                current_position = f"Between {sorted_levels[i][0]} and {sorted_levels[i + 1][0]}"
                break
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "trend_direction": trend.upper(),
            "swing_high": round(swing_high, 2),
            "swing_low": round(swing_low, 2),
            "fibonacci_levels": fib_levels,
            "closest_level": closest_level,
            "current_position": current_position,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Fibonacci calculation failed")
        return {"error": f"Fibonacci calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def get_momentum_indicators(symbol: str = "BTC", days: int = 100) -> Dict[str, Any]:
    """
    Calculate multiple momentum indicators (Stochastic, Williams %R, etc.)
    
    Args:
        symbol: Cryptocurrency symbol  
        days: Historical data days
        
    Returns:
        Multiple momentum indicators with signals
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < 20:
            return {"error": f"Insufficient data for {symbol}. Need at least 20 data points."}
            
        high_prices = df['high'].astype(float)
        low_prices = df['low'].astype(float)
        close_prices = df['close'].astype(float)
        
        indicators = {}
        
        # 1. Stochastic Oscillator
        if len(df) >= 14:
            period = 14
            lowest_low = low_prices.rolling(window=period).min()
            highest_high = high_prices.rolling(window=period).max()
            
            k_percent = ((close_prices - lowest_low) / (highest_high - lowest_low)) * 100
            d_percent = k_percent.rolling(window=3).mean()
            
            current_k = float(k_percent.iloc[-1])
            current_d = float(d_percent.iloc[-1])
            
            # Stochastic signal
            if current_k > 80:
                stoch_signal = "OVERBOUGHT"
            elif current_k < 20:
                stoch_signal = "OVERSOLD"
            elif current_k > current_d:
                stoch_signal = "BULLISH"
            else:
                stoch_signal = "BEARISH"
            
            indicators["stochastic"] = {
                "k_percent": round(current_k, 2),
                "d_percent": round(current_d, 2),
                "signal": stoch_signal
            }
        
        # 2. Williams %R
        if len(df) >= 14:
            period = 14
            highest_high = high_prices.rolling(window=period).max()
            lowest_low = low_prices.rolling(window=period).min()
            
            williams_r = ((highest_high - close_prices) / (highest_high - lowest_low)) * -100
            current_wr = float(williams_r.iloc[-1])
            
            # Williams %R signal
            if current_wr > -20:
                wr_signal = "OVERBOUGHT"
            elif current_wr < -80:
                wr_signal = "OVERSOLD"
            elif current_wr > -50:
                wr_signal = "BULLISH"
            else:
                wr_signal = "BEARISH"
            
            indicators["williams_r"] = {
                "value": round(current_wr, 2),
                "signal": wr_signal
            }
        
        # 3. Rate of Change (ROC)
        if len(df) >= 12:
            period = 12
            roc = ((close_prices / close_prices.shift(period)) - 1) * 100
            current_roc = float(roc.iloc[-1])
            
            # ROC signal
            if current_roc > 5:
                roc_signal = "STRONG_BULLISH"
            elif current_roc > 0:
                roc_signal = "BULLISH"
            elif current_roc < -5:
                roc_signal = "STRONG_BEARISH"
            else:
                roc_signal = "BEARISH"
            
            indicators["rate_of_change"] = {
                "value": round(current_roc, 2),
                "signal": roc_signal,
                "period": period
            }
        
        # 4. Commodity Channel Index (CCI)
        if len(df) >= 20:
            period = 20
            typical_price = (high_prices + low_prices + close_prices) / 3
            sma_tp = typical_price.rolling(window=period).mean()
            mean_deviation = typical_price.rolling(window=period).apply(
                lambda x: np.mean(np.abs(x - x.mean()))
            )
            
            cci = (typical_price - sma_tp) / (0.015 * mean_deviation)
            current_cci = float(cci.iloc[-1])
            
            # CCI signal
            if current_cci > 100:
                cci_signal = "OVERBOUGHT"
            elif current_cci < -100:
                cci_signal = "OVERSOLD"
            elif current_cci > 0:
                cci_signal = "BULLISH"
            else:
                cci_signal = "BEARISH"
            
            indicators["cci"] = {
                "value": round(current_cci, 2),
                "signal": cci_signal
            }
        
        # Overall momentum assessment
        bullish_count = sum(1 for ind in indicators.values() 
                          if ind.get("signal", "").endswith("BULLISH") or ind.get("signal") == "OVERSOLD")
        bearish_count = sum(1 for ind in indicators.values() 
                          if ind.get("signal", "").endswith("BEARISH") or ind.get("signal") == "OVERBOUGHT")
        
        if bullish_count > bearish_count:
            overall_momentum = "BULLISH"
        elif bearish_count > bullish_count:
            overall_momentum = "BEARISH"
        else:
            overall_momentum = "NEUTRAL"
        
        return {
            "symbol": symbol,
            "momentum_indicators": indicators,
            "overall_momentum": overall_momentum,
            "bullish_signals": bullish_count,
            "bearish_signals": bearish_count,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Momentum indicators calculation failed")
        return {"error": f"Momentum indicators calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def analyze_volume_profile(symbol: str = "BTC", days: int = 30) -> Dict[str, Any]:
    """
    Analyze volume profile and price-volume relationships
    
    Args:
        symbol: Cryptocurrency symbol
        days: Days of data to analyze
        
    Returns:
        Volume profile analysis with high-volume zones
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < 10:
            return {"error": f"Insufficient data for {symbol}. Need at least 10 data points."}
            
        close_prices = df['close'].astype(float)
        volumes = df['volume'].astype(float)
        
        # Create price bins for volume profile
        price_min = close_prices.min()
        price_max = close_prices.max()
        num_bins = min(20, len(df) // 2)  # Adaptive number of bins
        
        price_bins = np.linspace(price_min, price_max, num_bins)
        volume_profile = []
        
        for i in range(len(price_bins) - 1):
            bin_low = price_bins[i]
            bin_high = price_bins[i + 1]
            
            # Find volumes in this price range
            mask = (close_prices >= bin_low) & (close_prices < bin_high)
            bin_volume = volumes[mask].sum()
            
            if bin_volume > 0:
                volume_profile.append({
                    "price_low": round(bin_low, 2),
                    "price_high": round(bin_high, 2),
                    "price_mid": round((bin_low + bin_high) / 2, 2),
                    "volume": round(bin_volume, 2),
                    "percentage": 0  # Will calculate after
                })
        
        # Calculate percentages
        total_volume = sum(vp["volume"] for vp in volume_profile)
        for vp in volume_profile:
            vp["percentage"] = round((vp["volume"] / total_volume) * 100, 2)
        
        # Sort by volume (highest first)
        volume_profile.sort(key=lambda x: x["volume"], reverse=True)
        
        # Identify high-volume zones (top 20% of volume)
        high_volume_zones = volume_profile[:max(1, len(volume_profile) // 5)]
        
        # Volume-Price Trend (VPT)
        vpt = [0]
        for i in range(1, len(close_prices)):
            price_change_pct = (close_prices.iloc[i] - close_prices.iloc[i-1]) / close_prices.iloc[i-1]
            vpt_change = volumes.iloc[i] * price_change_pct
            vpt.append(vpt[-1] + vpt_change)
        
        # Volume analysis
        avg_volume = volumes.mean()
        current_volume = volumes.iloc[-1]
        volume_trend = "INCREASING" if volumes.tail(5).mean() > volumes.head(-5).mean() else "DECREASING"
        
        # Price-Volume divergence
        price_change_5d = (close_prices.iloc[-1] - close_prices.iloc[-6]) / close_prices.iloc[-6] * 100
        volume_change_5d = (volumes.tail(5).mean() - volumes.head(-5).tail(5).mean()) / volumes.head(-5).tail(5).mean() * 100
        
        if price_change_5d > 2 and volume_change_5d < -10:
            divergence = "BEARISH_DIVERGENCE"
        elif price_change_5d < -2 and volume_change_5d > 10:
            divergence = "BULLISH_DIVERGENCE"
        else:
            divergence = "NO_DIVERGENCE"
        
        return {
            "symbol": symbol,
            "volume_profile": volume_profile[:10],  # Top 10 zones
            "high_volume_zones": high_volume_zones,
            "volume_analysis": {
                "average_volume": round(avg_volume, 2),
                "current_volume": round(current_volume, 2),
                "volume_trend": volume_trend,
                "volume_ratio": round(current_volume / avg_volume, 2)
            },
            "price_volume_divergence": divergence,
            "vpt_current": round(vpt[-1], 2),
            "analysis_period_days": days,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Volume profile analysis failed")
        return {"error": f"Volume profile analysis failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def detect_trend_reversals(symbol: str = "BTC", days: int = 60) -> Dict[str, Any]:
    """
    Detect potential trend reversals using multiple indicators
    
    Args:
        symbol: Cryptocurrency symbol
        days: Days of data to analyze
        
    Returns:
        Trend reversal signals with confidence levels
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < 30:
            return {"error": f"Insufficient data for {symbol}. Need at least 30 data points."}
            
        close_prices = df['close'].astype(float)
        high_prices = df['high'].astype(float)
        low_prices = df['low'].astype(float)
        volumes = df['volume'].astype(float)
        
        reversal_signals = []
        confidence_score = 0
        
        # 1. RSI Divergence
        if len(df) >= 14:
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + gain / loss))
            
            # Check for RSI divergence
            recent_prices = close_prices.tail(10)
            recent_rsi = rsi.tail(10)
            
            if (recent_prices.iloc[-1] > recent_prices.iloc[0] and 
                recent_rsi.iloc[-1] < recent_rsi.iloc[0] and 
                rsi.iloc[-1] > 70):
                reversal_signals.append("BEARISH_RSI_DIVERGENCE")
                confidence_score += 25
                
            elif (recent_prices.iloc[-1] < recent_prices.iloc[0] and 
                  recent_rsi.iloc[-1] > recent_rsi.iloc[0] and 
                  rsi.iloc[-1] < 30):
                reversal_signals.append("BULLISH_RSI_DIVERGENCE")
                confidence_score += 25
        
        # 2. Volume Confirmation
        avg_volume = volumes.tail(20).mean()
        recent_volume = volumes.tail(5).mean()
        
        if recent_volume > avg_volume * 1.5:
            reversal_signals.append("HIGH_VOLUME_CONFIRMATION")
            confidence_score += 15
        
        # 3. Support/Resistance Break
        support_level = low_prices.tail(20).min()
        resistance_level = high_prices.tail(20).max()
        current_price = close_prices.iloc[-1]
        
        if current_price < support_level * 1.01:  # Near support
            reversal_signals.append("SUPPORT_TEST")
            confidence_score += 10
        elif current_price > resistance_level * 0.99:  # Near resistance
            reversal_signals.append("RESISTANCE_TEST")
            confidence_score += 10
        
        # 4. Moving Average Convergence
        if len(df) >= 50:
            ma_20 = close_prices.rolling(window=20).mean()
            ma_50 = close_prices.rolling(window=50).mean()
            
            # Check for MA convergence (potential reversal)
            ma_distance = abs(ma_20.iloc[-1] - ma_50.iloc[-1]) / ma_50.iloc[-1] * 100
            
            if ma_distance < 2:  # MAs converging
                reversal_signals.append("MA_CONVERGENCE")
                confidence_score += 10
        
        # 5. Candlestick Patterns (simplified)
        if len(df) >= 3:
            last_3_candles = df.tail(3)
            
            # Doji pattern (open ≈ close)
            for i, row in last_3_candles.iterrows():
                body_size = abs(row['close'] - row['open']) / row['open'] * 100
                if body_size < 0.5:  # Very small body
                    reversal_signals.append("DOJI_PATTERN")
                    confidence_score += 5
                    break
            
            # Hammer/Shooting Star
            last_candle = df.iloc[-1]
            body_size = abs(last_candle['close'] - last_candle['open'])
            total_range = last_candle['high'] - last_candle['low']
            
            if total_range > 0 and body_size / total_range < 0.3:
                if last_candle['close'] > (last_candle['high'] + last_candle['low']) / 2:
                    reversal_signals.append("HAMMER_PATTERN")
                    confidence_score += 15
                else:
                    reversal_signals.append("SHOOTING_STAR_PATTERN")
                    confidence_score += 15
        
        # Determine overall reversal probability
        if confidence_score >= 50:
            reversal_probability = "HIGH"
        elif confidence_score >= 30:
            reversal_probability = "MEDIUM"
        elif confidence_score >= 15:
            reversal_probability = "LOW"
        else:
            reversal_probability = "VERY_LOW"
        
        # Determine likely direction
        bullish_signals = sum(1 for signal in reversal_signals 
                            if "BULLISH" in signal or "HAMMER" in signal or "SUPPORT" in signal)
        bearish_signals = sum(1 for signal in reversal_signals 
                            if "BEARISH" in signal or "SHOOTING" in signal or "RESISTANCE" in signal)
        
        if bullish_signals > bearish_signals:
            likely_direction = "BULLISH_REVERSAL"
        elif bearish_signals > bullish_signals:
            likely_direction = "BEARISH_REVERSAL"
        else:
            likely_direction = "UNCERTAIN"
        
        return {
            "symbol": symbol,
            "reversal_signals": reversal_signals,
            "confidence_score": confidence_score,
            "reversal_probability": reversal_probability,
            "likely_direction": likely_direction,
            "current_price": round(float(close_prices.iloc[-1]), 2),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Trend reversal detection failed")
        return {"error": f"Trend reversal detection failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def calculate_volatility(symbol: str = "BTC", period: int = 30, days: int = 100) -> Dict[str, Any]:
    """
    Calculate various volatility metrics for cryptocurrency
    
    Args:
        symbol: Cryptocurrency symbol
        period: Period for volatility calculation (default 30)
        days: Historical data days
        
    Returns:
        Comprehensive volatility analysis
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < period:
            return {"error": f"Insufficient data for {symbol}. Need at least {period} data points."}
            
        close_prices = df['close'].astype(float)
        high_prices = df['high'].astype(float)
        low_prices = df['low'].astype(float)
        
        # 1. Historical Volatility (Standard Deviation of Returns)
        returns = close_prices.pct_change().dropna()
        historical_vol = returns.rolling(window=period).std() * np.sqrt(365) * 100  # Annualized
        current_vol = float(historical_vol.iloc[-1])
        
        # 2. Average True Range (ATR)
        high_low = high_prices - low_prices
        high_close_prev = np.abs(high_prices - close_prices.shift(1))
        low_close_prev = np.abs(low_prices - close_prices.shift(1))
        
        true_range = np.maximum(high_low, np.maximum(high_close_prev, low_close_prev))
        atr = true_range.rolling(window=period).mean()
        current_atr = float(atr.iloc[-1])
        atr_pct = (current_atr / close_prices.iloc[-1]) * 100
        
        # 3. Volatility Percentile (where current vol ranks historically)
        vol_percentile = (historical_vol.iloc[-1] > historical_vol).sum() / len(historical_vol) * 100
        
        # 4. Volatility Trend
        vol_trend = "FLAT"
        if len(historical_vol) >= 10:
            recent_vol = historical_vol.tail(10).mean()
            earlier_vol = historical_vol.head(-10).tail(10).mean()
            
            if recent_vol > earlier_vol * 1.1:
                vol_trend = "INCREASING"
            elif recent_vol < earlier_vol * 0.9:
                vol_trend = "DECREASING"
        
        # 5. Volatility Classification
        if current_vol > 100:
            vol_classification = "EXTREMELY_HIGH"
        elif current_vol > 60:
            vol_classification = "HIGH"
        elif current_vol > 30:
            vol_classification = "MODERATE"
        elif current_vol > 15:
            vol_classification = "LOW"
        else:
            vol_classification = "VERY_LOW"
        
        # 6. Volatility Breakout Detection
        vol_ma = historical_vol.rolling(window=20).mean()
        vol_std = historical_vol.rolling(window=20).std()
        vol_upper = vol_ma + (2 * vol_std)
        vol_lower = vol_ma - (2 * vol_std)
        
        if current_vol > vol_upper.iloc[-1]:
            breakout_signal = "VOLATILITY_BREAKOUT_HIGH"
        elif current_vol < vol_lower.iloc[-1]:
            breakout_signal = "VOLATILITY_BREAKOUT_LOW"
        else:
            breakout_signal = "NORMAL_RANGE"
        
        # 7. Risk Assessment
        if current_vol > 80:
            risk_level = "VERY_HIGH"
        elif current_vol > 50:
            risk_level = "HIGH"
        elif current_vol > 25:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        
        return {
            "symbol": symbol,
            "current_volatility_pct": round(current_vol, 2),
            "volatility_classification": vol_classification,
            "volatility_trend": vol_trend,
            "volatility_percentile": round(vol_percentile, 1),
            "atr": {
                "value": round(current_atr, 2),
                "percentage": round(atr_pct, 2)
            },
            "breakout_signal": breakout_signal,
            "risk_level": risk_level,
            "period_days": period,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Volatility calculation failed")
        return {"error": f"Volatility calculation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def get_correlation_analysis(symbols_list: List[str] = None, days: int = 60) -> Dict[str, Any]:
    """
    Analyze correlations between multiple cryptocurrencies

    Args:
        symbols_list: List of cryptocurrency symbols to analyze (default ["BTC", "ETH", "ADA", "SOL"])
        days: Days of historical data

    Returns:
        Correlation matrix and analysis
    """
    if symbols_list is None:
        symbols_list = ["BTC", "ETH", "ADA", "SOL"]
    try:
        correlation_data = {}
        price_data = {}
        
        # Fetch data for all symbols
        for symbol in symbols_list:
            df = safe_fetch_ohlcv_data(symbol, days)
            if df is not None and len(df) > 10:
                price_data[symbol] = df['close'].astype(float)
            else:
                logger.warning(f"Insufficient data for {symbol}")
        
        if len(price_data) < 2:
            return {"error": "Need at least 2 symbols with sufficient data"}
        
        # Align data by timestamp and calculate returns
        returns_data = {}
        min_length = min(len(prices) for prices in price_data.values())
        
        for symbol, prices in price_data.items():
            # Take the last min_length data points
            aligned_prices = prices.tail(min_length).reset_index(drop=True)
            returns = aligned_prices.pct_change().dropna()
            returns_data[symbol] = returns
        
        # Calculate correlation matrix
        correlation_matrix = {}
        for symbol1 in returns_data:
            correlation_matrix[symbol1] = {}
            for symbol2 in returns_data:
                if len(returns_data[symbol1]) > 0 and len(returns_data[symbol2]) > 0:
                    corr = np.corrcoef(returns_data[symbol1], returns_data[symbol2])[0, 1]
                    correlation_matrix[symbol1][symbol2] = round(float(corr), 3)
                else:
                    correlation_matrix[symbol1][symbol2] = 0.0
        
        # Find highest and lowest correlations
        correlations_list = []
        for symbol1 in correlation_matrix:
            for symbol2 in correlation_matrix[symbol1]:
                if symbol1 != symbol2:
                    correlations_list.append({
                        "pair": f"{symbol1}-{symbol2}",
                        "correlation": correlation_matrix[symbol1][symbol2]
                    })
        
        # Remove duplicates (A-B is same as B-A)
        unique_correlations = []
        seen_pairs = set()
        for corr in correlations_list:
            symbols = sorted(corr["pair"].split("-"))
            pair_key = f"{symbols[0]}-{symbols[1]}"
            if pair_key not in seen_pairs:
                unique_correlations.append({
                    "pair": pair_key,
                    "correlation": corr["correlation"]
                })
                seen_pairs.add(pair_key)
        
        # Sort by correlation strength
        unique_correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        
        # Correlation interpretation
        def interpret_correlation(corr):
            abs_corr = abs(corr)
            if abs_corr >= 0.8:
                return "VERY_STRONG"
            elif abs_corr >= 0.6:
                return "STRONG"
            elif abs_corr >= 0.4:
                return "MODERATE"
            elif abs_corr >= 0.2:
                return "WEAK"
            else:
                return "VERY_WEAK"
        
        # Add interpretations
        for corr in unique_correlations:
            corr["strength"] = interpret_correlation(corr["correlation"])
            corr["direction"] = "POSITIVE" if corr["correlation"] > 0 else "NEGATIVE"
        
        # Market cohesion analysis
        avg_correlation = np.mean([abs(corr["correlation"]) for corr in unique_correlations])
        
        if avg_correlation > 0.7:
            market_cohesion = "VERY_HIGH"
        elif avg_correlation > 0.5:
            market_cohesion = "HIGH"
        elif avg_correlation > 0.3:
            market_cohesion = "MODERATE"
        else:
            market_cohesion = "LOW"
        
        return {
            "symbols_analyzed": list(price_data.keys()),
            "correlation_matrix": correlation_matrix,
            "correlation_pairs": unique_correlations,
            "market_cohesion": market_cohesion,
            "average_correlation": round(avg_correlation, 3),
            "analysis_period_days": days,
            "data_points_used": min_length,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Correlation analysis failed")
        return {"error": f"Correlation analysis failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def generate_trading_signals(symbol: str = "BTC", strategy: str = "combined", days: int = 100) -> Dict[str, Any]:
    """
    Generate trading signals based on technical analysis
    
    Args:
        symbol: Cryptocurrency symbol
        strategy: Strategy type ('rsi', 'macd', 'ma', 'combined')
        days: Historical data days
        
    Returns:
        Trading signals with entry/exit recommendations
    """
    try:
        df = safe_fetch_ohlcv_data(symbol, days)
        if df is None or len(df) < 50:
            return {"error": f"Insufficient data for {symbol}. Need at least 50 data points."}
            
        close_prices = df['close'].astype(float)
        current_price = float(close_prices.iloc[-1])
        
        signals = []
        signal_strength = 0
        
        # RSI Strategy
        if strategy in ["rsi", "combined"]:
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + gain / loss))
            current_rsi = float(rsi.iloc[-1])
            
            if current_rsi < 30:
                signals.append({
                    "indicator": "RSI",
                    "signal": "BUY",
                    "strength": "STRONG",
                    "reason": f"RSI oversold at {current_rsi:.1f}"
                })
                signal_strength += 3
            elif current_rsi > 70:
                signals.append({
                    "indicator": "RSI",
                    "signal": "SELL",
                    "strength": "STRONG", 
                    "reason": f"RSI overbought at {current_rsi:.1f}"
                })
                signal_strength -= 3
            elif current_rsi < 40:
                signals.append({
                    "indicator": "RSI",
                    "signal": "BUY",
                    "strength": "WEAK",
                    "reason": f"RSI bearish at {current_rsi:.1f}"
                })
                signal_strength += 1
            elif current_rsi > 60:
                signals.append({
                    "indicator": "RSI",
                    "signal": "SELL",
                    "strength": "WEAK",
                    "reason": f"RSI bullish at {current_rsi:.1f}"
                })
                signal_strength -= 1
        
        # MACD Strategy
        if strategy in ["macd", "combined"]:
            ema_12 = close_prices.ewm(span=12).mean()
            ema_26 = close_prices.ewm(span=26).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9).mean()
            histogram = macd_line - signal_line
            
            current_macd = float(macd_line.iloc[-1])
            current_signal_line = float(signal_line.iloc[-1])
            current_histogram = float(histogram.iloc[-1])
            
            # MACD crossover signals
            if len(histogram) >= 2:
                if histogram.iloc[-2] < 0 and current_histogram > 0:
                    signals.append({
                        "indicator": "MACD",
                        "signal": "BUY",
                        "strength": "STRONG",
                        "reason": "MACD bullish crossover"
                    })
                    signal_strength += 3
                elif histogram.iloc[-2] > 0 and current_histogram < 0:
                    signals.append({
                        "indicator": "MACD",
                        "signal": "SELL",
                        "strength": "STRONG",
                        "reason": "MACD bearish crossover"
                    })
                    signal_strength -= 3
                elif current_macd > current_signal_line:
                    signals.append({
                        "indicator": "MACD",
                        "signal": "BUY",
                        "strength": "WEAK",
                        "reason": "MACD above signal line"
                    })
                    signal_strength += 1
                else:
                    signals.append({
                        "indicator": "MACD",
                        "signal": "SELL",
                        "strength": "WEAK",
                        "reason": "MACD below signal line"
                    })
                    signal_strength -= 1
        
        # Moving Average Strategy
        if strategy in ["ma", "combined"]:
            ma_20 = close_prices.rolling(window=20).mean()
            ma_50 = close_prices.rolling(window=50).mean()
            
            current_ma_20 = float(ma_20.iloc[-1])
            current_ma_50 = float(ma_50.iloc[-1])
            
            # MA crossover and position signals
            if current_price > current_ma_20 > current_ma_50:
                signals.append({
                    "indicator": "MA",
                    "signal": "BUY",
                    "strength": "STRONG",
                    "reason": "Price above both MAs, bullish alignment"
                })
                signal_strength += 2
            elif current_price < current_ma_20 < current_ma_50:
                signals.append({
                    "indicator": "MA",
                    "signal": "SELL",
                    "strength": "STRONG",
                    "reason": "Price below both MAs, bearish alignment"
                })
                signal_strength -= 2
            elif current_price > current_ma_20:
                signals.append({
                    "indicator": "MA",
                    "signal": "BUY",
                    "strength": "WEAK",
                    "reason": "Price above short-term MA"
                })
                signal_strength += 1
            else:
                signals.append({
                    "indicator": "MA",
                    "signal": "SELL",
                    "strength": "WEAK",
                    "reason": "Price below short-term MA"
                })
                signal_strength -= 1
        
        # Overall recommendation
        if signal_strength >= 5:
            overall_signal = "STRONG_BUY"
        elif signal_strength >= 2:
            overall_signal = "BUY"
        elif signal_strength <= -5:
            overall_signal = "STRONG_SELL"
        elif signal_strength <= -2:
            overall_signal = "SELL"
        else:
            overall_signal = "HOLD"
        
        # Risk management suggestions
        risk_management = {
            "stop_loss_pct": 5.0,  # 5% stop loss
            "take_profit_pct": 10.0,  # 10% take profit
            "position_size_pct": 2.0  # 2% of portfolio
        }
        
        if overall_signal in ["STRONG_BUY", "BUY"]:
            entry_price = current_price
            stop_loss = entry_price * (1 - risk_management["stop_loss_pct"] / 100)
            take_profit = entry_price * (1 + risk_management["take_profit_pct"] / 100)
        elif overall_signal in ["STRONG_SELL", "SELL"]:
            entry_price = current_price
            stop_loss = entry_price * (1 + risk_management["stop_loss_pct"] / 100)
            take_profit = entry_price * (1 - risk_management["take_profit_pct"] / 100)
        else:
            entry_price = stop_loss = take_profit = None
        
        return {
            "symbol": symbol,
            "strategy": strategy,
            "current_price": current_price,
            "overall_signal": overall_signal,
            "signal_strength": signal_strength,
            "individual_signals": signals,
            "entry_recommendations": {
                "entry_price": round(entry_price, 2) if entry_price else None,
                "stop_loss": round(stop_loss, 2) if stop_loss else None,
                "take_profit": round(take_profit, 2) if take_profit else None
            },
            "risk_management": risk_management,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Trading signal generation failed")
        return {"error": f"Trading signal generation failed: {str(e)}", "error_type": type(e).__name__}

@mcp.tool()
def backtest_strategy(symbol: str = "BTC", strategy: str = "rsi_oversold", period: str = "3m", initial_capital: float = 10000) -> Dict[str, Any]:
    """
    Backtest a simple trading strategy
    
    Args:
        symbol: Cryptocurrency symbol
        strategy: Strategy to backtest ('rsi_oversold', 'macd_crossover', 'ma_crossover')
        period: Backtest period ('1m', '3m', '6m', '1y')
        initial_capital: Initial capital in USD
        
    Returns:
        Backtesting results with performance metrics
    """
    try:
        # Convert period to days
        period_days = {
            "1m": 30,
            "3m": 90,
            "6m": 180,
            "1y": 365
        }.get(period, 90)
        
        df = safe_fetch_ohlcv_data(symbol, period_days)
        if df is None or len(df) < 50:
            return {"error": f"Insufficient data for {symbol}. Need at least 50 data points."}
            
        close_prices = df['close'].astype(float)
        
        # Initialize backtest variables
        capital = initial_capital
        position = 0  # 0 = no position, 1 = long
        entry_price = 0
        trades = []
        portfolio_values = [initial_capital]
        
        # Strategy implementation
        for i in range(50, len(close_prices)):  # Start after enough data for indicators
            current_price = float(close_prices.iloc[i])
            
            # RSI Oversold Strategy
            if strategy == "rsi_oversold":
                # Calculate RSI for current position
                delta = close_prices.iloc[i-14:i+1].diff()
                gain = (delta.where(delta > 0, 0)).mean()
                loss = (-delta.where(delta < 0, 0)).mean()
                
                if loss != 0:
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    
                    # Buy signal: RSI < 30 and no position
                    if rsi < 30 and position == 0:
                        position = 1
                        entry_price = current_price
                        shares = capital / current_price
                        
                    # Sell signal: RSI > 70 and have position
                    elif rsi > 70 and position == 1:
                        exit_price = current_price
                        capital = shares * exit_price
                        
                        # Record trade
                        trades.append({
                            "entry_price": round(entry_price, 2),
                            "exit_price": round(exit_price, 2),
                            "return_pct": round((exit_price - entry_price) / entry_price * 100, 2),
                            "profit_loss": round((exit_price - entry_price) * shares, 2)
                        })
                        
                        position = 0
                        shares = 0
            
            # MACD Crossover Strategy
            elif strategy == "macd_crossover":
                if i >= 26:  # Need enough data for MACD
                    prices_slice = close_prices.iloc[i-26:i+1]
                    ema_12 = prices_slice.ewm(span=12).mean()
                    ema_26 = prices_slice.ewm(span=26).mean()
                    macd_line = ema_12 - ema_26
                    signal_line = macd_line.ewm(span=9).mean()
                    
                    if len(macd_line) >= 2 and len(signal_line) >= 2:
                        # Buy signal: MACD crosses above signal line
                        if (macd_line.iloc[-2] <= signal_line.iloc[-2] and 
                            macd_line.iloc[-1] > signal_line.iloc[-1] and 
                            position == 0):
                            position = 1
                            entry_price = current_price
                            shares = capital / current_price
                            
                        # Sell signal: MACD crosses below signal line
                        elif (macd_line.iloc[-2] >= signal_line.iloc[-2] and 
                              macd_line.iloc[-1] < signal_line.iloc[-1] and 
                              position == 1):
                            exit_price = current_price
                            capital = shares * exit_price
                            
                            trades.append({
                                "entry_price": round(entry_price, 2),
                                "exit_price": round(exit_price, 2),
                                "return_pct": round((exit_price - entry_price) / entry_price * 100, 2),
                                "profit_loss": round((exit_price - entry_price) * shares, 2)
                            })
                            
                            position = 0
                            shares = 0
            
            # Moving Average Crossover Strategy
            elif strategy == "ma_crossover":
                if i >= 50:  # Need enough data for both MAs
                    ma_20 = close_prices.iloc[i-19:i+1].mean()
                    ma_50 = close_prices.iloc[i-49:i+1].mean()
                    prev_ma_20 = close_prices.iloc[i-20:i].mean()
                    prev_ma_50 = close_prices.iloc[i-50:i].mean()
                    
                    # Buy signal: MA20 crosses above MA50
                    if prev_ma_20 <= prev_ma_50 and ma_20 > ma_50 and position == 0:
                        position = 1
                        entry_price = current_price
                        shares = capital / current_price
                        
                    # Sell signal: MA20 crosses below MA50
                    elif prev_ma_20 >= prev_ma_50 and ma_20 < ma_50 and position == 1:
                        exit_price = current_price
                        capital = shares * exit_price
                        
                        trades.append({
                            "entry_price": round(entry_price, 2),
                            "exit_price": round(exit_price, 2),
                            "return_pct": round((exit_price - entry_price) / entry_price * 100, 2),
                            "profit_loss": round((exit_price - entry_price) * shares, 2)
                        })
                        
                        position = 0
                        shares = 0
            
            # Calculate current portfolio value
            if position == 1:
                current_value = shares * current_price
            else:
                current_value = capital
                
            portfolio_values.append(current_value)
        
        # Close any open position at the end
        if position == 1:
            final_price = float(close_prices.iloc[-1])
            capital = shares * final_price
            
            trades.append({
                "entry_price": round(entry_price, 2),
                "exit_price": round(final_price, 2),
                "return_pct": round((final_price - entry_price) / entry_price * 100, 2),
                "profit_loss": round((final_price - entry_price) * shares, 2)
            })
        
        # Calculate performance metrics
        final_value = portfolio_values[-1]
        total_return = (final_value - initial_capital) / initial_capital * 100
        
        if trades:
            winning_trades = [t for t in trades if t["return_pct"] > 0]
            losing_trades = [t for t in trades if t["return_pct"] <= 0]
            
            win_rate = len(winning_trades) / len(trades) * 100
            avg_win = np.mean([t["return_pct"] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t["return_pct"] for t in losing_trades]) if losing_trades else 0
            
            # Calculate max drawdown
            peak = initial_capital
            max_drawdown = 0
            for value in portfolio_values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak * 100
                max_drawdown = max(max_drawdown, drawdown)
        else:
            win_rate = avg_win = avg_loss = max_drawdown = 0
        
        # Buy and hold comparison
        buy_hold_return = (float(close_prices.iloc[-1]) - float(close_prices.iloc[49])) / float(close_prices.iloc[49]) * 100
        
        return {
            "symbol": symbol,
            "strategy": strategy,
            "period": period,
            "initial_capital": initial_capital,
            "final_value": round(final_value, 2),
            "total_return_pct": round(total_return, 2),
            "buy_hold_return_pct": round(buy_hold_return, 2),
            "outperformance_pct": round(total_return - buy_hold_return, 2),
            "total_trades": len(trades),
            "winning_trades": len([t for t in trades if t["return_pct"] > 0]),
            "losing_trades": len([t for t in trades if t["return_pct"] <= 0]),
            "win_rate_pct": round(win_rate, 1),
            "average_win_pct": round(avg_win, 2),
            "average_loss_pct": round(avg_loss, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "trades_sample": trades[:5],  # First 5 trades as sample
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception("Backtesting failed")
        return {"error": f"Backtesting failed: {str(e)}", "error_type": type(e).__name__}

# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint"""
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok", "server": "crypto-technical-analysis-ccxt", "tools": 14})

if __name__ == "__main__":
    mcp.run() 
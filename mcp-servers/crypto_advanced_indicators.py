#!/usr/bin/env python3
"""
Crypto Advanced Indicators MCP Server

Provides advanced technical indicators beyond the basic server.

8 Tools:
1. calculate_obv - On-Balance Volume (cumulative volume)
2. calculate_mfi - Money Flow Index (RSI with volume)
3. calculate_adx - Average Directional Index (trend strength)
4. calculate_ichimoku - Complete Ichimoku Cloud
5. calculate_vwap - Volume Weighted Average Price
6. calculate_pivot_points - Classic Pivots (R1, R2, S1, S2)
7. calculate_williams_r - Williams %R (momentum)
8. detect_divergences - Detect bullish/bearish divergences
"""

import ccxt
from fastmcp import FastMCP
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from validators import validate_symbol, validate_positive_int, validate_timeframe

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("crypto-advanced-indicators")

# Reliable exchange
EXCHANGE = ccxt.binance()

# Indicator thresholds
MFI_OVERBOUGHT = 80
MFI_OVERSOLD = 20
ADX_VERY_STRONG = 50
ADX_STRONG = 25
ADX_WEAK = 20
WILLIAMS_OVERBOUGHT = -20
WILLIAMS_OVERSOLD = -80
VWAP_EXTREME_STD = 2  # Standard deviations for extreme zones


def _fetch_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 100):
    """Helper: Fetch OHLCV data."""
    formatted_symbol = f"{symbol}/USDT"
    ohlcv = EXCHANGE.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


@mcp.tool()
def calculate_obv(
    symbol: str = "BTC",
    timeframe: str = "1h",
    periods: int = 100
) -> Dict[str, Any]:
    """
    Calculate On-Balance Volume (OBV).

    OBV accumulates volume based on price direction.
    OBV up + Price up = Bullish confirmation
    OBV down + Price up = Bearish divergence (warning)

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        periods: Historical periods

    Returns:
        Current OBV, trend, and divergences
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        periods = validate_positive_int(periods, "periods", max_value=500)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # Calculate OBV
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])

        df['obv'] = obv

        # OBV trend (last 20 periods)
        obv_recent = df['obv'].iloc[-20:]
        obv_slope = np.polyfit(range(len(obv_recent)), obv_recent, 1)[0]
        obv_trend = "RISING" if obv_slope > 0 else "FALLING"

        # Price trend
        price_recent = df['close'].iloc[-20:]
        price_slope = np.polyfit(range(len(price_recent)), price_recent, 1)[0]
        price_trend = "RISING" if price_slope > 0 else "FALLING"

        # Detect divergences
        if obv_trend == "FALLING" and price_trend == "RISING":
            divergence = "BEARISH_DIVERGENCE"
            interpretation = "Bearish divergence - Price rising but volume falling - Possible reversal"
        elif obv_trend == "RISING" and price_trend == "FALLING":
            divergence = "BULLISH_DIVERGENCE"
            interpretation = "Bullish divergence - Price falling but volume rising - Possible bounce"
        else:
            divergence = "NO_DIVERGENCE"
            interpretation = "OBV and price in sync - Trend confirmed"

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "current_obv": float(df['obv'].iloc[-1]),
            "obv_trend": obv_trend,
            "price_trend": price_trend,
            "divergence": divergence,
            "interpretation": interpretation,
            "current_price": float(df['close'].iloc[-1]),
        }

    except Exception as e:
        logger.exception("calculate_obv failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def calculate_mfi(
    symbol: str = "BTC",
    timeframe: str = "1h",
    period: int = 14,
    periods: int = 100
) -> Dict[str, Any]:
    """
    Calculate Money Flow Index (MFI) - "RSI with volume".

    MFI > 80 = Overbought
    MFI < 20 = Oversold

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        timeframe: Timeframe
        period: MFI period (default 14)
        periods: Historical data

    Returns:
        Current MFI with overbought/oversold signals
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        period = validate_positive_int(period, "period", max_value=100)
        periods = validate_positive_int(periods, "periods", max_value=500)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # Typical Price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # Raw Money Flow
        df['money_flow'] = df['typical_price'] * df['volume']

        # Positive/Negative Money Flow
        positive_flow = []
        negative_flow = []

        for i in range(1, len(df)):
            if df['typical_price'].iloc[i] > df['typical_price'].iloc[i-1]:
                positive_flow.append(df['money_flow'].iloc[i])
                negative_flow.append(0)
            elif df['typical_price'].iloc[i] < df['typical_price'].iloc[i-1]:
                positive_flow.append(0)
                negative_flow.append(df['money_flow'].iloc[i])
            else:
                positive_flow.append(0)
                negative_flow.append(0)

        df['positive_flow'] = [0] + positive_flow
        df['negative_flow'] = [0] + negative_flow

        # Calculate MFI
        mfi_values = []
        for i in range(period, len(df)):
            pos_sum = df['positive_flow'].iloc[i-period:i].sum()
            neg_sum = df['negative_flow'].iloc[i-period:i].sum()

            if neg_sum == 0:
                mfi_val = 100
            else:
                money_ratio = pos_sum / neg_sum
                mfi_val = 100 - (100 / (1 + money_ratio))

            mfi_values.append(mfi_val)

        df['mfi'] = [None] * period + mfi_values

        current_mfi = df['mfi'].iloc[-1]

        # Signals
        if current_mfi > MFI_OVERBOUGHT:
            signal = "OVERBOUGHT"
            interpretation = "Overbought - High money flow - Possible correction"
        elif current_mfi < MFI_OVERSOLD:
            signal = "OVERSOLD"
            interpretation = "Oversold - Low money flow - Possible bounce"
        else:
            signal = "NEUTRAL"
            interpretation = "MFI in neutral range"

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "period": period,
            "current_mfi": round(float(current_mfi), 2),
            "signal": signal,
            "interpretation": interpretation,
            "current_price": float(df['close'].iloc[-1]),
        }

    except Exception as e:
        logger.exception("calculate_mfi failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def calculate_adx(
    symbol: str = "BTC",
    timeframe: str = "1h",
    period: int = 14,
    periods: int = 100
) -> Dict[str, Any]:
    """
    Calculate Average Directional Index (ADX) - Trend strength.

    ADX > 25 = Strong trend
    ADX < 20 = No trend (ranging)

    Args:
        symbol: Symbol
        timeframe: Timeframe
        period: ADX period (default 14)
        periods: Historical data

    Returns:
        ADX with +DI and -DI for trend direction
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        period = validate_positive_int(period, "period", max_value=100)
        periods = validate_positive_int(periods, "periods", max_value=500)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # +DM and -DM
        df['up_move'] = df['high'] - df['high'].shift()
        df['down_move'] = df['low'].shift() - df['low']

        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)

        # Smoothed TR, +DM, -DM
        df['tr_smooth'] = df['tr'].rolling(window=period).sum()
        df['plus_dm_smooth'] = df['plus_dm'].rolling(window=period).sum()
        df['minus_dm_smooth'] = df['minus_dm'].rolling(window=period).sum()

        # +DI and -DI
        df['plus_di'] = 100 * (df['plus_dm_smooth'] / df['tr_smooth'])
        df['minus_di'] = 100 * (df['minus_dm_smooth'] / df['tr_smooth'])

        # DX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])

        # ADX (moving average of DX)
        df['adx'] = df['dx'].rolling(window=period).mean()

        current_adx = df['adx'].iloc[-1]
        current_plus_di = df['plus_di'].iloc[-1]
        current_minus_di = df['minus_di'].iloc[-1]

        # Interpretation
        if current_adx > ADX_VERY_STRONG:
            strength = "VERY_STRONG_TREND"
        elif current_adx > ADX_STRONG:
            strength = "STRONG_TREND"
        elif current_adx > ADX_WEAK:
            strength = "WEAK_TREND"
        else:
            strength = "NO_TREND"

        direction = "BULLISH" if current_plus_di > current_minus_di else "BEARISH"

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "period": period,
            "current_adx": round(float(current_adx), 2),
            "plus_di": round(float(current_plus_di), 2),
            "minus_di": round(float(current_minus_di), 2),
            "trend_strength": strength,
            "trend_direction": direction,
            "interpretation": f"{strength} - {direction} trend",
            "current_price": float(df['close'].iloc[-1]),
        }

    except Exception as e:
        logger.exception("calculate_adx failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def calculate_ichimoku(
    symbol: str = "BTC",
    timeframe: str = "4h",
    periods: int = 100
) -> Dict[str, Any]:
    """
    Calculate complete Ichimoku Cloud.

    Components:
    - Tenkan-sen (Conversion Line): (9-high + 9-low) / 2
    - Kijun-sen (Base Line): (26-high + 26-low) / 2
    - Senkou Span A: (Tenkan + Kijun) / 2, shifted 26 forward
    - Senkou Span B: (52-high + 52-low) / 2, shifted 26 forward
    - Chikou Span: Close, shifted 26 backward

    Args:
        symbol: Symbol
        timeframe: Timeframe (recommended 4h or 1d)
        periods: Historical data

    Returns:
        Complete Ichimoku with trading signals
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        periods = validate_positive_int(periods, "periods", max_value=500)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # Tenkan-sen (Conversion Line)
        period9_high = df['high'].rolling(window=9).max()
        period9_low = df['low'].rolling(window=9).min()
        df['tenkan_sen'] = (period9_high + period9_low) / 2

        # Kijun-sen (Base Line)
        period26_high = df['high'].rolling(window=26).max()
        period26_low = df['low'].rolling(window=26).min()
        df['kijun_sen'] = (period26_high + period26_low) / 2

        # Senkou Span A (Leading Span A)
        df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)

        # Senkou Span B (Leading Span B)
        period52_high = df['high'].rolling(window=52).max()
        period52_low = df['low'].rolling(window=52).min()
        df['senkou_span_b'] = ((period52_high + period52_low) / 2).shift(26)

        # Chikou Span (Lagging Span)
        df['chikou_span'] = df['close'].shift(-26)

        # Current values
        current_price = df['close'].iloc[-1]
        tenkan = df['tenkan_sen'].iloc[-1]
        kijun = df['kijun_sen'].iloc[-1]
        senkou_a = df['senkou_span_a'].iloc[-1]
        senkou_b = df['senkou_span_b'].iloc[-1]

        cloud_color = "BULLISH_CLOUD" if senkou_a > senkou_b else "BEARISH_CLOUD"

        # Signals
        signals = []

        # Price vs Cloud
        if current_price > max(senkou_a, senkou_b):
            signals.append("Price above cloud - Bullish")
        elif current_price < min(senkou_a, senkou_b):
            signals.append("Price below cloud - Bearish")
        else:
            signals.append("Price inside cloud - Indecisive")

        # TK Cross
        if tenkan > kijun:
            signals.append("Tenkan > Kijun - Bullish signal")
        else:
            signals.append("Tenkan < Kijun - Bearish signal")

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": float(current_price),
            "tenkan_sen": round(float(tenkan), 2),
            "kijun_sen": round(float(kijun), 2),
            "senkou_span_a": round(float(senkou_a), 2),
            "senkou_span_b": round(float(senkou_b), 2),
            "cloud_color": cloud_color,
            "signals": signals,
        }

    except Exception as e:
        logger.exception("calculate_ichimoku failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def calculate_vwap(
    symbol: str = "BTC",
    timeframe: str = "1h",
    periods: int = 24
) -> Dict[str, Any]:
    """
    Calculate Volume Weighted Average Price (VWAP).

    VWAP = Sum(Price x Volume) / Sum(Volume)

    Price > VWAP = Bullish
    Price < VWAP = Bearish

    Args:
        symbol: Symbol
        timeframe: Timeframe
        periods: Periods (default 24 for daily VWAP with 1h bars)

    Returns:
        VWAP with standard deviation bands
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        periods = validate_positive_int(periods, "periods", max_value=500)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # Typical Price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # VWAP
        df['tp_volume'] = df['typical_price'] * df['volume']
        vwap = df['tp_volume'].sum() / df['volume'].sum()

        # Standard deviation
        df['vwap_dev'] = (df['typical_price'] - vwap) ** 2 * df['volume']
        variance = df['vwap_dev'].sum() / df['volume'].sum()
        std_dev = variance ** 0.5

        # VWAP bands
        vwap_upper_1 = vwap + std_dev
        vwap_upper_2 = vwap + VWAP_EXTREME_STD * std_dev
        vwap_lower_1 = vwap - std_dev
        vwap_lower_2 = vwap - VWAP_EXTREME_STD * std_dev

        current_price = df['close'].iloc[-1]

        # Signals
        if current_price > vwap_upper_2:
            signal = "EXTREMELY_OVERBOUGHT"
            interpretation = "Price > VWAP+2std - Extremely overbought"
        elif current_price < vwap_lower_2:
            signal = "EXTREMELY_OVERSOLD"
            interpretation = "Price < VWAP-2std - Extremely oversold"
        elif current_price > vwap:
            signal = "BULLISH"
            interpretation = "Price above VWAP - Buyers dominating"
        else:
            signal = "BEARISH"
            interpretation = "Price below VWAP - Sellers dominating"

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "periods": periods,
            "current_price": float(current_price),
            "vwap": round(float(vwap), 2),
            "vwap_upper_1": round(float(vwap_upper_1), 2),
            "vwap_upper_2": round(float(vwap_upper_2), 2),
            "vwap_lower_1": round(float(vwap_lower_1), 2),
            "vwap_lower_2": round(float(vwap_lower_2), 2),
            "signal": signal,
            "interpretation": interpretation,
        }

    except Exception as e:
        logger.exception("calculate_vwap failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def calculate_pivot_points(
    symbol: str = "BTC",
    timeframe: str = "1d",
    periods: int = 2
) -> Dict[str, Any]:
    """
    Calculate classic Pivot Points (R1, R2, R3, S1, S2, S3).

    Pivot = (High + Low + Close) / 3
    R1 = 2 x Pivot - Low
    S1 = 2 x Pivot - High

    Args:
        symbol: Symbol
        timeframe: Timeframe (recommended 1d)
        periods: Periods (default 2 for previous day pivots)

    Returns:
        Pivots with resistance and support levels
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        periods = validate_positive_int(periods, "periods", max_value=30)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # Use previous period data
        high = df['high'].iloc[-2]
        low = df['low'].iloc[-2]
        close = df['close'].iloc[-2]

        # Pivot Point
        pivot = (high + low + close) / 3

        # Resistances
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)

        # Supports
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)

        current_price = df['close'].iloc[-1]

        # Find closest level
        levels = {
            'R3': r3, 'R2': r2, 'R1': r1,
            'PIVOT': pivot,
            'S1': s1, 'S2': s2, 'S3': s3
        }

        closest_level = min(levels.items(), key=lambda x: abs(x[1] - current_price))

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": float(current_price),
            "pivot": round(float(pivot), 2),
            "resistances": {
                "R1": round(float(r1), 2),
                "R2": round(float(r2), 2),
                "R3": round(float(r3), 2),
            },
            "supports": {
                "S1": round(float(s1), 2),
                "S2": round(float(s2), 2),
                "S3": round(float(s3), 2),
            },
            "closest_level": {
                "level": closest_level[0],
                "price": round(float(closest_level[1]), 2),
                "distance": round(float(current_price - closest_level[1]), 2)
            }
        }

    except Exception as e:
        logger.exception("calculate_pivot_points failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def calculate_williams_r(
    symbol: str = "BTC",
    timeframe: str = "1h",
    period: int = 14,
    periods: int = 100
) -> Dict[str, Any]:
    """
    Calculate Williams %R (momentum oscillator).

    Williams %R = (Highest High - Close) / (Highest High - Lowest Low) x -100

    %R > -20 = Overbought
    %R < -80 = Oversold

    Args:
        symbol: Symbol
        timeframe: Timeframe
        period: Williams %R period (default 14)
        periods: Historical data

    Returns:
        Williams %R with signals
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        period = validate_positive_int(period, "period", max_value=100)
        periods = validate_positive_int(periods, "periods", max_value=500)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # Calculate Williams %R
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()

        df['williams_r'] = ((highest_high - df['close']) / (highest_high - lowest_low)) * -100

        current_wr = df['williams_r'].iloc[-1]

        # Signals
        if current_wr > WILLIAMS_OVERBOUGHT:
            signal = "OVERBOUGHT"
            interpretation = "Overbought - Possible correction"
        elif current_wr < WILLIAMS_OVERSOLD:
            signal = "OVERSOLD"
            interpretation = "Oversold - Possible bounce"
        else:
            signal = "NEUTRAL"
            interpretation = "Williams %R in neutral range"

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "period": period,
            "current_williams_r": round(float(current_wr), 2),
            "signal": signal,
            "interpretation": interpretation,
            "current_price": float(df['close'].iloc[-1]),
        }

    except Exception as e:
        logger.exception("calculate_williams_r failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def detect_divergences(
    symbol: str = "BTC",
    timeframe: str = "1h",
    periods: int = 100
) -> Dict[str, Any]:
    """
    Detect divergences between price and RSI/MACD.

    Bullish Divergence: Price makes lower low, RSI makes higher low
    Bearish Divergence: Price makes higher high, RSI makes lower high

    Args:
        symbol: Symbol
        timeframe: Timeframe
        periods: Historical periods

    Returns:
        Detected divergences with reversal signals
    """
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        periods = validate_positive_int(periods, "periods", max_value=500)

        df = _fetch_ohlcv(symbol, timeframe, periods)

        # Calculate RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Find swing highs/lows (simplified - last 50 periods)
        recent = df.iloc[-50:]

        price_highs = recent['high'].nlargest(3).index.tolist()
        price_lows = recent['low'].nsmallest(3).index.tolist()

        divergences = []

        # Bearish Divergence (price rising, RSI falling)
        if len(price_highs) >= 2:
            last_high_idx = price_highs[0]
            prev_high_idx = price_highs[1]

            if recent.loc[last_high_idx, 'high'] > recent.loc[prev_high_idx, 'high']:
                if recent.loc[last_high_idx, 'rsi'] < recent.loc[prev_high_idx, 'rsi']:
                    divergences.append({
                        "type": "BEARISH_DIVERGENCE",
                        "interpretation": "Price makes higher high, RSI makes lower high - Possible bearish reversal"
                    })

        # Bullish Divergence (price falling, RSI rising)
        if len(price_lows) >= 2:
            last_low_idx = price_lows[0]
            prev_low_idx = price_lows[1]

            if recent.loc[last_low_idx, 'low'] < recent.loc[prev_low_idx, 'low']:
                if recent.loc[last_low_idx, 'rsi'] > recent.loc[prev_low_idx, 'rsi']:
                    divergences.append({
                        "type": "BULLISH_DIVERGENCE",
                        "interpretation": "Price makes lower low, RSI makes higher low - Possible bullish reversal"
                    })

        if not divergences:
            divergences.append({
                "type": "NO_DIVERGENCE",
                "interpretation": "No significant divergences detected"
            })

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": float(df['close'].iloc[-1]),
            "current_rsi": round(float(df['rsi'].iloc[-1]), 2),
            "divergences": divergences,
        }

    except Exception as e:
        logger.exception("detect_divergences failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


if __name__ == "__main__":
    mcp.run()

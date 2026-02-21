#!/usr/bin/env python3
"""
Crypto Futures Data MCP Server

Provides perpetual futures market data using CCXT (no API keys required).

10 Tools:
1. get_funding_rate - Current perpetual funding rate
2. get_funding_rate_history - Historical funding rates
3. get_open_interest - Current Open Interest
4. get_long_short_ratio - Long/Short ratio of traders
5. get_taker_buy_sell_ratio - Taker buy/sell volume ratio
6. calculate_liquidation_levels - Estimated liquidation levels
7. get_perpetual_stats - Complete perpetual statistics
8. compare_funding_rates - Compare funding across exchanges
9. analyze_funding_trend - Analyze funding rate trend
10. detect_funding_arbitrage - Detect funding rate arbitrage opportunities

Supported Exchanges (no API keys):
- Binance, Bybit, OKX, Bitget, MEXC
"""

import ccxt
from fastmcp import FastMCP
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import statistics
import logging

from validators import validate_symbol, validate_exchange, validate_positive_int

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("crypto-futures-data")

# Reliable exchanges with public futures data
RELIABLE_FUTURES_EXCHANGES = {
    'binance': ccxt.binance(),
    'bybit': ccxt.bybit(),
    'okx': ccxt.okx(),
    'bitget': ccxt.bitget(),
    'mexc': ccxt.mexc()
}

# Funding rate thresholds (annualized %)
FUNDING_NEUTRAL_THRESHOLD = 5        # |annual rate| < 5% = neutral
FUNDING_EXTREME_THRESHOLD = 50       # |annual rate| > 50% = extreme

# Long/short ratio thresholds
LS_EXTREMELY_BULLISH = 2.0           # Ratio > 2 = extremely bullish
LS_BULLISH = 1.2                     # Ratio > 1.2 = bullish
LS_EXTREMELY_BEARISH = 0.5           # Ratio < 0.5 = extremely bearish
LS_BEARISH = 0.8                     # Ratio < 0.8 = bearish

# Taker buy/sell ratio thresholds
TAKER_STRONG_BUY = 1.5              # Ratio > 1.5 = strong buy pressure
TAKER_MODERATE_BUY = 1.1            # Ratio > 1.1 = moderate buy pressure
TAKER_STRONG_SELL = 0.7             # Ratio < 0.7 = strong sell pressure
TAKER_MODERATE_SELL = 0.9           # Ratio < 0.9 = moderate sell pressure

# Funding trend thresholds (% change)
TREND_RAPID_INCREASE_PCT = 50       # > 50% change = rapidly increasing
TREND_INCREASE_PCT = 10             # > 10% change = increasing
TREND_RAPID_DECREASE_PCT = -50      # < -50% change = rapidly decreasing
TREND_DECREASE_PCT = -10            # < -10% change = decreasing

# Funding volatility thresholds
FUNDING_VOL_HIGH = 0.0005           # Funding rate stdev > 0.0005 = high vol
FUNDING_VOL_MODERATE = 0.0002       # Funding rate stdev > 0.0002 = moderate vol

# Arbitrage thresholds
MIN_ARBITRAGE_SPREAD_ANNUAL = 10    # Minimum annual % for arbitrage opportunity

# Scoring adjustments
SCORE_FUNDING_EXTREME = 15
SCORE_LS_RATIO = 10
SCORE_TAKER_PRESSURE = 10


def _get_exchange(exchange_name: str):
    """Get exchange instance."""
    if exchange_name not in RELIABLE_FUTURES_EXCHANGES:
        raise ValueError(f"Unsupported exchange: {exchange_name}. Supported: {sorted(RELIABLE_FUTURES_EXCHANGES.keys())}")
    return RELIABLE_FUTURES_EXCHANGES[exchange_name]


def _format_symbol(symbol: str) -> str:
    """
    Format symbol for perpetual futures.
    BTC -> BTC/USDT:USDT
    """
    if ':' in symbol:
        return symbol
    if '/' in symbol:
        base = symbol.split('/')[0]
        return f"{base}/USDT:USDT"
    return f"{symbol}/USDT:USDT"


@mcp.tool()
def get_funding_rate(
    symbol: str = "BTC",
    exchange: str = "binance"
) -> Dict[str, Any]:
    """
    Get current perpetual funding rate.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange (binance, bybit, okx, bitget, mexc)

    Returns:
        Current funding rate, next funding time, and analysis
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(RELIABLE_FUTURES_EXCHANGES.keys()))

        ex = _get_exchange(exchange)
        formatted_symbol = _format_symbol(symbol)

        funding_rate = ex.fetch_funding_rate(formatted_symbol)

        # Annualized funding rate
        rate = funding_rate['fundingRate']
        annual_rate = rate * 3 * 365 * 100  # 3 times per day

        # Next funding time
        next_funding = datetime.fromtimestamp(funding_rate['fundingTimestamp'] / 1000)

        # Analysis
        if abs(annual_rate) < FUNDING_NEUTRAL_THRESHOLD:
            bias = "NEUTRAL"
            interpretation = "Neutral funding rate, balanced market"
        elif annual_rate > FUNDING_NEUTRAL_THRESHOLD:
            bias = "BULLISH_EXTREME"
            interpretation = "Very positive funding rate - Longs paying Shorts - Possible correction"
        else:
            bias = "BEARISH_EXTREME"
            interpretation = "Very negative funding rate - Shorts paying Longs - Possible bounce"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "funding_rate": rate,
            "funding_rate_percentage": rate * 100,
            "annual_rate_percentage": round(annual_rate, 2),
            "next_funding_time": next_funding.isoformat(),
            "time_until_funding": str(next_funding - datetime.now()),
            "market_bias": bias,
            "interpretation": interpretation,
            "raw_data": funding_rate
        }

    except Exception as e:
        logger.exception("get_funding_rate failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def get_funding_rate_history(
    symbol: str = "BTC",
    exchange: str = "binance",
    hours: int = 24
) -> Dict[str, Any]:
    """
    Get historical funding rates.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange
        hours: Hours of history (default 24)

    Returns:
        Historical funding rates with statistics
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(RELIABLE_FUTURES_EXCHANGES.keys()))
        hours = validate_positive_int(hours, "hours", max_value=720)

        ex = _get_exchange(exchange)
        formatted_symbol = _format_symbol(symbol)

        since = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
        history = ex.fetch_funding_rate_history(formatted_symbol, since=since)

        if not history:
            return {
                "success": False,
                "error": "No funding rate history available",
                "error_type": "NoDataError",
                "exchange": exchange,
                "symbol": formatted_symbol
            }

        rates = [h['fundingRate'] for h in history]

        avg_rate = statistics.mean(rates)
        max_rate = max(rates)
        min_rate = min(rates)

        # Trend (last 8 vs first 8 funding rates)
        if len(rates) >= 16:
            recent_avg = statistics.mean(rates[-8:])
            older_avg = statistics.mean(rates[:8])
            trend = "INCREASING" if recent_avg > older_avg else "DECREASING"
        else:
            trend = "INSUFFICIENT_DATA"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "period_hours": hours,
            "total_fundings": len(rates),
            "average_rate": avg_rate,
            "average_rate_percentage": avg_rate * 100,
            "max_rate": max_rate,
            "min_rate": min_rate,
            "current_rate": rates[-1],
            "trend": trend,
            "annual_rate_avg": round(avg_rate * 3 * 365 * 100, 2),
            "history": history[-20:]
        }

    except Exception as e:
        logger.exception("get_funding_rate_history failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def get_open_interest(
    symbol: str = "BTC",
    exchange: str = "binance"
) -> Dict[str, Any]:
    """
    Get current Open Interest.

    Open Interest = Total open contracts (longs + shorts).
    Indicator of liquidity and trend strength.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange

    Returns:
        Current Open Interest and trend analysis
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(RELIABLE_FUTURES_EXCHANGES.keys()))

        ex = _get_exchange(exchange)
        formatted_symbol = _format_symbol(symbol)

        oi = ex.fetch_open_interest(formatted_symbol)

        ticker = ex.fetch_ticker(formatted_symbol)
        current_price = ticker['last']

        oi_value = oi['openInterestAmount']
        oi_contracts = oi['openInterestValue']

        oi_btc_equivalent = oi_value / current_price if current_price else 0

        interpretation = []
        if oi_btc_equivalent > 100000:
            interpretation.append("Very high OI - High liquidity and participation")
        elif oi_btc_equivalent < 50000:
            interpretation.append("Low OI - Low futures participation")

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "open_interest_usd": oi_value,
            "open_interest_contracts": oi_contracts,
            "open_interest_btc_equivalent": round(oi_btc_equivalent, 2),
            "current_price": current_price,
            "timestamp": oi['timestamp'],
            "interpretation": " | ".join(interpretation) if interpretation else "Normal OI",
            "raw_data": oi
        }

    except Exception as e:
        logger.exception("get_open_interest failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def get_long_short_ratio(
    symbol: str = "BTC",
    exchange: str = "binance",
    period: str = "5m"
) -> Dict[str, Any]:
    """
    Get Long/Short ratio of traders (top traders and all accounts).

    NOTE: Only Binance provides this data publicly.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange (only binance supported)
        period: Period (5m, 15m, 30m, 1h, 4h, 1d)

    Returns:
        Long/Short ratios for top traders and all accounts
    """
    if exchange != "binance":
        return {
            "success": False,
            "error": "Long/Short ratio only available on Binance",
            "error_type": "UnsupportedExchange",
            "exchange": exchange
        }

    try:
        symbol = validate_symbol(symbol)
        import requests

        base_symbol = symbol.replace("/", "").replace(":USDT", "")

        # Top Trader Long/Short Ratio (Positions)
        url_top = "https://fapi.binance.com/futures/data/topLongShortPositionRatio"
        params_top = {
            "symbol": f"{base_symbol}USDT",
            "period": period,
            "limit": 1
        }

        # Global Long/Short Ratio (Accounts)
        url_global = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
        params_global = {
            "symbol": f"{base_symbol}USDT",
            "period": period,
            "limit": 1
        }

        resp_top = requests.get(url_top, params=params_top, timeout=10)
        resp_global = requests.get(url_global, params=params_global, timeout=10)

        if resp_top.status_code != 200 or resp_global.status_code != 200:
            return {
                "success": False,
                "error": "Error fetching Long/Short ratio from Binance",
                "error_type": "APIError",
                "status_top": resp_top.status_code,
                "status_global": resp_global.status_code
            }

        data_top = resp_top.json()[0] if resp_top.json() else {}
        data_global = resp_global.json()[0] if resp_global.json() else {}

        top_ratio = float(data_top.get('longShortRatio', 0))
        global_ratio = float(data_global.get('longShortRatio', 0))

        # Analysis
        if top_ratio > LS_EXTREMELY_BULLISH:
            sentiment_top = "EXTREMELY_BULLISH"
            interpretation_top = "Top traders very long - Possible reversal"
        elif top_ratio > LS_BULLISH:
            sentiment_top = "BULLISH"
            interpretation_top = "Top traders moderately long"
        elif top_ratio < LS_EXTREMELY_BEARISH:
            sentiment_top = "EXTREMELY_BEARISH"
            interpretation_top = "Top traders very short - Possible reversal"
        elif top_ratio < LS_BEARISH:
            sentiment_top = "BEARISH"
            interpretation_top = "Top traders moderately short"
        else:
            sentiment_top = "NEUTRAL"
            interpretation_top = "Top traders balanced"

        return {
            "success": True,
            "exchange": "binance",
            "symbol": f"{base_symbol}USDT",
            "period": period,
            "top_trader_long_short_ratio": top_ratio,
            "global_long_short_ratio": global_ratio,
            "top_trader_sentiment": sentiment_top,
            "interpretation": interpretation_top,
            "divergence": abs(top_ratio - global_ratio) > 0.3,
            "raw_data": {
                "top_traders": data_top,
                "global": data_global
            }
        }

    except Exception as e:
        logger.exception("get_long_short_ratio failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def get_taker_buy_sell_ratio(
    symbol: str = "BTC",
    exchange: str = "binance",
    period: str = "5m"
) -> Dict[str, Any]:
    """
    Get taker buy/sell volume ratio.

    Taker Buy > Taker Sell = Buy pressure
    Taker Sell > Taker Buy = Sell pressure

    NOTE: Only Binance provides this data.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange (only binance)
        period: Period (5m, 15m, 30m, 1h, 4h, 1d)

    Returns:
        Taker buy/sell ratio with pressure analysis
    """
    if exchange != "binance":
        return {
            "success": False,
            "error": "Taker buy/sell ratio only available on Binance",
            "error_type": "UnsupportedExchange",
            "exchange": exchange
        }

    try:
        symbol = validate_symbol(symbol)
        import requests

        base_symbol = symbol.replace("/", "").replace(":USDT", "")

        url = "https://fapi.binance.com/futures/data/takerlongshortRatio"
        params = {
            "symbol": f"{base_symbol}USDT",
            "period": period,
            "limit": 1
        }

        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"Error fetching taker ratio: {resp.status_code}",
                "error_type": "APIError",
                "exchange": exchange
            }

        data = resp.json()[0] if resp.json() else {}

        buy_sell_ratio = float(data.get('buySellRatio', 0))
        buy_vol = float(data.get('buyVol', 0))
        sell_vol = float(data.get('sellVol', 0))

        # Pressure analysis
        if buy_sell_ratio > TAKER_STRONG_BUY:
            pressure = "STRONG_BUY_PRESSURE"
            interpretation = "Strong buy pressure - Takers buying aggressively"
        elif buy_sell_ratio > TAKER_MODERATE_BUY:
            pressure = "MODERATE_BUY_PRESSURE"
            interpretation = "Moderate buy pressure"
        elif buy_sell_ratio < TAKER_STRONG_SELL:
            pressure = "STRONG_SELL_PRESSURE"
            interpretation = "Strong sell pressure - Takers selling aggressively"
        elif buy_sell_ratio < TAKER_MODERATE_SELL:
            pressure = "MODERATE_SELL_PRESSURE"
            interpretation = "Moderate sell pressure"
        else:
            pressure = "BALANCED"
            interpretation = "Balanced pressure between buyers and sellers"

        return {
            "success": True,
            "exchange": "binance",
            "symbol": f"{base_symbol}USDT",
            "period": period,
            "buy_sell_ratio": buy_sell_ratio,
            "taker_buy_volume": buy_vol,
            "taker_sell_volume": sell_vol,
            "market_pressure": pressure,
            "interpretation": interpretation,
            "raw_data": data
        }

    except Exception as e:
        logger.exception("get_taker_buy_sell_ratio failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def calculate_liquidation_levels(
    symbol: str = "BTC",
    exchange: str = "binance",
    current_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate estimated liquidation levels for different leverages.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange
        current_price: Current price (fetched automatically if not provided)

    Returns:
        Liquidation levels for longs and shorts at different leverages
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(RELIABLE_FUTURES_EXCHANGES.keys()))

        ex = _get_exchange(exchange)
        formatted_symbol = _format_symbol(symbol)

        if current_price is None:
            ticker = ex.fetch_ticker(formatted_symbol)
            current_price = ticker['last']

        # Common leverages
        leverages = [5, 10, 20, 50, 100]

        liquidation_levels = {
            "longs": {},
            "shorts": {}
        }

        for lev in leverages:
            # LONG liquidation: price * (1 - 1/leverage - fees)
            long_liq = current_price * (1 - (1/lev) - 0.005)
            liquidation_levels["longs"][f"{lev}x"] = round(long_liq, 2)

            # SHORT liquidation: price * (1 + 1/leverage + fees)
            short_liq = current_price * (1 + (1/lev) + 0.005)
            liquidation_levels["shorts"][f"{lev}x"] = round(short_liq, 2)

        # Critical zones (where most liquidity accumulates)
        critical_zones = {
            "long_liquidations": {
                "10x_zone": f"${round(liquidation_levels['longs']['10x'], 0)} (10x leverage)",
                "20x_zone": f"${round(liquidation_levels['longs']['20x'], 0)} (20x leverage)"
            },
            "short_liquidations": {
                "10x_zone": f"${round(liquidation_levels['shorts']['10x'], 0)} (10x leverage)",
                "20x_zone": f"${round(liquidation_levels['shorts']['20x'], 0)} (20x leverage)"
            }
        }

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "current_price": current_price,
            "liquidation_levels": liquidation_levels,
            "critical_zones": critical_zones,
            "interpretation": "Liquidation zones are price magnets - High probability of hunting"
        }

    except Exception as e:
        logger.exception("calculate_liquidation_levels failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def get_perpetual_stats(
    symbol: str = "BTC",
    exchange: str = "binance"
) -> Dict[str, Any]:
    """
    Get complete perpetual statistics (funding rate, OI, ratios, liquidations).

    Consolidates all previous tools into a single comprehensive analysis.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange

    Returns:
        Complete perpetual analysis with scoring
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(RELIABLE_FUTURES_EXCHANGES.keys()))

        funding = get_funding_rate(symbol, exchange)
        oi = get_open_interest(symbol, exchange)

        ls_ratio = None
        if exchange == "binance":
            ls_ratio = get_long_short_ratio(symbol, exchange)

        taker_ratio = None
        if exchange == "binance":
            taker_ratio = get_taker_buy_sell_ratio(symbol, exchange)

        current_price = oi.get('current_price') if oi.get('success') else None
        liq_levels = calculate_liquidation_levels(symbol, exchange, current_price)

        # Signal scoring (0-100)
        score = 50  # Neutral
        signals = []

        # Funding rate analysis
        if funding.get('success'):
            annual_rate = funding['annual_rate_percentage']
            if abs(annual_rate) > FUNDING_EXTREME_THRESHOLD:
                if annual_rate > FUNDING_EXTREME_THRESHOLD:
                    score -= SCORE_FUNDING_EXTREME
                    signals.append("Extremely high funding - Correction risk")
                else:
                    score += SCORE_FUNDING_EXTREME
                    signals.append("Extremely low funding - Possible bounce")

        # Long/Short ratio analysis
        if ls_ratio and ls_ratio.get('success'):
            ratio = ls_ratio['top_trader_long_short_ratio']
            if ratio > LS_EXTREMELY_BULLISH:
                score -= SCORE_LS_RATIO
                signals.append("Top traders very long - Crowded trade")
            elif ratio < LS_EXTREMELY_BEARISH:
                score += SCORE_LS_RATIO
                signals.append("Top traders very short - Contrarian setup")

        # Taker pressure analysis
        if taker_ratio and taker_ratio.get('success'):
            pressure = taker_ratio['market_pressure']
            if pressure == "STRONG_BUY_PRESSURE":
                score += SCORE_TAKER_PRESSURE
                signals.append("Strong buy pressure")
            elif pressure == "STRONG_SELL_PRESSURE":
                score -= SCORE_TAKER_PRESSURE
                signals.append("Strong sell pressure")

        # Overall signal
        if score >= 70:
            overall_signal = "STRONG_BUY"
        elif score >= 55:
            overall_signal = "BUY"
        elif score <= 30:
            overall_signal = "STRONG_SELL"
        elif score <= 45:
            overall_signal = "SELL"
        else:
            overall_signal = "NEUTRAL"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "score": score,
            "overall_signal": overall_signal,
            "signals": signals,
            "funding_rate_data": funding if funding.get('success') else None,
            "open_interest_data": oi if oi.get('success') else None,
            "long_short_ratio_data": ls_ratio if ls_ratio and ls_ratio.get('success') else None,
            "taker_ratio_data": taker_ratio if taker_ratio and taker_ratio.get('success') else None,
            "liquidation_levels": liq_levels if liq_levels.get('success') else None
        }

    except Exception as e:
        logger.exception("get_perpetual_stats failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def compare_funding_rates(
    symbol: str = "BTC",
    exchanges: List[str] = None
) -> Dict[str, Any]:
    """
    Compare funding rates across multiple exchanges.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchanges: List of exchanges (default: all supported)

    Returns:
        Funding rate comparison with arbitrage detection
    """
    if exchanges is None:
        exchanges = list(RELIABLE_FUTURES_EXCHANGES.keys())

    try:
        symbol = validate_symbol(symbol)

        results = {}
        rates = []

        for exchange in exchanges:
            try:
                funding = get_funding_rate(symbol, exchange)
                if funding.get('success'):
                    results[exchange] = funding
                    rates.append({
                        'exchange': exchange,
                        'rate': funding['funding_rate'],
                        'annual_rate': funding['annual_rate_percentage']
                    })
            except Exception:
                continue

        if not rates:
            return {
                "success": False,
                "error": "Could not fetch funding rates from any exchange",
                "error_type": "NoDataError"
            }

        rates_sorted = sorted(rates, key=lambda x: x['rate'])

        lowest = rates_sorted[0]
        highest = rates_sorted[-1]
        spread = highest['rate'] - lowest['rate']
        spread_annual = spread * 3 * 365 * 100

        arbitrage_opportunity = spread_annual > MIN_ARBITRAGE_SPREAD_ANNUAL

        return {
            "success": True,
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "exchanges_compared": len(rates),
            "lowest_funding": lowest,
            "highest_funding": highest,
            "spread": spread,
            "spread_annual_percentage": round(spread_annual, 2),
            "arbitrage_opportunity": arbitrage_opportunity,
            "arbitrage_strategy": "Long on exchange with lowest funding, Short on exchange with highest funding" if arbitrage_opportunity else None,
            "all_rates": rates_sorted,
            "detailed_data": results
        }

    except Exception as e:
        logger.exception("compare_funding_rates failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


@mcp.tool()
def analyze_funding_trend(
    symbol: str = "BTC",
    exchange: str = "binance",
    hours: int = 48
) -> Dict[str, Any]:
    """
    Analyze funding rate trend over time.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange
        hours: Hours of history (default 48)

    Returns:
        Trend analysis with next funding prediction
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(RELIABLE_FUTURES_EXCHANGES.keys()))
        hours = validate_positive_int(hours, "hours", max_value=720)

        history = get_funding_rate_history(symbol, exchange, hours)

        if not history.get('success'):
            return history

        rates = [h['fundingRate'] for h in history['history']]

        if len(rates) >= 8:
            recent_4 = statistics.mean(rates[-4:])
            older_4 = statistics.mean(rates[-8:-4])

            change_pct = ((recent_4 - older_4) / abs(older_4)) * 100 if older_4 != 0 else 0

            if change_pct > TREND_RAPID_INCREASE_PCT:
                trend = "RAPIDLY_INCREASING"
                interpretation = "Funding rising rapidly - Market overheating"
            elif change_pct > TREND_INCREASE_PCT:
                trend = "INCREASING"
                interpretation = "Funding increasing - Longs dominating"
            elif change_pct < TREND_RAPID_DECREASE_PCT:
                trend = "RAPIDLY_DECREASING"
                interpretation = "Funding dropping rapidly - Capitulation"
            elif change_pct < TREND_DECREASE_PCT:
                trend = "DECREASING"
                interpretation = "Funding decreasing - Shorts dominating"
            else:
                trend = "STABLE"
                interpretation = "Stable funding - Balanced market"
        else:
            trend = "INSUFFICIENT_DATA"
            interpretation = "Not enough data for trend analysis"
            change_pct = 0

        # Funding volatility
        if len(rates) >= 8:
            volatility = statistics.stdev(rates[-8:])
            vol_label = "HIGH" if volatility > FUNDING_VOL_HIGH else "MODERATE" if volatility > FUNDING_VOL_MODERATE else "LOW"
        else:
            volatility = 0
            vol_label = "UNKNOWN"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": symbol,
            "period_hours": hours,
            "trend": trend,
            "change_percentage": round(change_pct, 2),
            "interpretation": interpretation,
            "volatility": volatility,
            "volatility_label": vol_label,
            "current_rate": rates[-1],
            "average_rate": history['average_rate'],
            "max_rate": history['max_rate'],
            "min_rate": history['min_rate']
        }

    except Exception as e:
        logger.exception("analyze_funding_trend failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def detect_funding_arbitrage(
    symbol: str = "BTC",
    min_spread_annual: float = 10.0
) -> Dict[str, Any]:
    """
    Detect funding rate arbitrage opportunities between exchanges.

    Strategy: Long on exchange with low funding, Short on exchange with high funding.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        min_spread_annual: Minimum annualized spread to consider arbitrage (%)

    Returns:
        Arbitrage opportunities with spread and recommended strategy
    """
    try:
        symbol = validate_symbol(symbol)

        comparison = compare_funding_rates(symbol)

        if not comparison.get('success'):
            return comparison

        spread_annual = comparison['spread_annual_percentage']

        if spread_annual < min_spread_annual:
            return {
                "success": True,
                "symbol": symbol,
                "arbitrage_opportunity": False,
                "spread_annual_percentage": spread_annual,
                "min_required_spread": min_spread_annual,
                "message": f"Current spread ({spread_annual:.2f}%) below minimum required ({min_spread_annual}%)"
            }

        lowest = comparison['lowest_funding']
        highest = comparison['highest_funding']

        # Estimated profit (assuming 8 hours per funding, 3 times per day)
        profit_per_funding = comparison['spread']
        daily_profit_pct = profit_per_funding * 3 * 100

        return {
            "success": True,
            "symbol": symbol,
            "arbitrage_opportunity": True,
            "spread_annual_percentage": spread_annual,
            "estimated_daily_profit_percentage": round(daily_profit_pct, 4),
            "strategy": {
                "action": "FUNDING_RATE_ARBITRAGE",
                "long_exchange": lowest['exchange'],
                "long_funding_rate": lowest['rate'],
                "short_exchange": highest['exchange'],
                "short_funding_rate": highest['rate'],
                "hedge_ratio": "1:1 (delta neutral)",
                "risk": "Exchange risk, liquidation risk, funding convergence"
            },
            "execution_steps": [
                f"1. Deposit collateral on {lowest['exchange']} and {highest['exchange']}",
                f"2. Open LONG on {lowest['exchange']} (funding rate: {lowest['rate']:.6f})",
                f"3. Open SHORT on {highest['exchange']} (funding rate: {highest['rate']:.6f})",
                "4. Keep positions balanced (delta neutral)",
                "5. Close when spread decreases or is no longer profitable"
            ],
            "warnings": [
                "Requires collateral on both exchanges",
                "Liquidation risk if price moves significantly",
                "Funding rates can converge quickly",
                "Trading fees may reduce profit"
            ]
        }

    except Exception as e:
        logger.exception("detect_funding_arbitrage failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "symbol": symbol
        }


if __name__ == "__main__":
    mcp.run()

#!/usr/bin/env python3
"""
Crypto Market Microstructure MCP Server

Deep market microstructure analysis: orderbook, order flow,
spread, slippage, and manipulation detection.

6 Tools:
1. analyze_orderbook_depth - Deep orderbook liquidity analysis
2. detect_orderbook_imbalance - Detect buy/sell imbalances
3. calculate_spread_metrics - Bid-ask spread, slippage, and trading costs
4. analyze_order_flow - Order flow (buyer/seller aggression)
5. detect_spoofing_patterns - Detect fake orders (spoofing/layering)
6. calculate_market_impact - Estimated impact of large orders
"""

import ccxt
from fastmcp import FastMCP
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import statistics
import logging

from validators import validate_symbol, validate_exchange, validate_positive_int

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("crypto-market-microstructure")

# Reusable exchange instances
EXCHANGES = {
    'binance': ccxt.binance(),
    'bybit': ccxt.bybit(),
}

# Orderbook analysis thresholds
STRONG_LEVEL_MULTIPLIER = 2       # Volume > Nx avg = strong level
IMBALANCE_STRONG_BUY = 1.5       # Bid/ask ratio for strong buy pressure
IMBALANCE_STRONG_SELL = 0.66     # Bid/ask ratio for strong sell pressure
IMBALANCE_EXTREME_BUY = 2.0      # Extreme buy pressure threshold
IMBALANCE_EXTREME_SELL = 0.5     # Extreme sell pressure threshold
SPREAD_EXCELLENT_BPS = 5         # Spread < 5 bps = excellent liquidity
SPREAD_GOOD_BPS = 10             # Spread < 10 bps = good liquidity
SPREAD_MODERATE_BPS = 20         # Spread < 20 bps = moderate liquidity
SPOOFING_VOLUME_MULTIPLIER = 5   # Volume > 5x avg = suspicious
SPOOFING_DISTANCE_PCT = 0.5      # Orders > 0.5% from mid = suspicious
SPOOFING_COUNT_THRESHOLD = 3     # > 3 suspicious orders = elevated score
ORDER_FLOW_STRONG_PCT = 65       # > 65% buy/sell = strong aggression
ORDER_FLOW_MODERATE_PCT = 55     # > 55% buy/sell = moderate aggression
LARGE_TRADE_MULTIPLIER = 3       # Volume > 3x avg = large trade
IMPACT_MINIMAL_PCT = 0.1         # Price impact < 0.1% = minimal
IMPACT_LOW_PCT = 0.5             # Price impact < 0.5% = low
IMPACT_MODERATE_PCT = 1.0        # Price impact < 1.0% = moderate
IMPACT_HIGH_PCT = 2.0            # Price impact < 2.0% = high


def _get_exchange(exchange_name: str):
    """Get exchange instance, defaulting to binance."""
    return EXCHANGES.get(exchange_name, EXCHANGES['binance'])


@mcp.tool()
def analyze_orderbook_depth(
    symbol: str = "BTC",
    exchange: str = "binance",
    depth_levels: int = 50
) -> Dict[str, Any]:
    """
    Analyze orderbook depth and liquidity.

    Args:
        symbol: Symbol (BTC, ETH, etc.)
        exchange: Exchange (binance, bybit)
        depth_levels: Depth levels to analyze (default 50)

    Returns:
        Liquidity analysis with concentrated bids/asks
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(EXCHANGES.keys()))
        depth_levels = validate_positive_int(depth_levels, "depth_levels", max_value=500)

        ex = _get_exchange(exchange)
        formatted_symbol = f"{symbol}/USDT"

        orderbook = ex.fetch_order_book(formatted_symbol, limit=depth_levels)

        bids = orderbook['bids'][:depth_levels]
        asks = orderbook['asks'][:depth_levels]

        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        mid_price = (best_bid + best_ask) / 2

        # Total liquidity
        total_bid_volume = sum(bid[1] for bid in bids)
        total_ask_volume = sum(ask[1] for ask in asks)
        total_bid_value = sum(bid[0] * bid[1] for bid in bids)
        total_ask_value = sum(ask[0] * ask[1] for ask in asks)

        # Liquidity ratio
        liquidity_ratio = total_bid_volume / total_ask_volume if total_ask_volume > 0 else 0

        # Spread
        spread_absolute = best_ask - best_bid
        spread_percentage = (spread_absolute / mid_price) * 100 if mid_price > 0 else 0

        # Liquidity concentration (% in top 10 levels)
        top10_bid_volume = sum(bid[1] for bid in bids[:10])
        top10_ask_volume = sum(ask[1] for ask in asks[:10])
        bid_concentration = (top10_bid_volume / total_bid_volume) * 100 if total_bid_volume > 0 else 0
        ask_concentration = (top10_ask_volume / total_ask_volume) * 100 if total_ask_volume > 0 else 0

        # Average depth per level
        avg_bid_depth = total_bid_volume / len(bids) if bids else 0
        avg_ask_depth = total_ask_volume / len(asks) if asks else 0

        # Strong support/resistance analysis (levels with > 2x avg volume)
        strong_support_levels = []
        strong_resistance_levels = []

        for bid in bids:
            if bid[1] > avg_bid_depth * STRONG_LEVEL_MULTIPLIER:
                strong_support_levels.append({
                    "price": bid[0],
                    "volume": bid[1],
                    "strength": round((bid[1] / avg_bid_depth), 2)
                })

        for ask in asks:
            if ask[1] > avg_ask_depth * STRONG_LEVEL_MULTIPLIER:
                strong_resistance_levels.append({
                    "price": ask[0],
                    "volume": ask[1],
                    "strength": round((ask[1] / avg_ask_depth), 2)
                })

        # Interpretation
        if liquidity_ratio > 1.2:
            bias = "BID_HEAVY"
            interpretation = "More liquidity on bids - Buy pressure"
        elif liquidity_ratio < 0.8:
            bias = "ASK_HEAVY"
            interpretation = "More liquidity on asks - Sell pressure"
        else:
            bias = "BALANCED"
            interpretation = "Balanced liquidity"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "timestamp": datetime.now().isoformat(),
            "mid_price": round(mid_price, 2),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": {
                "absolute": round(spread_absolute, 2),
                "percentage": round(spread_percentage, 4)
            },
            "liquidity": {
                "total_bid_volume": round(total_bid_volume, 4),
                "total_ask_volume": round(total_ask_volume, 4),
                "total_bid_value_usd": round(total_bid_value, 2),
                "total_ask_value_usd": round(total_ask_value, 2),
                "liquidity_ratio": round(liquidity_ratio, 2),
                "bias": bias
            },
            "concentration": {
                "bid_concentration_top10": round(bid_concentration, 2),
                "ask_concentration_top10": round(ask_concentration, 2)
            },
            "strong_levels": {
                "support": strong_support_levels[:5],
                "resistance": strong_resistance_levels[:5]
            },
            "interpretation": interpretation
        }

    except Exception as e:
        logger.exception("analyze_orderbook_depth failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def detect_orderbook_imbalance(
    symbol: str = "BTC",
    exchange: str = "binance",
    depth: int = 20
) -> Dict[str, Any]:
    """
    Detect orderbook imbalances (more bids than asks or vice versa).

    Imbalance > 1.5 = Strong buy pressure
    Imbalance < 0.66 = Strong sell pressure

    Args:
        symbol: Symbol
        exchange: Exchange
        depth: Levels to consider (default 20)

    Returns:
        Imbalance ratio with direction prediction
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(EXCHANGES.keys()))
        depth = validate_positive_int(depth, "depth", max_value=200)

        ex = _get_exchange(exchange)
        formatted_symbol = f"{symbol}/USDT"

        orderbook = ex.fetch_order_book(formatted_symbol, limit=depth)

        bids = orderbook['bids'][:depth]
        asks = orderbook['asks'][:depth]

        # Calculate volume at different levels
        levels = [5, 10, 20]
        imbalances = {}

        for level in levels:
            bid_vol = sum(b[1] for b in bids[:level])
            ask_vol = sum(a[1] for a in asks[:level])
            imbalance = bid_vol / ask_vol if ask_vol > 0 else 10
            imbalances[f"level_{level}"] = round(imbalance, 2)

        avg_imbalance = statistics.mean(imbalances.values())

        # Interpretation
        if avg_imbalance > IMBALANCE_EXTREME_BUY:
            pressure = "EXTREME_BUY_PRESSURE"
            prediction = "Very likely upward move"
            confidence = "HIGH"
        elif avg_imbalance > IMBALANCE_STRONG_BUY:
            pressure = "STRONG_BUY_PRESSURE"
            prediction = "Likely upward move"
            confidence = "MEDIUM"
        elif avg_imbalance < IMBALANCE_EXTREME_SELL:
            pressure = "EXTREME_SELL_PRESSURE"
            prediction = "Very likely downward move"
            confidence = "HIGH"
        elif avg_imbalance < IMBALANCE_STRONG_SELL:
            pressure = "STRONG_SELL_PRESSURE"
            prediction = "Likely downward move"
            confidence = "MEDIUM"
        else:
            pressure = "BALANCED"
            prediction = "Balanced orderbook - No clear bias"
            confidence = "LOW"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "timestamp": datetime.now().isoformat(),
            "imbalances_by_level": imbalances,
            "average_imbalance": round(avg_imbalance, 2),
            "market_pressure": pressure,
            "prediction": prediction,
            "confidence": confidence,
            "interpretation": f"Bid/ask ratio: {avg_imbalance:.2f} - {prediction}"
        }

    except Exception as e:
        logger.exception("detect_orderbook_imbalance failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def calculate_spread_metrics(
    symbol: str = "BTC",
    exchange: str = "binance",
    order_size_usd: float = 10000
) -> Dict[str, Any]:
    """
    Calculate spread and slippage metrics.

    Args:
        symbol: Symbol
        exchange: Exchange
        order_size_usd: Order size in USD for slippage calculation

    Returns:
        Spread, estimated slippage, and trading costs
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(EXCHANGES.keys()))

        ex = _get_exchange(exchange)
        formatted_symbol = f"{symbol}/USDT"

        orderbook = ex.fetch_order_book(formatted_symbol, limit=100)

        bids = orderbook['bids']
        asks = orderbook['asks']

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2

        # Spread
        spread_absolute = best_ask - best_bid
        spread_percentage = (spread_absolute / mid_price) * 100
        spread_bps = spread_percentage * 100

        # Calculate slippage for a market buy order (consumes asks)
        cumulative_ask_volume = 0
        cumulative_ask_cost = 0
        buy_slippage_price = None

        for ask in asks:
            ask_price, ask_volume = ask[0], ask[1]
            ask_volume_usd = ask_price * ask_volume

            if cumulative_ask_cost + ask_volume_usd >= order_size_usd:
                remaining_usd = order_size_usd - cumulative_ask_cost
                remaining_volume = remaining_usd / ask_price
                cumulative_ask_volume += remaining_volume
                cumulative_ask_cost = order_size_usd
                buy_slippage_price = ask_price
                break
            else:
                cumulative_ask_volume += ask_volume
                cumulative_ask_cost += ask_volume_usd

        if buy_slippage_price:
            buy_avg_price = order_size_usd / cumulative_ask_volume
            buy_slippage = ((buy_avg_price - best_ask) / best_ask) * 100
        else:
            buy_avg_price = None
            buy_slippage = None

        # Calculate slippage for a market sell order (consumes bids)
        cumulative_bid_volume = 0
        cumulative_bid_value = 0
        sell_slippage_price = None

        for bid in bids:
            bid_price, bid_volume = bid[0], bid[1]
            bid_volume_usd = bid_price * bid_volume

            if cumulative_bid_value + bid_volume_usd >= order_size_usd:
                remaining_usd = order_size_usd - cumulative_bid_value
                remaining_volume = remaining_usd / bid_price
                cumulative_bid_volume += remaining_volume
                cumulative_bid_value = order_size_usd
                sell_slippage_price = bid_price
                break
            else:
                cumulative_bid_volume += bid_volume
                cumulative_bid_value += bid_volume_usd

        if sell_slippage_price:
            sell_avg_price = order_size_usd / cumulative_bid_volume
            sell_slippage = ((best_bid - sell_avg_price) / best_bid) * 100
        else:
            sell_avg_price = None
            sell_slippage = None

        # Total trading cost (spread + slippage)
        if buy_slippage and sell_slippage:
            total_cost_percentage = spread_percentage + ((buy_slippage + sell_slippage) / 2)
        else:
            total_cost_percentage = spread_percentage

        # Liquidity classification
        if spread_bps < SPREAD_EXCELLENT_BPS:
            liquidity_quality = "EXCELLENT"
        elif spread_bps < SPREAD_GOOD_BPS:
            liquidity_quality = "GOOD"
        elif spread_bps < SPREAD_MODERATE_BPS:
            liquidity_quality = "MODERATE"
        else:
            liquidity_quality = "POOR"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "mid_price": round(mid_price, 2),
            "spread": {
                "absolute": round(spread_absolute, 2),
                "percentage": round(spread_percentage, 4),
                "basis_points": round(spread_bps, 2)
            },
            "slippage_estimate": {
                "order_size_usd": order_size_usd,
                "buy_slippage_percentage": round(buy_slippage, 4) if buy_slippage else None,
                "sell_slippage_percentage": round(sell_slippage, 4) if sell_slippage else None,
                "buy_avg_price": round(buy_avg_price, 2) if buy_avg_price else None,
                "sell_avg_price": round(sell_avg_price, 2) if sell_avg_price else None
            },
            "total_trading_cost_percentage": round(total_cost_percentage, 4),
            "liquidity_quality": liquidity_quality,
            "interpretation": f"Spread: {spread_bps:.1f} bps - Liquidity: {liquidity_quality}"
        }

    except Exception as e:
        logger.exception("calculate_spread_metrics failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def analyze_order_flow(
    symbol: str = "BTC",
    exchange: str = "binance",
    limit: int = 100
) -> Dict[str, Any]:
    """
    Analyze order flow (recent trades) to detect aggression.

    Taker buy = Aggressive buyer (bullish)
    Taker sell = Aggressive seller (bearish)

    Args:
        symbol: Symbol
        exchange: Exchange
        limit: Number of recent trades to analyze

    Returns:
        Buyer/seller aggression analysis
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(EXCHANGES.keys()))
        limit = validate_positive_int(limit, "limit", max_value=1000)

        ex = _get_exchange(exchange)
        formatted_symbol = f"{symbol}/USDT"

        trades = ex.fetch_trades(formatted_symbol, limit=limit)

        if not trades:
            return {
                "success": False,
                "error": "No trades available",
                "error_type": "NoDataError",
                "exchange": exchange,
                "symbol": formatted_symbol
            }

        # Analyze trades
        buy_volume = 0
        sell_volume = 0
        buy_count = 0
        sell_count = 0

        large_buy_trades = []
        large_sell_trades = []

        # Calculate average volume to detect "large" trades
        volumes = [t['amount'] for t in trades]
        avg_volume = statistics.mean(volumes)
        large_trade_threshold = avg_volume * LARGE_TRADE_MULTIPLIER

        for trade in trades:
            amount = trade['amount']
            side = trade['side']

            if side == 'buy':
                buy_volume += amount
                buy_count += 1
                if amount > large_trade_threshold:
                    large_buy_trades.append({
                        "price": trade['price'],
                        "amount": amount,
                        "timestamp": trade['timestamp']
                    })
            else:
                sell_volume += amount
                sell_count += 1
                if amount > large_trade_threshold:
                    large_sell_trades.append({
                        "price": trade['price'],
                        "amount": amount,
                        "timestamp": trade['timestamp']
                    })

        total_volume = buy_volume + sell_volume
        buy_ratio = (buy_volume / total_volume) * 100 if total_volume > 0 else 0
        sell_ratio = (sell_volume / total_volume) * 100 if total_volume > 0 else 0

        # Aggression classification
        if buy_ratio > ORDER_FLOW_STRONG_PCT:
            aggression = "STRONG_BUY_AGGRESSION"
            interpretation = "Buyers very aggressive - Strong upward pressure"
        elif buy_ratio > ORDER_FLOW_MODERATE_PCT:
            aggression = "MODERATE_BUY_AGGRESSION"
            interpretation = "Buyers moderately aggressive"
        elif sell_ratio > ORDER_FLOW_STRONG_PCT:
            aggression = "STRONG_SELL_AGGRESSION"
            interpretation = "Sellers very aggressive - Strong downward pressure"
        elif sell_ratio > ORDER_FLOW_MODERATE_PCT:
            aggression = "MODERATE_SELL_AGGRESSION"
            interpretation = "Sellers moderately aggressive"
        else:
            aggression = "BALANCED"
            interpretation = "Balanced flow between buyers and sellers"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "timestamp": datetime.now().isoformat(),
            "trades_analyzed": limit,
            "volume_distribution": {
                "buy_volume": round(buy_volume, 4),
                "sell_volume": round(sell_volume, 4),
                "buy_percentage": round(buy_ratio, 2),
                "sell_percentage": round(sell_ratio, 2)
            },
            "trade_count": {
                "buy_trades": buy_count,
                "sell_trades": sell_count
            },
            "large_trades": {
                "threshold": round(large_trade_threshold, 4),
                "large_buys": len(large_buy_trades),
                "large_sells": len(large_sell_trades),
                "recent_large_buys": large_buy_trades[:5],
                "recent_large_sells": large_sell_trades[:5]
            },
            "market_aggression": aggression,
            "interpretation": interpretation
        }

    except Exception as e:
        logger.exception("analyze_order_flow failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def detect_spoofing_patterns(
    symbol: str = "BTC",
    exchange: str = "binance",
    depth: int = 50,
    large_order_threshold_btc: float = 5.0
) -> Dict[str, Any]:
    """
    Detect potential spoofing patterns (fake orders).

    Spoofing = Placing large orders to move the price, then canceling them.

    Indicators:
    - Very large orders far from current price
    - Abnormal concentration at specific levels

    Args:
        symbol: Symbol
        exchange: Exchange
        depth: Orderbook levels to analyze
        large_order_threshold_btc: Threshold to consider an order "large" (in BTC)

    Returns:
        Detection of potentially fake orders
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(EXCHANGES.keys()))
        depth = validate_positive_int(depth, "depth", max_value=500)

        ex = _get_exchange(exchange)
        formatted_symbol = f"{symbol}/USDT"

        orderbook = ex.fetch_order_book(formatted_symbol, limit=depth)

        bids = orderbook['bids']
        asks = orderbook['asks']

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2

        # Detect abnormally large orders
        suspicious_bids = []
        suspicious_asks = []

        avg_bid_volume = statistics.mean([b[1] for b in bids])
        avg_ask_volume = statistics.mean([a[1] for a in asks])

        # Threshold: 5x average AND greater than BTC threshold
        large_bid_threshold = max(avg_bid_volume * SPOOFING_VOLUME_MULTIPLIER, large_order_threshold_btc)
        large_ask_threshold = max(avg_ask_volume * SPOOFING_VOLUME_MULTIPLIER, large_order_threshold_btc)

        for i, bid in enumerate(bids):
            price, volume = bid[0], bid[1]
            distance_from_mid = ((mid_price - price) / mid_price) * 100

            # Large orders > 0.5% away from mid price are suspicious
            if volume > large_bid_threshold and distance_from_mid > SPOOFING_DISTANCE_PCT:
                suspicious_bids.append({
                    "level": i,
                    "price": price,
                    "volume": round(volume, 4),
                    "distance_percentage": round(distance_from_mid, 2),
                    "volume_ratio": round(volume / avg_bid_volume, 2)
                })

        for i, ask in enumerate(asks):
            price, volume = ask[0], ask[1]
            distance_from_mid = ((price - mid_price) / mid_price) * 100

            if volume > large_ask_threshold and distance_from_mid > SPOOFING_DISTANCE_PCT:
                suspicious_asks.append({
                    "level": i,
                    "price": price,
                    "volume": round(volume, 4),
                    "distance_percentage": round(distance_from_mid, 2),
                    "volume_ratio": round(volume / avg_ask_volume, 2)
                })

        # Spoofing score
        spoofing_score = 0

        if len(suspicious_bids) > SPOOFING_COUNT_THRESHOLD:
            spoofing_score += 25
        if len(suspicious_asks) > SPOOFING_COUNT_THRESHOLD:
            spoofing_score += 25
        if len(suspicious_bids) > len(suspicious_asks) * 2:
            spoofing_score += 25  # Possible fake support
        elif len(suspicious_asks) > len(suspicious_bids) * 2:
            spoofing_score += 25  # Possible fake resistance

        # Interpretation
        if spoofing_score > 50:
            risk_level = "HIGH"
            interpretation = "High spoofing risk - Suspicious large orders detected"
        elif spoofing_score > 25:
            risk_level = "MODERATE"
            interpretation = "Moderate spoofing risk - Some suspicious orders"
        else:
            risk_level = "LOW"
            interpretation = "Low spoofing risk - Orderbook appears legitimate"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "timestamp": datetime.now().isoformat(),
            "spoofing_score": spoofing_score,
            "risk_level": risk_level,
            "suspicious_orders": {
                "bids": suspicious_bids[:10],
                "asks": suspicious_asks[:10],
                "total_suspicious_bids": len(suspicious_bids),
                "total_suspicious_asks": len(suspicious_asks)
            },
            "interpretation": interpretation,
            "recommendation": "Verify if these orders persist or get canceled quickly" if risk_level != "LOW" else "Orderbook appears healthy"
        }

    except Exception as e:
        logger.exception("detect_spoofing_patterns failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


@mcp.tool()
def calculate_market_impact(
    symbol: str = "BTC",
    exchange: str = "binance",
    order_size_usd: float = 100000
) -> Dict[str, Any]:
    """
    Calculate the estimated market impact of a large order.

    Market Impact = How much the price would move when executing an order.

    Args:
        symbol: Symbol
        exchange: Exchange
        order_size_usd: Order size in USD

    Returns:
        Estimated price impact and total execution cost
    """
    try:
        symbol = validate_symbol(symbol)
        exchange = validate_exchange(exchange, supported=set(EXCHANGES.keys()))

        ex = _get_exchange(exchange)
        formatted_symbol = f"{symbol}/USDT"

        orderbook = ex.fetch_order_book(formatted_symbol, limit=200)

        bids = orderbook['bids']
        asks = orderbook['asks']

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2

        # BUY ORDER (consumes asks)
        cumulative_volume = 0
        cumulative_cost = 0
        levels_consumed = 0
        insufficient_liquidity_buy = False

        for ask in asks:
            ask_price, ask_volume = ask[0], ask[1]
            ask_value = ask_price * ask_volume

            if cumulative_cost + ask_value >= order_size_usd:
                remaining_usd = order_size_usd - cumulative_cost
                remaining_volume = remaining_usd / ask_price
                cumulative_volume += remaining_volume
                cumulative_cost = order_size_usd
                levels_consumed += 1
                break
            else:
                cumulative_volume += ask_volume
                cumulative_cost += ask_value
                levels_consumed += 1

        if cumulative_cost >= order_size_usd:
            avg_execution_price = order_size_usd / cumulative_volume
            price_impact_buy = ((avg_execution_price - best_ask) / best_ask) * 100
            price_movement_buy = avg_execution_price - mid_price
            price_movement_buy_pct = ((avg_execution_price - mid_price) / mid_price) * 100
        else:
            avg_execution_price = None
            price_impact_buy = None
            price_movement_buy = None
            price_movement_buy_pct = None
            insufficient_liquidity_buy = True

        # SELL ORDER (consumes bids)
        cumulative_volume_sell = 0
        cumulative_value_sell = 0
        levels_consumed_sell = 0
        insufficient_liquidity_sell = False

        for bid in bids:
            bid_price, bid_volume = bid[0], bid[1]
            bid_value = bid_price * bid_volume

            if cumulative_value_sell + bid_value >= order_size_usd:
                remaining_usd = order_size_usd - cumulative_value_sell
                remaining_volume = remaining_usd / bid_price
                cumulative_volume_sell += remaining_volume
                cumulative_value_sell = order_size_usd
                levels_consumed_sell += 1
                break
            else:
                cumulative_volume_sell += bid_volume
                cumulative_value_sell += bid_value
                levels_consumed_sell += 1

        if cumulative_value_sell >= order_size_usd:
            avg_execution_price_sell = order_size_usd / cumulative_volume_sell
            price_impact_sell = ((best_bid - avg_execution_price_sell) / best_bid) * 100
            price_movement_sell = mid_price - avg_execution_price_sell
            price_movement_sell_pct = ((mid_price - avg_execution_price_sell) / mid_price) * 100
        else:
            avg_execution_price_sell = None
            price_impact_sell = None
            price_movement_sell = None
            price_movement_sell_pct = None
            insufficient_liquidity_sell = True

        # Impact classification
        if price_impact_buy and price_impact_buy < IMPACT_MINIMAL_PCT:
            impact_classification = "MINIMAL"
        elif price_impact_buy and price_impact_buy < IMPACT_LOW_PCT:
            impact_classification = "LOW"
        elif price_impact_buy and price_impact_buy < IMPACT_MODERATE_PCT:
            impact_classification = "MODERATE"
        elif price_impact_buy and price_impact_buy < IMPACT_HIGH_PCT:
            impact_classification = "HIGH"
        else:
            impact_classification = "VERY_HIGH"

        return {
            "success": True,
            "exchange": exchange,
            "symbol": formatted_symbol,
            "order_size_usd": order_size_usd,
            "mid_price": round(mid_price, 2),
            "buy_order_impact": {
                "average_execution_price": round(avg_execution_price, 2) if avg_execution_price else None,
                "price_impact_percentage": round(price_impact_buy, 4) if price_impact_buy else None,
                "price_movement_usd": round(price_movement_buy, 2) if price_movement_buy else None,
                "price_movement_percentage": round(price_movement_buy_pct, 4) if price_movement_buy_pct else None,
                "levels_consumed": levels_consumed,
                "insufficient_liquidity": insufficient_liquidity_buy
            },
            "sell_order_impact": {
                "average_execution_price": round(avg_execution_price_sell, 2) if avg_execution_price_sell else None,
                "price_impact_percentage": round(price_impact_sell, 4) if price_impact_sell else None,
                "price_movement_usd": round(price_movement_sell, 2) if price_movement_sell else None,
                "price_movement_percentage": round(price_movement_sell_pct, 4) if price_movement_sell_pct else None,
                "levels_consumed": levels_consumed_sell,
                "insufficient_liquidity": insufficient_liquidity_sell
            },
            "impact_classification": impact_classification,
            "recommendation": f"Impact {impact_classification} - Consider splitting into multiple orders" if impact_classification in ["HIGH", "VERY_HIGH"] else "Acceptable impact for direct execution"
        }

    except Exception as e:
        logger.exception("calculate_market_impact failed")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exchange": exchange,
            "symbol": symbol
        }


if __name__ == "__main__":
    mcp.run()

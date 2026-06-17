"""E4.1 — Stop/target engine ported from swing_scanner.

compute_targets: 5-method confluence engine (pure function, no I/O).
attach_risk: populates stop/target/atr/risk_reward on any result dataclass.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pandas as pd
from ta.volatility import AverageTrueRange


@dataclass
class TargetMethod:
    name: str
    price: float
    label: str


@dataclass
class TargetAnalysis:
    methods: list
    confluence_zone: tuple
    suggested_target: float
    risk_reward: float
    first_obstacle: float = 0.0


def find_swing_points(df: pd.DataFrame, window: int = 5) -> tuple:
    """Find the most recent swing high and swing low for Fibonacci calculation."""
    highs = df["High"].values
    lows = df["Low"].values
    n = len(df)

    swing_high = None
    swing_high_idx = None
    swing_low = None
    swing_low_idx = None

    for i in range(n - 1 - window, window, -1):
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, min(window + 1, n - i))):
            swing_high = highs[i]
            swing_high_idx = i
            break

    start = (swing_high_idx - 1) if swing_high_idx else n - 1 - window
    for i in range(start, window, -1):
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, min(window + 1, n - i))):
            swing_low = lows[i]
            swing_low_idx = i
            break

    return swing_low, swing_high, swing_low_idx, swing_high_idx


def compute_targets(df: pd.DataFrame, price: float, stop: float,
                    setup: str, atr: float) -> TargetAnalysis:
    """5-method profit target engine. Pure function — no I/O.

    EMA20 is computed inline from df["Close"] — no pre-computed column required.
    """
    ema20_series = df["Close"].ewm(span=20).mean()
    methods = []

    # Method 1: ATR-Based
    if setup == "PULLBACK":
        atr_target = round(price + 2 * atr, 2)
        methods.append(TargetMethod("ATR (2×)", atr_target, "Entry + 2× avg daily range"))
    else:
        atr_target = round(price + 3 * atr, 2)
        methods.append(TargetMethod("ATR (3×)", atr_target, "Entry + 3× avg daily range"))

    # Method 2: Previous Highs
    recent_highs = df["High"].iloc[-60:]
    resistance_levels = []
    for i in range(2, len(recent_highs) - 2):
        h = recent_highs.iloc[i]
        if h > recent_highs.iloc[i-1] and h > recent_highs.iloc[i-2] and \
           h > recent_highs.iloc[i+1] and h > recent_highs.iloc[i+2] and h > price:
            resistance_levels.append(h)
    period_high = df["High"].iloc[-60:].max()
    if period_high > price:
        resistance_levels.append(period_high)

    if resistance_levels:
        nearest_resistance = min(resistance_levels)
        prev_high_target = round(nearest_resistance, 2)
        methods.append(TargetMethod("Prev High", prev_high_target,
                                    "Nearest resistance from recent highs"))
    else:
        all_time_high = df["High"].max()
        if all_time_high > price:
            prev_high_target = round(all_time_high, 2)
            methods.append(TargetMethod("Prev High", prev_high_target,
                                        "Period high (no nearer resistance)"))

    # Method 3: Measured Move
    high_20 = df["High"].iloc[-21:-1].max()
    low_20 = df["Low"].iloc[-21:-1].min()
    range_height = high_20 - low_20

    if setup == "BREAKOUT":
        measured_target = round(high_20 + range_height, 2)
        methods.append(TargetMethod("Measured Move", measured_target,
                                    f"Breakout + range height (${range_height:.2f})"))
    else:
        measured_target = round(price + range_height * 0.75, 2)
        methods.append(TargetMethod("Measured Move", measured_target,
                                    f"Entry + 75% of range (${range_height:.2f})"))

    # Method 4: Fibonacci Extensions
    swing_low, swing_high, _, _ = find_swing_points(df)
    if swing_low is not None and swing_high is not None and swing_low < swing_high:
        swing_range = swing_high - swing_low
        fib_1272 = round(swing_low + swing_range * 1.272, 2)
        fib_1618 = round(swing_low + swing_range * 1.618, 2)
        fib_levels = [(1.272, fib_1272), (1.618, fib_1618)]
        valid_fibs = [(label, val) for label, val in fib_levels if val > price]
        if valid_fibs:
            fib_label, fib_target = valid_fibs[0]
            methods.append(TargetMethod(f"Fib {fib_label:.3f}", fib_target,
                                        f"Swing ${swing_low:.2f}→${swing_high:.2f}, ext {fib_label}×"))
            if len(valid_fibs) > 1:
                fib_label2, fib_target2 = valid_fibs[1]
                methods.append(TargetMethod(f"Fib {fib_label2:.3f}", fib_target2,
                                            "Extended fib target (aggressive)"))

    # Method 5: EMA Distance (Mean Reversion)
    ema20_window = ema20_series.iloc[-60:]
    close_window = df["Close"].iloc[-60:]
    if len(ema20_window) > 0 and not ema20_window.isna().all():
        pct_above_ema = ((close_window - ema20_window) / ema20_window * 100)
        positive_excursions = pct_above_ema[pct_above_ema > 0]
        if len(positive_excursions) > 5:
            typical_stretch = positive_excursions.quantile(0.75)
            current_ema20 = ema20_series.iloc[-1]
            if not pd.isna(current_ema20) and typical_stretch > 0:
                ema_target = round(current_ema20 * (1 + typical_stretch / 100), 2)
                if ema_target > price:
                    methods.append(TargetMethod("EMA Stretch", ema_target,
                                                f"75th pctl stretch above 20 EMA ({typical_stretch:.1f}%)"))

    # Confluence Analysis
    target_prices = sorted([m.price for m in methods if m.price > price])

    if len(target_prices) >= 2:
        best_cluster: list = []
        best_spread = float("inf")
        for i in range(len(target_prices)):
            cluster = [target_prices[i]]
            for j in range(i + 1, len(target_prices)):
                if (target_prices[j] - target_prices[i]) / target_prices[i] < 0.03:
                    cluster.append(target_prices[j])
            if len(cluster) >= 2:
                spread = cluster[-1] - cluster[0]
                if spread < best_spread:
                    best_spread = spread
                    best_cluster = cluster
        if best_cluster:
            zone_low = min(best_cluster)
            zone_high = max(best_cluster)
            suggested = round((zone_low + zone_high) / 2, 2)
        else:
            zone_low = target_prices[0]
            zone_high = target_prices[0]
            suggested = target_prices[0]
    elif len(target_prices) == 1:
        zone_low = target_prices[0]
        zone_high = target_prices[0]
        suggested = target_prices[0]
    else:
        zone_low = atr_target
        zone_high = atr_target
        suggested = atr_target

    risk = price - stop
    rr = (suggested - price) / risk if risk > 0 else 0
    first_obstacle = target_prices[0] if target_prices else suggested

    return TargetAnalysis(
        methods=methods,
        confluence_zone=(round(zone_low, 2), round(zone_high, 2)),
        suggested_target=suggested,
        risk_reward=round(rr, 2),
        first_obstacle=round(first_obstacle, 2),
    )


def count_resistance_obstacles(df: pd.DataFrame, price: float, target: float) -> tuple:
    """Count significant resistance levels between current price and target."""
    recent_highs = df["High"].iloc[-60:]
    levels = []
    for i in range(2, len(recent_highs) - 2):
        h = recent_highs.iloc[i]
        if (h > recent_highs.iloc[i-1] and h > recent_highs.iloc[i-2] and
                h > recent_highs.iloc[i+1] and h > recent_highs.iloc[i+2]):
            if price < h < target:
                if not any(abs(h - existing) / existing < 0.01 for existing in levels):
                    levels.append(round(h, 2))
    if price > 5:
        step = 5 if price > 20 else 1
        round_level = (int(price / step) + 1) * step
        while round_level < target:
            if not any(abs(round_level - existing) / existing < 0.02 for existing in levels):
                levels.append(round_level)
            round_level += step
    levels.sort()
    return len(levels), levels


def attach_risk(result, df: pd.DataFrame):
    """Populate stop/target/atr/risk_reward on any PullbackResult or BreakoutResult.

    Returns a new dataclass instance. Safe on near-misses.
    Stop-gte-entry: populates stop and atr, leaves target/rr as None.
    """
    from scanner.strategies.pullback import PullbackResult

    atr_val = float(
        AverageTrueRange(df["High"], df["Low"], df["Close"], 14)
        .average_true_range().iloc[-1]
    )
    ema20 = float(df["Close"].ewm(span=20).mean().iloc[-1])
    price = result.close

    if isinstance(result, PullbackResult):
        stop = round(ema20 - atr_val, 2)
        setup = "PULLBACK"
    else:
        high_20_prev = float(df["High"].iloc[-21:-1].max())
        stop = round(high_20_prev - 0.5 * atr_val, 2)
        setup = "BREAKOUT"

    atr_rounded = round(atr_val, 4)

    if stop >= price:
        return dataclasses.replace(
            result,
            suggested_stop=stop,
            atr=atr_rounded,
            suggested_target=None,
            risk_reward=None,
        )

    targets = compute_targets(df, price, stop, setup, atr_val)
    return dataclasses.replace(
        result,
        suggested_stop=stop,
        suggested_target=targets.suggested_target,
        risk_reward=targets.risk_reward,
        atr=atr_rounded,
    )

"""
Liquidity-risk metrics, path-deficit formulations, and relative drawdown proxies.

Scope & Financial Contracts:
1. Relative Path-Drawdown Proxy:
   When opening balance B_0 and statutory reserve threshold R are unavailable
   (as in offline transaction dataset evaluation), the supported metric is:
       relative_path_drawdown_proxy = max_{h=1..H} max(0, sum_{i=1}^h (withdrawals_i - deposits_i))
   This measures maximum cumulative net cash outflow over the horizon. It is a
   relative drawdown proxy, NOT an actual liquidity shortfall, reserve breach,
   or probability of insolvency.

2. Actual Reserve Deficit:
   When opening cash balance B_0 and policy threshold R are authorized and supplied:
       B_h = B_0 + sum_{i=1}^h (deposits_i - withdrawals_i)
       deficit_h = max(0, R - B_h)
       maximum_path_deficit = max_{h=1..H} deficit_h

3. Path Envelope vs Marginal Intervals:
   Adding independent marginal interval bounds across lead times produces an
   overly conservative, path-inconsistent envelope that assumes worst-case errors
   occur simultaneously at every hour.
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np


def compute_relative_path_drawdown_proxy(
    net_flows: Optional[Union[List[float], np.ndarray]] = None,
    deposits: Optional[Union[List[float], np.ndarray]] = None,
    withdrawals: Optional[Union[List[float], np.ndarray]] = None,
    horizon: int = 72,
) -> float:
    """
    Calculate maximum relative cumulative net outflow (path drawdown proxy) over horizon:
        D_H = max_{h=1..H} max(0, sum_{i=1}^h (withdrawals_i - deposits_i))
            = max_{h=1..H} max(0, - sum_{i=1}^h net_flow_i)

    Accepts either signed net_flows (positive=deposits, negative=withdrawals)
    or separate deposits and withdrawals sequences.

    Returns non-negative drawdown in currency units (USD/INR).
    """
    if net_flows is not None:
        flows = np.asarray(net_flows, dtype=float)[:horizon]
    elif deposits is not None and withdrawals is not None:
        dep = np.asarray(deposits, dtype=float)[:horizon]
        wdr = np.asarray(withdrawals, dtype=float)[:horizon]
        if len(dep) != len(wdr):
            raise ValueError(f"Length mismatch: deposits {len(dep)} vs withdrawals {len(wdr)}")
        flows = dep - wdr
    else:
        raise ValueError("Must provide either net_flows or both deposits and withdrawals.")

    if len(flows) == 0:
        return 0.0

    cumulative_net = np.cumsum(flows)
    min_position = float(np.min(cumulative_net))
    return float(max(0.0, -min_position))


def compute_batch_path_drawdown_proxies(
    net_flows_batch: np.ndarray,
    horizons: List[int] = [6, 24, 48, 72],
) -> Dict[int, np.ndarray]:
    """
    Vectorized computation of path drawdown proxies across a batch of paths.
    net_flows_batch: shape (N_samples, H_steps)
    Returns: Dict mapping horizon H -> array of shape (N_samples,)
    """
    arr = np.asarray(net_flows_batch, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    cum_flows = np.cumsum(arr, axis=1)  # shape (N, H)
    results = {}
    for h in horizons:
        sub_cum = cum_flows[:, :h]
        min_pos = np.min(sub_cum, axis=1)  # shape (N,)
        drawdowns = np.maximum(0.0, -min_pos)
        results[h] = drawdowns
    return results


def compute_actual_path_deficit(
    balance_0: float,
    reserve_threshold: float,
    deposits: Union[List[float], np.ndarray],
    withdrawals: Union[List[float], np.ndarray],
    horizon: int = 72,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Calculate actual reserve deficit path when opening cash balance B_0 and
    policy threshold R are authorized:
        B_h = B_0 + sum_{i=1}^h (deposits_i - withdrawals_i)
        deficit_h = max(0, R - B_h)
        maximum_path_deficit = max_{h=1..H} deficit_h

    Returns:
        (balance_path, deficit_path, maximum_path_deficit)
    """
    if balance_0 < 0.0:
        raise ValueError(f"Opening balance B_0 must be non-negative, got {balance_0}")
    if reserve_threshold < 0.0:
        raise ValueError(f"Reserve threshold R must be non-negative, got {reserve_threshold}")

    dep = np.asarray(deposits, dtype=float)[:horizon]
    wdr = np.asarray(withdrawals, dtype=float)[:horizon]
    if len(dep) != len(wdr):
        raise ValueError(f"Length mismatch: deposits {len(dep)} vs withdrawals {len(wdr)}")
    if len(dep) == 0:
        return np.array([balance_0]), np.array([0.0]), 0.0

    net_flows = dep - wdr
    balance_path = balance_0 + np.cumsum(net_flows)
    deficit_path = np.maximum(0.0, reserve_threshold - balance_path)
    max_deficit = float(np.max(deficit_path))

    return balance_path, deficit_path, max_deficit


def compute_marginal_sum_envelope(
    net_lower: Union[List[float], np.ndarray],
    horizon: int = 72,
) -> float:
    """
    Compute cumulative drawdown envelope obtained by summing marginal lower bounds:
        E_H = max_{h=1..H} max(0, sum_{i=1}^h - net_lower_i)
    where net_lower_i = deposits_lower_i - withdrawals_upper_i.

    Demonstrates the conservative planning heuristic used in treasury.py:reserve_plan.
    Note: This is an upper bound envelope, NOT a calibrated path probability.
    """
    lowers = np.asarray(net_lower, dtype=float)[:horizon]
    if len(lowers) == 0:
        return 0.0

    # Accumulate worst-case marginal net flows
    cumulative_worst = np.cumsum(lowers)
    min_worst = float(np.min(cumulative_worst))
    return float(max(0.0, -min_worst))


# Backward-compatible aliases
def compute_cumulative_path_deficit(
    net_flows: Union[List[float], np.ndarray],
) -> np.ndarray:
    """
    Compute cumulative net position path from signed hourly flows.
    Returns array of cumulative net positions: C_t = sum_{i=1}^t flow_i.
    """
    flows = np.asarray(net_flows, dtype=float)
    return np.cumsum(flows)


def compute_max_path_deficit(
    net_flows: Union[List[float], np.ndarray],
    horizon: int = 72,
) -> float:
    """Legacy wrapper for compute_relative_path_drawdown_proxy."""
    return compute_relative_path_drawdown_proxy(net_flows=net_flows, horizon=horizon)


def evaluate_horizons_deficit(
    net_flows: Union[List[float], np.ndarray],
    horizons: List[int] = [6, 24, 48, 72],
) -> Dict[int, float]:
    """Calculate maximum cumulative drawdown proxy for each investment horizon."""
    flows = np.asarray(net_flows, dtype=float)
    results = {}
    for h in horizons:
        results[h] = compute_relative_path_drawdown_proxy(net_flows=flows, horizon=h)
    return results

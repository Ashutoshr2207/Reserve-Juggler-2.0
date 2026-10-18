"""
Empirical paired-trajectory scenario simulation for cumulative path risk.

Methodology:
1. Aligned Residual Trajectory Pairing:
   Out-of-sample calibration predictions on August (N=673) generate paired
   residual trajectories:
       e_{t, dep, h} = y_{t, dep, h} - y_hat_{t, dep, h}
       e_{t, wdr, h} = y_{t, wdr, h} - y_hat_{t, wdr, h}
   for each origin t in August across all 72 lead times h in 1..72.

2. Joint Dependency Preservation:
   Pairing deposit and withdrawal residual trajectories simultaneously preserves:
   - Cross-sectional correlation between gross receipts and disbursements.
   - Within-path temporal autocorrelation across forecast horizons 1..72.

3. Simulation & Quantile Estimation:
   Given new point forecasts (y_hat_{dep}, y_hat_{wdr}):
       y_tilde_{dep}^{(k)} = max(0.0, y_hat_{dep} + e_{k, dep})
       y_tilde_{wdr}^{(k)} = max(0.0, y_hat_{wdr} + e_{k, wdr})
   Simulated path drawdown proxy for horizon H:
       D_H^{(k)} = max_{1 <= h <= H} max(0, sum_{i=1}^h (y_tilde_{wdr, i}^{(k)} - y_tilde_{dep, i}^{(k)}))
   Yields empirical scenario distribution {D_H^{(1)}, ..., D_H^{(N)}} from which
   mean, standard deviation, and path-risk quantiles (q50, q90, q95, q99) are estimated.

4. Methodological Disclaimer:
   Rolling origins overlap in time; residual trajectories exhibit serial dependence.
   Reported quantiles represent empirical scenario distributions, NOT an exact
   finite-sample exchangeable conformal coverage guarantee.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class PairedTrajectoryScenarioCalibrator:
    """
    Lead-time paired residual trajectory calibrator for joint path-risk simulation.
    """

    def __init__(
        self,
        horizon_hours: int = 72,
        min_samples: int = 30,
        model_name: str = "Forecaster",
        quantile_method: str = "linear",
    ):
        self.horizon_hours = horizon_hours
        self.min_samples = min_samples
        self.model_name = model_name
        self.quantile_method = quantile_method

        self.is_fitted_: bool = False
        self.sample_count_: int = 0
        self.dep_residuals_: Optional[np.ndarray] = None  # shape (N, H)
        self.wdr_residuals_: Optional[np.ndarray] = None  # shape (N, H)
        self.warnings_: List[str] = []

    def fit(
        self,
        y_true_dep: np.ndarray,
        y_pred_dep: np.ndarray,
        y_true_wdr: np.ndarray,
        y_pred_wdr: np.ndarray,
    ) -> "PairedTrajectoryScenarioCalibrator":
        """
        Fit joint residual trajectories on out-of-sample calibration predictions.
        All inputs must be 2D arrays of shape (N_samples, H_steps).
        """
        t_dep = np.asarray(y_true_dep, dtype=float)
        p_dep = np.asarray(y_pred_dep, dtype=float)
        t_wdr = np.asarray(y_true_wdr, dtype=float)
        p_wdr = np.asarray(y_pred_wdr, dtype=float)

        for name, arr in [("y_true_dep", t_dep), ("y_pred_dep", p_dep),
                          ("y_true_wdr", t_wdr), ("y_pred_wdr", p_wdr)]:
            if arr.ndim != 2:
                raise ValueError(f"{name} must be 2D array (N, H), got shape {arr.shape}")

        if not (t_dep.shape == p_dep.shape == t_wdr.shape == p_wdr.shape):
            raise ValueError(
                f"Shape mismatch: {t_dep.shape}, {p_dep.shape}, {t_wdr.shape}, {p_wdr.shape}"
            )

        n_samples, horizon = t_dep.shape
        if n_samples < self.min_samples:
            raise ValueError(
                f"Insufficient calibration samples: required at least {self.min_samples}, got {n_samples}"
            )
        if horizon < self.horizon_hours:
            raise ValueError(
                f"Horizon mismatch: required at least {self.horizon_hours} steps, got {horizon}"
            )

        e_dep = t_dep[:, :self.horizon_hours] - p_dep[:, :self.horizon_hours]
        e_wdr = t_wdr[:, :self.horizon_hours] - p_wdr[:, :self.horizon_hours]

        if np.isnan(e_dep).any() or np.isnan(e_wdr).any():
            raise ValueError("Calibration residuals contain NaN values.")

        self.sample_count_ = n_samples
        self.dep_residuals_ = e_dep
        self.wdr_residuals_ = e_wdr
        self.is_fitted_ = True
        self.warnings_ = []

        return self

    def simulate_scenarios(
        self,
        point_dep: np.ndarray,
        point_wdr: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simulate joint 72-hour trajectories under paired calibration scenarios:
            y_tilde_{dep}^{(k)} = max(0.0, point_dep + e_{k, dep})
            y_tilde_{wdr}^{(k)} = max(0.0, point_wdr + e_{k, wdr})

        Returns:
            (sim_dep, sim_wdr): each shape (N_scenarios, H_steps)
        """
        if not self.is_fitted_:
            raise RuntimeError("Calibrator must be fitted before calling simulate_scenarios().")

        p_dep = np.asarray(point_dep, dtype=float)[:self.horizon_hours]
        p_wdr = np.asarray(point_wdr, dtype=float)[:self.horizon_hours]

        if len(p_dep) < self.horizon_hours or len(p_wdr) < self.horizon_hours:
            raise ValueError(
                f"Point forecasts must have at least {self.horizon_hours} steps"
            )

        # Broadcast across N scenarios: shape (N, H)
        sim_dep = np.maximum(0.0, p_dep[np.newaxis, :] + self.dep_residuals_)
        sim_wdr = np.maximum(0.0, p_wdr[np.newaxis, :] + self.wdr_residuals_)

        return sim_dep, sim_wdr

    def predict_path_risk(
        self,
        point_dep: np.ndarray,
        point_wdr: np.ndarray,
        horizons: List[int] = [6, 24, 48, 72],
        quantiles: List[float] = [0.50, 0.90, 0.95, 0.99],
    ) -> Dict[int, Dict[str, Any]]:
        """
        Evaluate path-risk metrics and quantiles across specified horizons.
        Returns dict keyed by horizon H containing:
            - point_drawdown: deterministic plug-in drawdown proxy from point forecasts
            - mean_flow_drawdown: drawdown functional applied to mean simulated flow trajectory
            - mean_drawdown: average simulated drawdown across scenarios (>= mean_flow_drawdown by Jensen)
            - std_drawdown: standard deviation across scenarios
            - quantiles: dict of requested quantile levels -> simulated drawdown values
        """
        sim_dep, sim_wdr = self.simulate_scenarios(point_dep, point_wdr)

        p_dep = np.asarray(point_dep, dtype=float)[:self.horizon_hours]
        p_wdr = np.asarray(point_wdr, dtype=float)[:self.horizon_hours]
        point_net_flows = p_dep - p_wdr

        # Mean simulated flow trajectory after residual addition and non-negative clipping
        mean_sim_dep = np.mean(sim_dep, axis=0)
        mean_sim_wdr = np.mean(sim_wdr, axis=0)
        mean_sim_net_flows = mean_sim_dep - mean_sim_wdr

        # Simulated net flows: shape (N, H)
        sim_net_flows = sim_dep - sim_wdr
        sim_cum_net = np.cumsum(sim_net_flows, axis=1)  # shape (N, H)

        results = {}
        for h in horizons:
            # 1. Point forecast drawdown (plug-in)
            sub_point_cum = np.cumsum(point_net_flows[:h])
            point_dd = float(max(0.0, -np.min(sub_point_cum)))

            # 2. Drawdown of mean simulated flow trajectory: g(mean(X_sim))
            # By Jensen's inequality for convex functional g, E[g(X)] >= g(E[X]).
            # Therefore, mean_drawdown >= mean_flow_drawdown mathematically holds.
            sub_mean_sim_cum = np.cumsum(mean_sim_net_flows[:h])
            mean_flow_dd = float(max(0.0, -np.min(sub_mean_sim_cum)))

            # 3. Scenario drawdowns: for each scenario k, max_{1<=i<=h} max(0, -cumsum_i)
            sub_sim_cum = sim_cum_net[:, :h]
            scenario_min_pos = np.min(sub_sim_cum, axis=1)  # shape (N,)
            scenario_drawdowns = np.maximum(0.0, -scenario_min_pos)

            mean_dd = float(np.mean(scenario_drawdowns))
            std_dd = float(np.std(scenario_drawdowns, ddof=1)) if len(scenario_drawdowns) > 1 else 0.0

            q_dict = {}
            for q in quantiles:
                q_val = float(np.quantile(scenario_drawdowns, q, method=self.quantile_method))
                q_dict[q] = q_val

            results[h] = {
                "point_drawdown": point_dd,
                "mean_flow_drawdown": mean_flow_dd,
                "mean_drawdown": mean_dd,
                "std_drawdown": std_dd,
                "quantiles": q_dict,
            }

        return results

    def to_dict(self) -> Dict[str, Any]:
        """Serialize calibrator state to dictionary."""
        if not self.is_fitted_:
            return {"is_fitted": False}

        return {
            "is_fitted": True,
            "horizon_hours": self.horizon_hours,
            "min_samples": self.min_samples,
            "sample_count": self.sample_count_,
            "model_name": self.model_name,
            "quantile_method": self.quantile_method,
            "warnings": self.warnings_,
            "dep_residuals": self.dep_residuals_.tolist(),
            "wdr_residuals": self.wdr_residuals_.tolist(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PairedTrajectoryScenarioCalibrator":
        """Deserialize calibrator from dictionary."""
        calibrator = cls(
            horizon_hours=data["horizon_hours"],
            min_samples=data.get("min_samples", 30),
            model_name=data.get("model_name", "Forecaster"),
            quantile_method=data.get("quantile_method", "linear"),
        )
        if not data.get("is_fitted", False):
            return calibrator

        calibrator.sample_count_ = data["sample_count"]
        calibrator.dep_residuals_ = np.array(data["dep_residuals"], dtype=float)
        calibrator.wdr_residuals_ = np.array(data["wdr_residuals"], dtype=float)
        calibrator.warnings_ = data.get("warnings", [])
        calibrator.is_fitted_ = True
        return calibrator

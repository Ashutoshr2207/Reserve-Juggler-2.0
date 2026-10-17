"""Deterministic, time-ordered INR planning for an Indian banking demo."""

import copy
import math
from datetime import datetime, timedelta, timezone

OPTIONS = [
    {
        "id": "flex",
        "name": "Intraday treasury placement (demo)",
        "hours": 6,
        "rate": 4.0,
        "minimum": 250_000,
        "fee": 20,
        "penalty": "No early redemption",
    },
    {
        "id": "overnight",
        "name": "Overnight treasury deposit (demo)",
        "hours": 24,
        "rate": 5.0,
        "minimum": 500_000,
        "fee": 50,
        "penalty": "No early redemption",
    },
    {
        "id": "extended",
        "name": "48-hour treasury deposit (demo)",
        "hours": 48,
        "rate": 5.4,
        "minimum": 1_000_000,
        "fee": 100,
        "penalty": "No early redemption",
    },
]


def moment(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone.")
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def inr(value):
    whole, fraction = f"{abs(value):.2f}".split(".")
    tail = whole[-3:]
    head = whole[:-3]
    groups = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    grouped = ",".join(groups + [tail])
    return f"{'−' if value < 0 else ''}₹{grouped}.{fraction}"


def amount(value, maximum=1e10):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Amount must be numeric.")
    if not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"Amount must be finite and between zero and {maximum:g}.")
    return round(value, 2)


def configuration(state):
    return {
        "risk_buffer": 5_000_000,
        "option": "overnight",
        **state.get("planning_policy", {}),
    }


def scheduled(state):
    if "scheduled" in state:
        return copy.deepcopy(state["scheduled"])
    now = moment(state["history"][-1]["timestamp"])
    return [
        {
            "id": "demo-payout",
            "kind": "payment",
            "amount": 70_000_000,
            "timestamp": iso(now + timedelta(hours=6)),
            "label": "RTGS customer payment / NEFT salary obligation",
        },
        {
            "id": "demo-settlement",
            "kind": "settlement",
            "amount": 40_000_000,
            "timestamp": iso(now + timedelta(hours=7)),
            "label": "Confirmed UPI merchant settlement receipt",
        },
    ]


def timeline(state, stress=None, forecast_rows=None):
    """Withdrawals precede receipts at equal timestamps; no future netting."""
    stress = stress or {}
    withdrawal_pct = amount(stress.get("withdrawals", 0), 100)
    upi_pct = amount(stress.get("upi", 0), 100)
    delay = amount(stress.get("delay", 0), 48)
    payout = amount(stress.get("payout", 0))
    now = moment(state["history"][-1]["timestamp"])
    end = now + timedelta(hours=72)
    profiles = {h: [] for h in range(24)}
    for row in state["history"][-336:]:
        profiles[moment(row["timestamp"]).hour].append(row)
    transactions = []
    predictions = {r["timestamp"]: r for r in forecast_rows or []}
    uncertainty_squared = uncertainty_total = 0.0
    for i in range(1, 73):
        due = now + timedelta(hours=i)
        sample = profiles[due.hour]
        deposits = round(sum(r["deposits"] for r in sample) / len(sample), 2)
        withdrawals = round(
            sum(r["withdrawals"] for r in sample)
            / len(sample)
            * (1 + withdrawal_pct / 100),
            2,
        )
        prediction = predictions.get(iso(due))
        if prediction:
            # Gross hourly seasonal profiles plus a net-model correction. This
            # reconciles the timed path to the existing forecast without adding
            # forecast net flows a second time.
            base_withdrawals = withdrawals / (1 + withdrawal_pct / 100)
            # Extreme negative forecasts must remain representable without
            # inventing deposits when the forecast exceeds the gross profile.
            base_withdrawals = max(base_withdrawals, -prediction["mean"])
            withdrawals = round(base_withdrawals * (1 + withdrawal_pct / 100), 2)
            deposits = round(max(0, base_withdrawals + prediction["mean"]), 2)
            uncertainty_squared += max(0, prediction["mean"] - prediction["lower"]) ** 2
            allowance = math.sqrt(uncertainty_squared)
            transactions.append(
                {
                    "timestamp": iso(due),
                    "kind": "uncertainty",
                    "flow": -(allowance - uncertainty_total),
                    "label": "Root-sum-square forecast uncertainty allowance",
                }
            )
            uncertainty_total = allowance
        merchant = round(deposits * 0.08, 2)
        for kind, value, when in [
            ("UPI", -round(withdrawals * 0.45 * (1 + upi_pct / 100), 2), due),
            ("IMPS", -round(withdrawals * 0.20, 2), due),
            ("NEFT", -round(withdrawals * 0.20, 2), due),
            ("RTGS", -round(withdrawals * 0.10, 2), due),
            (
                "ATM",
                -(
                    withdrawals
                    - round(withdrawals * 0.45, 2)
                    - 2 * round(withdrawals * 0.20, 2)
                    - round(withdrawals * 0.10, 2)
                ),
                due,
            ),
            ("deposit", deposits - merchant, due),
            ("settlement", merchant, due + timedelta(hours=delay)),
        ]:
            transactions.append(
                {
                    "timestamp": iso(when),
                    "kind": kind,
                    "flow": value,
                    "label": (
                        f"Expected {kind} outflow"
                        if kind in ("UPI", "IMPS", "NEFT", "RTGS", "ATM")
                        else "NEFT / IMPS expected deposit"
                        if kind == "deposit"
                        else "UPI merchant settlement"
                    ),
                }
            )
    events = scheduled(state)
    if payout:
        events.append(
            {
                "id": "stress-payout",
                "kind": "payment",
                "amount": payout,
                "timestamp": iso(now + timedelta(hours=6)),
                "label": "Scenario additional payout",
            }
        )
    for event in events:
        when = moment(event["timestamp"])
        if event["kind"] == "settlement":
            when += timedelta(hours=delay)
        if when <= now:
            continue
        sign = 1 if event["kind"] in ("deposit", "settlement") else -1
        transactions.append(
            {
                "timestamp": iso(when),
                "kind": event["kind"],
                "flow": sign * event["amount"],
                "label": event["label"],
                "id": event["id"],
            }
        )
    # Existing sweep maturities are contractual inflows, never liquid before due.
    for tranche in state["tranches"]:
        when = moment(tranche["matures"])
        if when > now:
            earned = round(
                tranche["amount"]
                * tranche["annual_yield"]
                / 100
                * tranche["hours"]
                / (365 * 24),
                2,
            )
            transactions.append(
                {
                    "timestamp": iso(when),
                    "kind": "maturity",
                    "flow": tranche["amount"] + earned,
                    "label": "Contractual vault maturity",
                }
            )
    return sorted(
        [t for t in transactions if moment(t["timestamp"]) <= end],
        key=lambda t: (moment(t["timestamp"]), t["flow"] >= 0),
    )


def evaluate(cash, transactions, floor, duration, rate=0, fee=0, minimum=0, now=None):
    """Maximum safe principal; protect every due time including maturity ties."""
    now = now or moment(transactions[0]["timestamp"]) - timedelta(hours=1)
    maturity = now + timedelta(hours=duration)
    cumulative = lowest = locked_lowest = 0.0
    for transaction in sorted(
        transactions, key=lambda t: (moment(t["timestamp"]), t["flow"] >= 0)
    ):
        cumulative += transaction["flow"]
        lowest = min(lowest, cumulative)
        # At maturity, obligations are processed before redemption conservatively.
        if moment(transaction["timestamp"]) <= maturity:
            locked_lowest = min(locked_lowest, cumulative)
    required = math.ceil((floor - locked_lowest) * 100) / 100
    eligible = math.floor(max(0, cash - required - fee) * 100) / 100
    baseline_gap = max(0, floor - (cash + lowest))
    if baseline_gap or cash + lowest - fee < floor:
        eligible = 0
    interest = round(eligible * rate / 100 * duration / (365 * 24), 2)
    if eligible < minimum or interest <= fee:
        suggested = 0.0
    else:
        suggested = eligible
    fee_gap = max(0, floor - (cash + lowest - fee))
    reason = (
        "Investment stopped: cash cannot protect all payment times and the reserve."
        if baseline_gap or fee_gap
        else "Investment rejected: below minimum or earnings do not cover fees."
        if not suggested
        else "Approved: cash protects each due time throughout the investment lock."
    )
    return {
        "required": required,
        "available_cash": cash,
        "protected_floor": floor,
        "projected_minimum": round(cash + lowest, 2),
        "minimum_during_lock_after_sweep": round(
            cash - suggested - (fee if suggested else 0) + locked_lowest, 2
        ),
        "emergency_funding": round(baseline_gap, 2),
        "eligible": eligible,
        "suggested": suggested,
        "shortfall": round(baseline_gap, 2),
        "interest": interest if suggested else 0,
        "net_return": round(interest - fee, 2) if suggested else 0,
        "matures": iso(maturity),
        "fee": fee,
        "reason": reason,
        "risk": "High Risk" if baseline_gap else "Warning" if not suggested else "Safe",
    }


def analyze(state, stress=None, forecast_rows=None):
    from liquidity_forecasting.treasury import forecast

    settings = configuration(state)
    if forecast_rows is None:
        rows, model, converged, _ = forecast(state)
    else:
        rows, model, converged = forecast_rows, "Evaluation forecast", False
    combined = dict(stress or {})
    execution = combined.get("execution", "success")
    if execution not in ("success", "failure", "timeout"):
        raise ValueError("Execution must be success, failure, or timeout.")
    combined["withdrawals"] = max(
        amount(combined.get("withdrawals", 0), 100),
        state["policy"]["withdrawal_stress"],
    )
    transactions = timeline(state, combined, rows)
    floor = state["policy"]["minimum_buffer"] + settings["risk_buffer"]
    now = moment(state["history"][-1]["timestamp"])
    options = [
        {
            **option,
            "rate": settings.get("rates", {}).get(option["id"], option["rate"]),
            **evaluate(
                state["cash"],
                transactions,
                floor,
                option["hours"],
                settings.get("rates", {}).get(option["id"], option["rate"]),
                option["fee"],
                option["minimum"],
                now,
            ),
        }
        for option in OPTIONS
    ]
    if execution != "success":
        for option in options:
            option.update(
                suggested=0,
                interest=0,
                net_return=0,
                risk="High Risk" if option["shortfall"] else "Warning",
                reason=f"Deferred: hypothetical execution {execution}; cash retained.",
                minimum_during_lock_after_sweep=round(
                    state["cash"] - option["required"] + floor, 2
                ),
            )
    selected = next(o for o in options if o["id"] == settings["option"])
    best = max(options, key=lambda o: (o["net_return"], -o["hours"]))
    balance = state["cash"]
    points = []
    for transaction in transactions:
        balance = round(balance + transaction["flow"], 2)
        points.append(
            {
                **transaction,
                "balance": balance,
                "status": "High Risk"
                if balance < 0
                else "Warning"
                if balance < floor
                else "Safe",
            }
        )
    pending = [
        {
            **e,
            "status": next(
                (p["status"] for p in points if p.get("id") == e["id"]), "Safe"
            ),
        }
        for e in scheduled(state)
    ]
    return {
        "policy": settings,
        "floor": floor,
        "options": options,
        "selected": selected,
        "optimized": best,
        "projected_minimum": min([state["cash"]] + [p["balance"] for p in points]),
        "locked_principal": sum(t["amount"] for t in state["tranches"]),
        "forecast_model": model,
        "forecast_converged": converged,
        "timeline": points,
        "events": pending,
        "method": (
            "SARIMAX/fallback net forecast reconciled to gross hourly profiles; "
            "root-sum-square uncertainty allowance (uncorrelated-error assumption); "
            "outflows before same-time receipts"
        ),
        "note": (
            "Demo outflows: UPI 45%, IMPS 20%, NEFT 20%, RTGS 10%, ATM 5%. "
            "8% of deposits are merchant receipts. No double counting."
            " Uncertainty is a planning heuristic, not a calibrated path guarantee; "
            "correlated errors require additional risk buffers and stress testing."
        ),
    }


def apply_planning(state, action, payload):
    """Mutate only a transactional copy provided by the treasury service."""
    from liquidity_forecasting.treasury import event

    before = analyze(state)
    state.setdefault("scheduled", scheduled(state))
    if action == "planning_policy":
        option = payload.get("option")
        if option not in {o["id"] for o in OPTIONS}:
            raise ValueError("Select a known investment option.")
        if not isinstance(payload.get("rates", {}), dict):
            raise ValueError("Illustrative rates must be an object keyed by option.")
        state["planning_policy"] = {
            "option": option,
            "risk_buffer": amount(payload.get("risk_buffer")),
            "rates": {
                o["id"]: amount(
                    payload.get("rates", {}).get(
                        o["id"],
                        configuration(state).get("rates", {}).get(o["id"], o["rate"]),
                    ),
                    20,
                )
                for o in OPTIONS
            },
        }
    elif action == "planning_balance":
        if state["tranches"]:
            raise ValueError(
                "Demo balances cannot change while investments are locked."
            )
        state["cash"] = amount(payload.get("cash"))
        state["vault"] = amount(payload.get("vault"))
        state["policy"]["auto_sweep"] = False
    elif action == "planning_event":
        kind = payload.get("kind")
        if kind not in (
            "withdrawal",
            "payment",
            "deposit",
            "settlement",
            "delay",
            "risk",
        ):
            raise ValueError("Choose a valid event type.")
        hours = amount(payload.get("hours"), 48)
        if not 0 < hours <= 48:
            raise ValueError("Event timing must be greater than zero, up to 48 hours.")
        if kind == "risk":
            state["planning_policy"] = {
                **configuration(state),
                "risk_buffer": amount(payload.get("amount")),
            }
        elif kind == "delay":
            found = False
            for e in state["scheduled"]:
                if e["kind"] == "settlement":
                    e["timestamp"] = iso(
                        moment(e["timestamp"]) + timedelta(hours=hours)
                    )
                    e["label"] = "Delayed merchant receipt"
                    found = True
            if not found:
                raise ValueError("No pending merchant receipt to delay.")
        else:
            value = amount(payload.get("amount"))
            if value <= 0:
                raise ValueError("Event amount must be greater than zero.")
            state["scheduled"].append(
                {
                    "id": f"event-{state['revision']}",
                    "kind": kind,
                    "amount": value,
                    "timestamp": iso(
                        moment(state["history"][-1]["timestamp"])
                        + timedelta(hours=hours)
                    ),
                    "label": f"Simulated unexpected {kind}",
                }
            )
    elif action in ("planning_invest", "planning_optimize"):
        chosen = (
            before["optimized"] if action == "planning_optimize" else before["selected"]
        )
        principal = chosen["suggested"]
        if principal <= 0:
            raise ValueError(chosen["reason"])
        outcome = payload.get("execution", "success")
        if outcome not in ("success", "failure", "timeout"):
            raise ValueError("Execution must be success, failure, or timeout.")
        if outcome != "success":
            event(
                state, "Failed sweep", 0, f"Simulated {outcome}; no funds transferred"
            )
            state.setdefault("decisions", []).insert(
                0,
                {
                    "timestamp": state["history"][-1]["timestamp"],
                    "action": action,
                    "cash": state["cash"],
                    "reserve": chosen["required"],
                    "investment": 0,
                    "reason": (
                        f"Deferred: simulated execution {outcome}; balances unchanged."
                    ),
                    "before": chosen,
                    "after": chosen,
                },
            )
            return
        state["cash"] = round(state["cash"] - principal - chosen["fee"], 2)
        state["vault"] = round(state["vault"] + principal, 2)
        state["tranches"].append(
            {
                "amount": principal,
                "matures": chosen["matures"],
                "annual_yield": chosen["rate"],
                "hours": chosen["hours"],
                "started": state["history"][-1]["timestamp"],
                "fee": chosen["fee"],
                "expected_interest": chosen["interest"],
                "redemption": chosen["penalty"],
            }
        )
        event(state, "Investment", principal, chosen["name"] + ": " + chosen["reason"])
        event(state, "Fee", -chosen["fee"], "Illustrative investment entry fee")
    else:
        raise ValueError("Unknown planning action.")
    after = analyze(state)
    delta = after["selected"]["required"] - before["selected"]["required"]
    trigger = (
        f"{payload.get('kind', 'Event')} simulation changed reserve by {inr(delta)}. "
        if action == "planning_event"
        else "Demo settings recalculated. "
        if action in ("planning_policy", "planning_balance")
        else "Investment simulated; fee charged and principal locked. "
    )
    decision = {
        "timestamp": state["history"][-1]["timestamp"],
        "action": action,
        "cash": state["cash"],
        "reserve": after["selected"]["required"],
        "investment": after["selected"]["suggested"],
        "reason": trigger + after["selected"]["reason"],
        "before": before["selected"],
        "after": after["selected"],
    }
    state.setdefault("decisions", []).insert(0, decision)
    state["decisions"] = state["decisions"][:200]
    event(
        state,
        "Decision",
        after["selected"]["suggested"],
        f"{action}: {after['selected']['reason']}",
    )

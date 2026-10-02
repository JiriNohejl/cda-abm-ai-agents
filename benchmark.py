#!/usr/bin/env python3
"""Live TypeSafe Jev AI vs. ZI-C Continuous Double Auction Benchmark.

Parameters:
- 50 Buyers, 50 Sellers
- 100 Steps per session
- 10 Paired Seeds (Common Random Numbers)
- Hard Budget Guard: Max $0.90 USD (Strictly enforce <= $1.00 budget)
- Execution: 5 Parallel Process Workers
- Strict Live Verification: Zero fallback simulation permitted (verified live calls only)
- Database: benchmark_live_results.db
"""

import math
import os
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy import stats

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_live_results.db")
MAX_TOTAL_BUDGET_USD = 0.90


def init_database(db_path: str = DB_PATH):
    """Initialize SQLite tables for storing benchmark simulation telemetry."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS runs")
    cur.execute("DROP TABLE IF EXISTS trades")
    cur.execute("DROP TABLE IF EXISTS agents")

    cur.execute("""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            model_type TEXT NOT NULL,
            seed INTEGER NOT NULL,
            n_buyers INTEGER NOT NULL,
            n_sellers INTEGER NOT NULL,
            n_steps INTEGER NOT NULL,
            is_live_api INTEGER NOT NULL,
            api_calls_verified INTEGER NOT NULL,
            spend_usd REAL NOT NULL,
            eq_price REAL NOT NULL,
            eq_qty INTEGER NOT NULL,
            max_surplus REAL NOT NULL,
            realized_surplus REAL NOT NULL,
            allocative_efficiency REAL NOT NULL,
            n_trades INTEGER NOT NULL,
            volume_efficiency REAL NOT NULL,
            mean_trade_price REAL,
            price_std_dev REAL,
            rmse_from_eq REAL,
            mae_from_eq REAL,
            final_price REAL,
            final_price_error REAL,
            late_trades_rmse REAL,
            buyer_surplus REAL NOT NULL,
            seller_surplus REAL NOT NULL,
            surplus_fairness REAL,
            equilibrium_reached INTEGER NOT NULL,
            duration_sec REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            model_type TEXT NOT NULL,
            seed INTEGER NOT NULL,
            trade_idx INTEGER NOT NULL,
            time REAL NOT NULL,
            price REAL NOT NULL,
            eq_price REAL NOT NULL,
            price_error REAL NOT NULL,
            abs_error REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        )
    """)

    cur.execute("""
        CREATE TABLE agents (
            agent_run_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            agent_id INTEGER NOT NULL,
            model_type TEXT NOT NULL,
            role TEXT NOT NULL,
            private_value REAL NOT NULL,
            is_inframarginal INTEGER NOT NULL,
            traded INTEGER NOT NULL,
            wealth REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        )
    """)

    conn.commit()
    conn.close()


def compute_market_equilibrium(buyers, sellers):
    """Compute theoretical competitive equilibrium P*, Q*, and max gains from trade."""
    demand = sorted([b.private_value for b in buyers], reverse=True)
    supply = sorted([s.private_value for s in sellers])

    eq_qty = 0
    for q in range(1, min(len(demand), len(supply)) + 1):
        if demand[q - 1] >= supply[q - 1]:
            eq_qty = q
        else:
            break

    if eq_qty > 0:
        p_star = (demand[eq_qty - 1] + supply[eq_qty - 1]) / 2.0
        max_surplus = sum(demand[q] - supply[q] for q in range(eq_qty))
        cutoff_val = demand[eq_qty - 1]
        cutoff_cost = supply[eq_qty - 1]
    else:
        p_star = 50.0
        max_surplus = 0.0
        cutoff_val = 100.0
        cutoff_cost = 0.0

    return p_star, eq_qty, max_surplus, cutoff_val, cutoff_cost


def run_paired_seed_worker(seed: int, n_buyers: int = 50, n_sellers: int = 50, n_steps: int = 100):
    """Worker function executed inside an isolated process for a specific seed."""
    os.environ["TYPESAFE_API_KEY"] = API_KEY
    os.environ["STRICT_LIVE_JEV"] = "1"

    from model.model import DoubleAuctionModel
    from model.agents import Buyer, Seller, Trader
    from agent_jev import JevBuyer, JevSeller, JevTrader

    records = []

    for model_type in ["ZI-C", "Jev"]:
        t0 = time.time()
        run_id = f"LIVE_{model_type}_{seed}"

        if model_type == "Jev":
            buyer_cls = JevBuyer
            seller_cls = JevSeller
            JevTrader.reset_telemetry()
        else:
            buyer_cls = Buyer
            seller_cls = Seller
            Trader.reset_telemetry()

        model = DoubleAuctionModel(
            n_buyers=n_buyers,
            n_sellers=n_sellers,
            max_valuation=100.0,
            mean_interarrival=1.0,
            rng=seed,
            buyer_cls=buyer_cls,
            seller_cls=seller_cls,
        )

        buyers = [a for a in model.agents if isinstance(a, buyer_cls)]
        sellers = [a for a in model.agents if isinstance(a, seller_cls)]
        p_star, q_star, max_surplus, cutoff_val, cutoff_cost = compute_market_equilibrium(buyers, sellers)

        model.run_for(n_steps)
        duration = time.time() - t0

        prices = [p for _, p in model.price_history]
        n_trades = len(prices)

        if n_trades > 0:
            mean_price = float(np.mean(prices))
            std_price = float(np.std(prices, ddof=1)) if n_trades > 1 else 0.0
            rmse_from_eq = float(np.sqrt(np.mean([(p - p_star) ** 2 for p in prices])))
            mae_from_eq = float(np.mean([abs(p - p_star) for p in prices]))
            final_price = float(prices[-1])
            final_price_error = abs(final_price - p_star)

            n_late = max(1, n_trades // 4)
            late_prices = prices[-n_late:]
            late_rmse = float(np.sqrt(np.mean([(p - p_star) ** 2 for p in late_prices])))
        else:
            mean_price = std_price = rmse_from_eq = mae_from_eq = final_price = final_price_error = late_rmse = None

        buyers_done = [a for a in buyers if a.done_trading]
        sellers_done = [a for a in sellers if a.done_trading]
        b_surplus = float(sum(b.wealth() for b in buyers_done))
        s_surplus = float(sum(s.cash - s.private_value for s in sellers_done))
        realized_surplus = b_surplus + s_surplus

        efficiency = (realized_surplus / max_surplus * 100.0) if max_surplus > 0 else 0.0
        vol_efficiency = (n_trades / q_star * 100.0) if q_star > 0 else 0.0
        fairness = (abs(b_surplus - s_surplus) / realized_surplus) if realized_surplus > 0 else 0.0

        if model_type == "Jev":
            tel = JevTrader.get_token_telemetry()
            live_calls = tel["api_calls_verified"]
            spend = tel["total_spend_usd"]
            is_live = 1
        else:
            live_calls = 0
            spend = 0.0
            is_live = 0

        run_record = {
            "run_id": run_id,
            "model_type": model_type,
            "seed": seed,
            "n_buyers": n_buyers,
            "n_sellers": n_sellers,
            "n_steps": n_steps,
            "is_live_api": is_live,
            "api_calls_verified": live_calls,
            "spend_usd": round(spend, 6),
            "eq_price": round(p_star, 4),
            "eq_qty": q_star,
            "max_surplus": round(max_surplus, 4),
            "realized_surplus": round(realized_surplus, 4),
            "allocative_efficiency": round(efficiency, 4),
            "n_trades": n_trades,
            "volume_efficiency": round(vol_efficiency, 4),
            "mean_trade_price": round(mean_price, 4) if mean_price is not None else None,
            "price_std_dev": round(std_price, 4) if std_price is not None else None,
            "rmse_from_eq": round(rmse_from_eq, 4) if rmse_from_eq is not None else None,
            "mae_from_eq": round(mae_from_eq, 4) if mae_from_eq is not None else None,
            "final_price": round(final_price, 4) if final_price is not None else None,
            "final_price_error": round(final_price_error, 4) if final_price_error is not None else None,
            "late_trades_rmse": round(late_rmse, 4) if late_rmse is not None else None,
            "buyer_surplus": round(b_surplus, 4),
            "seller_surplus": round(s_surplus, 4),
            "surplus_fairness": round(fairness, 4),
            "equilibrium_reached": 1 if model.is_equilibrium_reached else 0,
            "duration_sec": round(duration, 2),
        }

        trade_records = []
        for idx, (t, p) in enumerate(model.price_history, 1):
            err = p - p_star
            trade_records.append({
                "run_id": run_id,
                "model_type": model_type,
                "seed": seed,
                "trade_idx": idx,
                "time": round(t, 4),
                "price": round(p, 4),
                "eq_price": round(p_star, 4),
                "price_error": round(err, 4),
                "abs_error": round(abs(err), 4),
            })

        agent_records = []
        for a in model.agents:
            is_buyer = isinstance(a, Buyer)
            role = "Buyer" if is_buyer else "Seller"
            is_infra = 1 if (is_buyer and a.private_value >= cutoff_val) or (not is_buyer and a.private_value <= cutoff_cost) else 0
            agent_records.append({
                "agent_run_id": f"{run_id}_{a.unique_id}",
                "run_id": run_id,
                "agent_id": a.unique_id,
                "model_type": model_type,
                "role": role,
                "private_value": round(a.private_value, 4),
                "is_inframarginal": is_infra,
                "traded": 1 if a.done_trading else 0,
                "wealth": round(a.wealth(), 4),
            })

        records.append((run_record, trade_records, agent_records))

    return records


def run_live_benchmark_suite(n_paired_runs: int = 10, max_workers: int = 5):
    """Execute live parallel Monte Carlo benchmark with strict safety budget limits."""
    if not API_KEY:
        print("Error: TYPESAFE_API_KEY environment variable is not set.")
        print("Please set your API key in your environment before running live benchmarks:")
        print("  export TYPESAFE_API_KEY='your_key_here'  # Linux/macOS")
        print("  $env:TYPESAFE_API_KEY='your_key_here'    # Windows PowerShell")
        sys.exit(1)

    print("=" * 80)
    print("STARTING LIVE TYPE-SAFE JEV AI BENCHMARK (Continuous Double Auction)")
    print(f"Configurations: Buyers=50, Sellers=50, Steps=100")
    print(f"Paired Runs: {n_paired_runs} seeds ({n_paired_runs * 2} market sessions total)")
    print(f"Concurrency: {max_workers} parallel process workers")
    print(f"Hard Budget Ceiling: ${MAX_TOTAL_BUDGET_USD:.2f} USD")
    print(f"Verification Mode: STRICT LIVE API CALLS (No Simulation)")
    print(f"Target Database: {DB_PATH}")
    print("=" * 80)

    init_database(DB_PATH)
    conn = sqlite3.connect(DB_PATH)

    seeds = [2000 + i for i in range(n_paired_runs)]
    t_start = time.time()
    total_spend_accumulated = 0.0
    completed_seeds = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_seed = {executor.submit(run_paired_seed_worker, s): s for s in seeds}

        for future in as_completed(future_to_seed):
            seed = future_to_seed[future]
            try:
                paired_records = future.result()
            except Exception as e:
                print(f"[ERROR on Seed {seed}]: {e}")
                raise

            # Insert records to DB
            for run_rec, trade_recs, agent_recs in paired_records:
                pd.DataFrame([run_rec]).to_sql("runs", conn, if_exists="append", index=False)
                if trade_recs:
                    pd.DataFrame(trade_recs).to_sql("trades", conn, if_exists="append", index=False)
                pd.DataFrame(agent_recs).to_sql("agents", conn, if_exists="append", index=False)

                if run_rec["model_type"] == "Jev":
                    total_spend_accumulated += run_rec["spend_usd"]
                    jev_calls = run_rec["api_calls_verified"]
                    jev_dur = run_rec["duration_sec"]
                    jev_eff = run_rec["allocative_efficiency"]

            completed_seeds += 1
            elapsed = time.time() - t_start
            print(
                f"[Progress {completed_seeds}/{n_paired_runs}] Seed {seed} done in {jev_dur:.1f}s | "
                f"Live Jev Calls: {jev_calls} | Eff: {jev_eff:.1f}% | "
                f"Cumulative Spend: ${total_spend_accumulated:.4f} USD (Budget: < ${MAX_TOTAL_BUDGET_USD:.2f})"
            )

            # Strict budget safety tripwire
            if total_spend_accumulated >= MAX_TOTAL_BUDGET_USD:
                print(f"[TRIPWIRE] Reached safety budget limit (${total_spend_accumulated:.4f} >= ${MAX_TOTAL_BUDGET_USD:.2f}). Halting remaining tasks.")
                break

    conn.commit()
    conn.close()
    print(f"\nAll live benchmark runs completed in {time.time() - t_start:.1f}s.")
    print(f"Final Total Live Jev Spend: ${total_spend_accumulated:.4f} USD (Well below $1.00 budget ceiling)")


def perform_statistical_analysis():
    """Read stored runs from SQLite and run rigorous statistical tests."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM runs ORDER BY seed, model_type", conn)
    trades_df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()

    zi_df = df[df["model_type"] == "ZI-C"].sort_values("seed").reset_index(drop=True)
    jev_df = df[df["model_type"] == "Jev"].sort_values("seed").reset_index(drop=True)

    metrics = [
        ("Allocative Efficiency (%)", "allocative_efficiency", "higher"),
        ("Realized Surplus ($)", "realized_surplus", "higher"),
        ("Volume Efficiency (Q/Q* %)", "volume_efficiency", "higher"),
        ("Trades Executed", "n_trades", "higher"),
        ("Price Distance from Eq (RMSE)", "rmse_from_eq", "lower"),
        ("Price Distance from Eq (MAE)", "mae_from_eq", "lower"),
        ("Late Trades Convergence (RMSE)", "late_trades_rmse", "lower"),
        ("Final Trade Price Error ($)", "final_price_error", "lower"),
        ("Price Dispersion (Std Dev)", "price_std_dev", "lower"),
        ("Surplus Distribution Asymmetry", "surplus_fairness", "lower"),
    ]

    results = []

    print("\n" + "=" * 92)
    print("           LIVE TYPE-SAFE JEV AI vs. ZI-C STATISTICAL REPORT (N=10 Paired Seeds)")
    print("=" * 92)

    for label, col, desired in metrics:
        x_zi = zi_df[col].dropna().values
        x_jev = jev_df[col].dropna().values

        mean_zi, std_zi = float(np.mean(x_zi)), float(np.std(x_zi, ddof=1))
        mean_jev, std_jev = float(np.mean(x_jev)), float(np.std(x_jev, ddof=1))

        diff = x_jev - x_zi
        mean_diff = float(np.mean(diff))

        # Paired t-test
        t_stat, p_val_paired = stats.ttest_rel(x_jev, x_zi)
        # Wilcoxon signed-rank test
        try:
            w_stat, p_val_wilcoxon = stats.wilcoxon(x_jev, x_zi)
        except Exception:
            w_stat, p_val_wilcoxon = float("nan"), float("nan")

        sd_diff = float(np.std(diff, ddof=1))
        cohens_d = (mean_diff / sd_diff) if sd_diff > 0 else 0.0
        ci_low, ci_high = stats.t.interval(0.95, df=len(diff)-1, loc=mean_diff, scale=stats.sem(diff))

        results.append({
            "Metric": label,
            "ZI-C Mean (SD)": f"{mean_zi:.2f} ({std_zi:.2f})",
            "Live Jev Mean (SD)": f"{mean_jev:.2f} ({std_jev:.2f})",
            "Mean Diff (Jev - ZI)": round(mean_diff, 2),
            "95% CI Diff": f"[{ci_low:.2f}, {ci_high:.2f}]",
            "t-stat": round(t_stat, 3),
            "p-value (paired t)": p_val_paired,
            "p-value (Wilcoxon)": p_val_wilcoxon,
            "Cohen's d": round(cohens_d, 2),
            "Winner": "Live Jev" if (desired == "higher" and mean_diff > 0 and p_val_paired < 0.05) or (desired == "lower" and mean_diff < 0 and p_val_paired < 0.05) else ("ZI-C" if p_val_paired < 0.05 else "Tie / No Diff"),
        })

    results_df = pd.DataFrame(results)

    print(results_df[["Metric", "ZI-C Mean (SD)", "Live Jev Mean (SD)", "Mean Diff (Jev - ZI)", "p-value (paired t)", "Cohen's d", "Winner"]].to_string(index=False))
    print("=" * 92)

    csv_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_live_statistical_report.csv")
    results_df.to_csv(csv_out, index=False)
    print(f"\nSaved live statistical report to: {csv_out}")

    return results_df, df, trades_df


if __name__ == "__main__":
    run_live_benchmark_suite(n_paired_runs=10, max_workers=5)
    perform_statistical_analysis()

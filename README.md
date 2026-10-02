# Continuous Double Auction (CDA) AI Market Benchmark

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Mesa ABM](https://img.shields.io/badge/Mesa-ABM%203.5+-brightgreen.svg)](https://github.com/projectmesa/mesa)
[![Tests: 28 Passed](https://img.shields.io/badge/tests-28%20passed-success.svg)](https://pytest.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?hide_repo_select=true&ref=main&repo=JiriNohejl/cda-abm-ai-agents)

> **Does cognitive trader intelligence matter in market microstructure, or does the market institution do all the heavy lifting?**  
> An experimental agent-based computational economics (ACE) testbed comparing canonical **Zero-Intelligence with Constraint (ZI-C)** traders ([Gode & Sunder, 1993](https://doi.org/10.1086/261867)) against **Cognitive LLM Agents** powered by [TypeSafe AI's Jev model](https://typesafe.ai).

---

## ⚡ Key Empirical Finding

Across paired Monte Carlo market simulations under identical Poisson arrival distributions and supply/demand fundamentals:

| Microstructure Metric | ZI-C Baseline (1993) | Cognitive Jev AI | Impact ($\Delta$) | Significance ($p$) | Effect Size ($d$) | Conclusion |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Allocative Efficiency (%)** | 96.99% | **97.11%** | +0.12% | $p = 0.864$ | $d = 0.06$ | **Tie (Institution dominates surplus extraction)** |
| **Price Dispersion ($\sigma_P$)** | 13.40 | **7.66** | **-5.74** | **$p < 0.001$** | **$d = -1.74$** | 🏆 **Jev AI compresses price volatility by 43%** |
| **Distance from Equilibrium (RMSE)** | 13.38 | **8.33** | **-5.05** | **$p = 0.001$** | **$d = -1.49$** | 🏆 **Jev AI cuts pricing error by 38%** |
| **Late Phase Convergence (RMSE)** | 11.40 | **7.27** | **-4.13** | **$p < 0.001$** | **$d = -1.67$** | 🏆 **Jev AI forms a tighter terminal corridor** |

**Takeaway:** The continuous double auction institution alone achieves ~97% allocative efficiency regardless of trader rationality. However, **cognitive AI agents dramatically stabilize price discovery**, eliminating chaotic drift and forming tight equilibrium pricing corridors.

---

## 🚀 Quickstart (3 Ways to Run)

### 1. Interactive Web Interface (Zero Frontend Dependencies)
Launch the lightweight dark-mode dashboard to watch trades, order book depth, and Walrasian supply/demand curves in real time:

```bash
pip install -r requirements.txt
python web_app.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.  
*(Optional: You can paste your TypeSafe API key directly into the web UI header during runtime without saving it to disk.)*

### 2. Run Directly in Cloud via GitHub Codespaces
Click the **Open in GitHub Codespaces** button or press `.` on GitHub. It builds an isolated cloud environment with all dependencies pre-installed and forwards port 8000 to your browser with one click.

### 3. Publication Econometrics Notebook
View or re-run the complete econometric analysis with publication figures:
```bash
jupyter notebook cda_econometrics_analysis.ipynb
```
*(The notebook is pre-rendered with high-resolution plots so you can view it directly on GitHub without running anything!)*

---

## 🧠 Architecture: ZI-C vs. Jev Cognitive Primitives

```
┌────────────────────────────────────────────────────────┐
│         Mesa Continuous Double Auction Engine          │
│   • Poisson Interarrival  • Limit Order Book (LOB)     │
└───────────┬────────────────────────────────┬───────────┘
            │                                │
    ┌───────▼────────┐               ┌───────▼────────┐
    │  ZI-C (1993)   │               │    Jev AI      │
    ├────────────────┤               ├────────────────┤
    │ Uniform random │               │ Inside-Out     │
    │ Bids & Asks    │               │ Probabilistic  │
    │ Zero memory    │               │ Archetypes     │
    └────────────────┘               └────────────────┘
```

- **ZI-C Agents (`model/agents.py`)**: Draw bids $b \sim U[0, v_i]$ and asks $a \sim U[c_i, \text{max\_val}]$. Pure stochastic noise constrained only by budget.
- **Jev AI Agents (`agent_jev.py`)**: Uses TypeSafe AI's Jev model with structured decision primitives (`Score`, `Choice`):
  - **Archetype Sampling**: Evaluates order book state to tactically choose between *Aggressive Taker*, *Queue Competitor*, *Passive Maker*, or *Deep Discount*.
  - **Zero-Token Pre-filtering**: Bypasses AI calls for submarginal valuations ($v_i < P^*$).
  - **LOB Delta-Caching**: Reuses state distribution if book depth hasn't shifted.
  - **Ultra-Lean Footprint**: $\sim 15$ input tokens per decision (outputs are cost-free).

---

## 📁 Repository Structure

```text
├── model/                          # Core Mesa ABM continuous double auction engine
│   ├── agents.py                   # ZI-C Buyer and Seller classes
│   ├── model.py                    # Auction model with Poisson scheduler
│   └── order_book.py               # Limit order book matching engine
├── tests/                          # 28 passing unit & integration tests
├── agent_jev.py                    # Cognitive Jev AI trader implementation & token gating
├── benchmark.py                    # Paired Monte Carlo benchmark & statistical tests
├── benchmark_live_results.db       # Empirical SQLite database (10 paired market runs)
├── benchmark_live_statistical_report.csv # Econometric summary statistics table
├── cda_econometrics_analysis.ipynb # Pre-rendered publication-grade analysis notebook
├── market_ai_presentation.pptx     # 7-slide executive presentation deck
├── web_app.py                      # Real-time web GUI (HTML5 Canvas + Dark Theme)
├── requirements.txt                # Lean Python dependencies
├── .env.example                    # Optional environment variables template
└── README.md
```

---

## 🧪 Testing & Benchmarks

Run the complete test suite:
```bash
pytest -v
```

Re-run the paired Monte Carlo benchmark suite:
```bash
python benchmark.py
```

---

## 📜 References
- **Gode, D. K., & Sunder, S. (1993).** Allocative efficiency of markets with zero-intelligence traders. *Journal of Political Economy*, 101(1), 119-137.
- **Smith, V. L. (1962).** An experimental study of competitive market behavior. *Journal of Political Economy*, 70(2), 111-137.
- **TypeSafe AI.** *Jev Foundation Models for Agentic Decision Primitives*. https://typesafe.ai.

## 📄 License
Licensed under the [MIT License](LICENSE).

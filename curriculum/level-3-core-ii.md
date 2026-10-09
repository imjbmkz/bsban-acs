# Level 3 — Core II

Level 3 turns probability into statistical modeling, which is where data engineering experience
starts paying off: the models get built and also shipped.

| Code | Course | Prereq | Theory | Practice build | Business application | Main resource |
| --- | --- | --- | --- | --- | --- | --- |
| M301 | Multivariable Calculus | M201, M202 | Partial derivatives, gradients, multiple integrals, Lagrange multipliers | Gradient descent from scratch | Constrained budget allocation | MIT OCW 18.02SC |
| M302 | Optimization & Numerical Methods | M301 | Convexity, LP duality, Newton's method, numerical stability | Solver comparison: SciPy vs OR-Tools | Cost minimization under capacity limits | Boyd & Vandenberghe *Convex Optimization* (free), ch. 1–5 |
| S301 | Mathematical Statistics | S201, M301 | Estimators, MLE, sufficiency, likelihood-ratio tests, asymptotics | Derive and code MLEs; bootstrap vs theory | Defending a forecast's error bars to a CFO | Rice *Mathematical Statistics and Data Analysis* |
| S302 | Regression & Linear Models | S301, M202 | OLS, GLMs, diagnostics, interactions, regularization | Pricing or demand model with full diagnostics | Driver analysis: what moves revenue | Gelman et al. *Regression and Other Stories* (free) |
| S303 | Statistical Learning | S302 | Bias–variance, trees, ensembles, SVMs, cross-validation | Churn model with honest validation | Retention budget: who to target and expected ROI | *ISLP* — Intro to Statistical Learning, Python (free) |
| S304 | Time Series & Forecasting | S302 | Stationarity, ARIMA, ETS, hierarchical forecasting | Demand forecast pipeline on Databricks | Inventory and staffing plans | Hyndman *Forecasting: Principles and Practice* (free) |
| C301 | Distributed Data Processing — *test-out* | C202, C203 | Partitioning, shuffles, consistency, stream processing | Databricks certification plus one streaming project | Platform cost/performance trade-offs | Databricks DE Professional cert; *DDIA* part II |
| C302 | Data Products & MLOps | C102, S303 | Model serving, monitoring, drift, feature stores | Deploy S303's churn model with CI/CD and monitoring | Total cost of ownership of an ML product | Huyen *Designing Machine Learning Systems* |
| B301 | Operations Research & Decision Analysis | M302, S201 | LP/IP, queuing, simulation, decision trees | Scheduling or routing optimizer | Warehouse or workforce optimization case | Hillier & Lieberman *Introduction to Operations Research* |
| B302 | Strategy & Consulting Methods | B103, B202 | Competitive analysis, value chains, case frameworks | Market-sizing model + case-interview drills | Full strategy recommendation for a real company | Rumelt *Good Strategy Bad Strategy*; Cosentino *Case in Point* |

**Level 3 exit check:** three portfolio-grade projects (S302, S303, S304), each with a GitHub repo, a
technical write-up and a one-page business memo. These double as job-abroad portfolio pieces.

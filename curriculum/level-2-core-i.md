# Level 2 — Core I

Level 2 is the hardest and most important level: linear algebra and probability are the two subjects
every statistics and CS master's checks first.

| Code | Course | Prereq | Theory | Practice build | Business application | Main resource |
| --- | --- | --- | --- | --- | --- | --- |
| M201 | Calculus II | M102 | Integration techniques, series, Taylor approximation | Approximate functions and compute areas numerically | Present value of cash-flow streams; continuous compounding | OpenStax *Calculus Vol. 2*; MIT 18.01SC |
| M202 | Linear Algebra | M102 | Vectors, matrices, eigenvalues, SVD, projections | Implement least squares and PCA in NumPy | Customer segmentation; portfolio factor exposure | Strang, MIT 18.06; 3Blue1Brown *Essence of Linear Algebra* |
| S201 | Probability Theory | M201 | Random variables, expectation, conditioning, LLN, CLT | Monte Carlo simulator for a business process | Pricing a warranty or insurance product | Harvard Stat 110 (Blitzstein), free lectures + book |
| S202 | Applied Statistical Methods | S101, S201 | ANOVA, chi-square, nonparametric tests, power, multiple testing | Reusable testing library with power calculator | Sample size and test plan for a product launch | Penn State STAT 500 notes (free) |
| C201 | Data Structures & Algorithms | M103, C101 | Big-O, sorting, hashing, trees, graphs, dynamic programming | Solve 60+ problems; build an LRU cache and a graph scheduler | Why a slow job costs money: complexity vs cloud bill | Princeton *Algorithms* (Sedgewick) on Coursera |
| C202 | Database Systems Internals | C103 | Storage, indexing, query optimization, transactions | Build a toy query engine or B-tree index | Choosing an engine for a client's workload | CMU 15-445 (free videos); Kleppmann *DDIA* |
| C203 | Computer Systems & Operating Systems | C101 | Processes, memory, concurrency, file systems, networking | Multithreaded file processor; profile memory use | Right-sizing clusters and instances | *OSTEP* (free book) |
| B201 | Principles of Macroeconomics | B101 | GDP, inflation, interest rates, monetary/fiscal policy | Pull central-bank data and chart a macro dashboard | How rate changes hit a client's demand | CORE Econ; MIT 14.02 |
| B202 | Corporate Finance | B102, M201 | Time value of money, NPV/IRR, WACC, capital budgeting | DCF model in Python and in a spreadsheet | Business case for a data platform investment | Damodaran's free NYU corporate finance course |
| B203 | Marketing Analytics & Experimentation | S101, B101 | Funnels, CLV, attribution, A/B test design | Simulated A/B test with analysis notebook | Go/no-go memo on a campaign | Kohavi et al. *Trustworthy Online Controlled Experiments* |

**Level 2 exit check:** a timed Stat 110 final and an 18.06 final, each at 70% or better. Passing
both puts the theory core of a statistics master's within reach.

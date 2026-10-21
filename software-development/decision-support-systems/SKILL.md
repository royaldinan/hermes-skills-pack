---
name: decision-support-systems
description: "Use when solving MCDM or decision support systems (DSS)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [dss, mcdm, ahp, saw, topsis, weighted-product, colab, decision-making]
---

# Decision Support Systems & Multi-Criteria Decision-Making (MCDM)

## Overview

Multi-Criteria Decision Making (MCDM) evaluates finite candidate alternatives across conflicting quantitative and qualitative criteria. This skill governs solving, verifying, and delivering MCDM pipelines using AHP (Analytic Hierarchy Process) for objective criteria weighting combined with SAW (Simple Additive Weighting), TOPSIS, and WP (Weighted Product) for alternative ranking.

---

## When to Use

Use when:
- Solving candidate selection, vendor evaluation, site selection, or resource allocation problems with multiple criteria.
- Classifying criteria into Cost (lower is better) vs Benefit (higher is better).
- Constructing and validating AHP pairwise comparison matrices (Saaty scale 1-9) with Consistency Ratio ($CR \le 0.10$).
- Implementing SAW, TOPSIS, or WP ranking algorithms in Python, Excel, or interactive notebooks.
- Generating and delivering 1-click Google Colab notebooks or multi-sheet Excel evaluation workbooks.

---

## Core Engineering Workflow

### 1. Rapid Mathematical Execution First
- **Immediate Local Calculation**: When given a candidate evaluation table, compute the mathematical models (AHP weights, CR consistency, normalized scores, and rankings) immediately in Python.
- **Never Block on Web/UI Overhead**: Do not spend turns attempting to scrape login-protected Colab URLs or build complex web interfaces when the user needs direct tabular results. Deliver the rankings and top candidates first.

### 2. Criteria Cost vs Benefit Formalization
- **Benefit Attributes ($B$)**: Higher value is preferred ($r_{ij} = x_{ij} / \max_k x_{kj}$).
  - Typical examples: Test Score, Technical Skill, Experience, Interview Score, Project Success Rate, GPA, Customer Rating.
- **Cost Attributes ($C$)**: Lower value is preferred ($r_{ij} = \min_k x_{kj} / x_{ij}$).
  - Typical examples: Salary expectation, Project cost, Tuition fee, Latency, Defect rate, Commute distance.

### 3. AHP Pairwise Matrix & Consistency Ratio ($CR$)
- Build reciprocal comparison matrix $A = [a_{ij}]$ where $a_{ji} = 1 / a_{ij}$ and $a_{ii} = 1$ using Saaty scale (1=equal, 3=moderate, 5=strong, 7=very strong, 9=extreme).
- Calculate priority vector $W$:
  $$w_i = \frac{1}{n} \sum_{j=1}^n \frac{a_{ij}}{\sum_{k=1}^n a_{kj}}$$
- Verify consistency:
  $$\lambda_{\max} = \frac{1}{n} \sum_{i=1}^n \frac{(A \cdot W)_i}{w_i}, \quad CI = \frac{\lambda_{\max} - n}{n - 1}, \quad CR = \frac{CI}{RI}$$
- Random Index ($RI$): $n=3: 0.58$, $n=4: 0.90$, $n=5: 1.12$, $n=6: 1.24$, $n=7: 1.32$, $n=8: 1.41$.
- **Hard Gate**: If $CR > 0.10$, the matrix is inconsistent and judgments must be revised before proceeding to ranking.

### 4. Ranking Methods Execution

#### Simple Additive Weighting (SAW)
- Normalize decision matrix:
  $$r_{ij} = \begin{cases} \frac{x_{ij}}{\max_i x_{ij}}, & \text{if } j \in \text{Benefit} \\ \frac{\min_i x_{ij}}{x_{ij}}, & \text{if } j \in \text{Cost} \end{cases}$$
- Final Preference Score: $V_i = \sum_{j=1}^n w_j \cdot r_{ij}$.

#### TOPSIS (Similarity to Ideal Solution)
- Vector Normalization: $r_{ij} = \frac{x_{ij}}{\sqrt{\sum_{i=1}^m x_{ij}^2}}$.
- Weighted Normalized Matrix: $y_{ij} = w_j \cdot r_{ij}$.
- Ideal Solutions:
  - $A^+ = (\max y_{ij} \text{ for } B, \min y_{ij} \text{ for } C)$
  - $A^- = (\min y_{ij} \text{ for } B, \max y_{ij} \text{ for } C)$
- Euclidean Distances: $D_i^+ = \sqrt{\sum (y_{ij} - A_j^+)^2}, \quad D_i^- = \sqrt{\sum (y_{ij} - A_j^-)^2}$.
- Relative Closeness: $V_i = \frac{D_i^-}{D_i^+ + D_i^-}$.

### 5. Multi-Artifact Delivery

#### 1-Click Google Colab Link via GitHub Gist
- Avoid headless browser automation on Google Colab (which triggers authentication walls).
- Create a clean `.ipynb` notebook file locally.
- Publish via CLI:
  ```bash
  gh gist create "<path>/notebook.ipynb" --public -d "<Description>"
  ```
- Formulate the direct 1-click Colab URL:
  `https://colab.research.google.com/gist/<username>/<gist_id>`
  Colab opens public Gist notebooks instantly without login or file-upload friction.

#### Multi-Sheet Excel Deliverable
- Use `openpyxl` to generate a structured workbook containing:
  1. `Final Ranking`: Summary table with Top Candidates highlighted.
  2. `Raw Data & Criteria`: Original decision matrix with Cost/Benefit classification.
  3. `AHP Pairwise Matrix`: Raw comparisons, weights, and CI/CR verification.
  4. `SAW Method`: Normalized matrix and weighted sums.
  5. `TOPSIS Method`: Vector normalization, distances ($D^+, D^-$), and relative closeness.

---
name: expert-systems
description: "Use when building or debugging expert system inference."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [expert-systems, inference-engine, rule-based, forward-chaining, backward-chaining, fuzzy-logic, colab]
---

# Expert Systems & Knowledge-Based Inference

## Overview

Expert systems simulate human domain expert reasoning through formal knowledge representation and inference engines. Flawed inference implementations often pass unit tests while harboring severe logical pathologies: artificial confidence saturation, fake multi-cycle reasoning, tie-breaking biases, and unreachable rules.

## When to Use

Use when designing, implementing, auditing, or comparing:
- Rule-Based Expert Systems (RBS)
- Forward Chaining (data-driven reasoning)
- Backward Chaining (goal-driven reasoning)
- Fuzzy Inference Systems (Mamdani & Sugeno)
- Diagnostic support interfaces (Gradio/CLI/web) connected to clinical or technical rule bases
- Deploying expert system notebooks to cloud environments (Google Colab, Jupyter)

---

## Core Engineering Workflow

### 1. Knowledge Base (KB) Formalization
- Define rules with structured condition schemas, not free-text strings that require fragile parsing like `desc.split(" AND ")`.
- Store conditions as typed predicate lists: `[{"var": "fever", "op": ">", "val": 38.0}]` so verification engines can inspect ASTs deterministically.
- Pair every rule with its positive criteria, exclusion criteria (contraindications), and prior specificity rank.

### 2. UI & Schema Parity Verification
- Map every variable evaluated in the knowledge base to an input field in the consumer interface (CLI/web/Gradio).
- **Pitfall**: Missing input fields default to static values, silently muting rules that depend on them (e.g. platelets defaulting to normal disables hemorrhagic fever rules permanently).
- **Resilient Ingestion Schema Normalization**: When rule bases require specialized variables not present in legacy or raw datasets (e.g. clinical rules requiring 41 variables while sample CSVs only supply 17), inject an automated default dictionary (`required_defaults`) at the data ingestion boundary. Auto-fill missing columns with baseline physiological values (normal vitals, absence of acute signs) so the pipeline never raises `KeyError` or halts on older data files.

### 3. Inference Engine Validation Suite
- Always test each engine against multi-symptom profiles that contain conflicting, foreign, or boundary symptoms.
- Ensure confidence and truth degree vary smoothly with symptom intensity rather than locking at 1.0 or 0.0.

### 4. Interactive Notebook & Cloud Runtime Deployment (Google Colab / Jupyter)
- **Never invoke blocking interactive file upload utilities like `google.colab.files.upload()` as an unconditioned fallback**:
  In Google Colab, `google.colab` is always importable, but calling `files.upload()` halts headless and "Run all" execution indefinitely waiting for a button click. When a shared notebook is opened by a different user, in incognito mode, or after a runtime disconnect, `/content/` is empty. The unconditioned `files.upload()` freezes the runtime, causing the notebook to hang and trapping subsequent sessions in a "Resuming execution" reconnect loop.
- **Implement non-blocking dual-mode dataset ingestion**:
  Always check local session storage first (`os.path.exists("dataset.csv")`); if missing, immediately stream the dataset from a remote URL repository (`pd.read_csv(raw_url)`) and save a copy locally, without pausing execution.
- **Avoid silent heavy pip installations in early cells**:
  Executing `subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])` without visible progress conceals multi-hundred-megabyte package downloads (such as Gradio and its dependencies), misleading users into aborting execution. Keep setup cells lean or isolate heavy package installation to the interface cell with visible progress.

### 5. Academic & Benchmark Synthesis Reporting (Notebook Conclusions)
- **Empirical Grounding Over Abstract Praise**:
  Synthesize each method (Rule-Based, Forward Chaining, Backward Chaining, Fuzzy Logic) directly against recorded benchmark metrics: diagnostic accuracy, clinical coverage, and microsecond inference latency.
- **Strict Anti-Slop Academic Writing**:
  Do not use em-dashes (—), en-dashes (–), double-dashes (--), or AI buzzwords (`delve`, `testament`, `pivotal`, `foster`, `leverage`). Use clean punctuation (periods, parentheses, semicolons) and objective technical phrasing.
- **Dual-Surface Delivery (Colab + LMS Plain Text)**:
  Append conclusion markdown cells directly to the `.ipynb` file structure and push to GitHub so Google Colab via GitHub updates immediately without manual re-uploading. Concurrently generate a plain `.txt` file containing the text for direct submission to LMS text areas.

---

## Paradigm Rules & Pitfalls

### 1. Rule-Based Expert Systems (RBS)

- **Calculate dynamic Certainty Factors (CF)**: Never hardcode static confidence values (e.g. `1.0 if len(fired)==1 else 0.88`). Calculate confidence from premise satisfaction ratio:
  ```
  CF = (matched_conditions / rule_condition_count) * (matched_conditions / total_observed_symptoms)
  ```
- **Structure Conflict Resolution**: When multiple rules fire, sort by precondition specificity (number of verified criteria), salience priority, and recency.
- **Check for Unmatched Contradictions**: A patient exhibiting high fever and cough should not receive 100% confidence for Flu if they also present acute abdominal distress or neurological signs. Flag unmodeled symptoms as negative evidence that reduces diagnosis confidence.

### 2. Forward Chaining (Data-Driven)

- **Preserve Working Memory Integrity Across Cycles**:
  - Cycle 1: Abstract raw continuous inputs into categorical facts (e.g. `fever > 38.0` -> assert `hyperthermia`).
  - Cycle 2: Combine base facts into intermediate clinical syndromes (e.g. `hyperthermia` + `severe_cough` -> assert `acute_respiratory_syndrome`).
  - Cycle 3: Derive terminal conclusions ONLY from asserted facts in Working Memory, not by re-evaluating raw patient inputs against flat production rules.
- **Avoid Pseudo-Chaining**: If Cycle 3 directly evaluates raw data inputs against the original rule list, the intermediate cycles are decorative dead code. Every terminal rule must require at least one intermediate fact asserted by a prior cycle.
- **Wrap Multi-Cycle Predicates in Callables (`lambda m: ...`)**: When defining rules in a list of tuples or dictionaries, writing `wm.get("fact")` evaluates the condition eagerly at list definition time before prior cycles have asserted facts into `wm`. Wrap rule preconditions in callable lambdas (`lambda m: m.get("fact")`) evaluated at cycle execution time.
- **Maintain an Execution Trace**: Record the exact premise activations that caused each newly asserted fact per cycle.

### 3. Backward Chaining (Goal-Driven)

- **Evaluate All Candidate Goals in Auto Mode (Avoid First-Hit Bias)**:
  - When running without a specified target hypothesis, test ALL candidate rules in the knowledge base.
  - Collect every goal where `proven == True`.
  - Select the winner using specificity ranking and condition coverage, never the first rule that returns true in dictionary iteration order (which permanently starves downstream rules).
- **Build Full Proof Trees**: Represent the trace as a recursive goal-subgoal tree. When a sub-goal fails, explicitly log the missing condition and observed value to explain refutation.

### 4. Fuzzy Inference Systems (Mamdani)

- **Prevent Membership Saturation (Trapezoidal Plateau Pitfall)**:
  - Wide flat plateaus `[b, c]` in trapezoidal membership functions return `1.0` across broad ranges, causing multiple unrelated diseases to tie at `1.0`.
  - Use triangular, sigmoid, or Gaussian curves for continuous variables where peak severity is distinct, or apply smooth tapering slopes.
- **Avoid Dictionary Insertion Tie-Breaker Bias**:
  - If multiple diseases evaluate to equal maximum membership, standard stable sorting picks whichever disease was defined first in code.
  - Break ties by comparing secondary symptom coverage, overall severity index, or specificity rather than dictionary order.
- **Incorporate Negative Evidence / Differential Penalties**:
  - T-norm minimum conjunction (`min(fever, cough)`) ignores symptoms outside the rule premise.
  - Penalize disease score if prominent contradictory symptoms are present:
    ```
    score[disease] = t_norm_premise * (1.0 - contradiction_penalty)
    ```
- **Do Not Treat Categorical Inputs as Crisp 1.0/0.0**:
  - Grading binary symptoms as crisp `1.0` forces fuzzy `min` operations to hinge entirely on continuous inputs. Scale categorical inputs by confidence or duration when available.

---

## Verification Checklist

Before deploying or submitting any expert system implementation:

1. [ ] Every rule premise variable exists as an explicit interactive input widget.
2. [ ] Modifying symptom sliders produces continuously graded confidence outputs, not fixed 1.0 or 0.95 constants.
3. [ ] Adding contradictory symptoms visibly lowers confidence or shifts the primary diagnosis.
4. [ ] In auto mode, backward chaining tests all hypotheses before resolving the winner.
5. [ ] Forward chaining derives terminal diagnoses strictly from working memory abstractions.
6. [ ] Chained conditions in multi-cycle forward chaining use lazy callable predicates (`lambda m: ...`), not eager list literals.
7. [ ] Tie-breaking logic is deterministic, clinically grounded, and independent of dictionary insertion order.
8. [ ] Standalone test scripts configure non-interactive matplotlib backends (`matplotlib.use('Agg')`) to prevent `plt.show()` from blocking headless execution.
9. [ ] Colab notebooks implement non-blocking data ingestion (check local file, then stream from remote repository), never bare interactive upload prompts.
10. [ ] Academic synthesis and conclusions are grounded in empirical benchmark metrics, follow strict anti-slop rules (no em-dashes, no buzzwords), and are committed/pushed to GitHub for instant Colab reflection alongside a .txt backup.

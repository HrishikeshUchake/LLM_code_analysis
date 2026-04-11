# LLM Code Analysis & Multi-Agent RAG System

This repository provides an automated framework for static code analysis, control flow tracing, and mathematical Big-O complexity prediction of C++ (and MPI) applications. It leverages local Large Language Models (LLMs) like Qwen2.5-Coder through a Retrieval-Augmented Generation (RAG) and multi-agent pipeline executing on an HPC cluster via SLURM.

## Overview

Statically analyzing code for algorithmic complexity line-by-line is challenging for pure LLM generation due to context limitations, logical hallucinations, and complex variable aliasing across basic blocks. 

To solve this, our pipeline:
1. Parses and segments C++ source code into structural blocks.
2. Embeds and queries the blocks using **ChromaDB** in a RAG workflow to maintain context.
3. Solves the Big-O complexity for each line using a **Multi-Agent Decomposition** strategy.
4. Outputs machine-readable, mapped JSON complexities for downstream profiling.

## Multi-Agent Architecture

Asking a single LLM to trace Abstract Syntax Trees (AST), compute mathematical limits, and output strict JSON often leads to format corruption and poor reasoning. We implemented a 3-agent Chain-of-Thought pipeline to explicitly separate these concerns:

### 1. Agent 1: The Tracer (Compiler Engineer)
* **Goal:** Extract control flow and trace dependencies.
* **Function:** Analyzes the raw code block and tracks variable mutations between the current block, previous block outputs (`output_return`), and the next block inputs (`next_input_function`). It explicitly identifies loop bound limits and nesting depth *without* doing any Big-O math.

### 2. Agent 2: The Analyst (Theoretical Computer Scientist)
* **Goal:** Calculate algorithm complexity.
* **Function:** Takes the text trace provided by Agent 1 and performs step-by-step mathematical derivations. It independently analyzes each loop, determines the computational complexity, and rigidly back-substitutes intermediate variables (e.g., `<CALL_VAR...>`) to base control variables like `n` and `p`.

### 3. Agent 3: The Formatter (Strict Data Bot)
* **Goal:** Sanitize and structure the output.
* **Function:** Takes the verbose mathematical reasoning from Agent 2 and strips out all markdown and explanatory prose. It guarantees the output flawlessly matches our `OUT1` to `OUT5` schema to seamlessly integrate into the JSON datastore (`output_4_complexity.json`) without breaking the parsing scripts.

## Repository Structure

* `codes/code_0F/`: Contains the target C++ code (`code_experiment.cpp`) and bash scripts driving the pipeline workflow (`T8_execute_llm_p1.sh`, etc.).
* `codes/code_0F/data_analysis/`: Data output directory where parsed dictionaries, code segments, and the final `output_4_complexity.json` are stored.
* `llm/`: Contains the LLM inferencing logic.
  * `prompt_experiment.py`: Main orchestration script that runs the RAG queries and executes the 3-agent pipeline.
  * `multi_agent_prompts.py`: Contains the carefully tuned system and user prompts used by the Tracer, Analyst, and Formatter.
* `operate_segmentation_data/`: Python scripts for initial data processing.
* `submit_local_llm_pipeline.slurm`: SLURM batch script to queue and execute the LLM workload on HPC GPU partitions.
* `setup_cluster_cache.sh`: Manages high-performance HuggingFace cache routing to Lustre filesystems to avoid quota limits.

## Execution

Ensure the Python virtual environment is successfully created and requirements are installed:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

To run the pipeline and dispatch the LLM predictions to the HPC cluster:
```bash
sbatch submit_local_llm_pipeline.slurm
```

You can monitor the output logs for the Multi-Agent tracking via the active SLURM output:
```bash
tail -f outputs/projectv2_local_llm_<JOB_ID>.out
```
#!/usr/bin/env python3

#TODO: update
"""
Evaluate LLM on complexity prediction task with multi-model support.

Usage:
    # Hugging Face Qwen direct API
    python evaluate_llm.py --provider huggingface --model Qwen/Qwen2.5-72B-Instruct --limit 50
"""

import argparse
import json
import os
import re
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

#---------------------------------------------------------#
# Example
#---------------------------------------------------------#
FEW_SHOT_EXAMPLES = """
Example 1:

INPUT:

control_vars: n, p

source_vars:
<CALL2_VAR6_n> = n*p
<CALL2_VAR4_size> = p

code_lines:
line=9  | depth=0 | code=[LIBRARY_FUNCTION] MPI_Bcast(..., <CALL2_VAR6_n>, ...)
line=10 | depth=0 | code=int <CALL2_VAR17_base> = <CALL2_VAR6_n> / <CALL2_VAR4_size>;
line=11 | depth=0 | code=int <CALL2_VAR18_local_n> = <CALL2_VAR17_base>;
line=12 | depth=0 | code=[LOOP] for (... <CALL2_VAR18_local_n> ...)
line=14 | depth=0 | code=int <CALL2_VAR6_n> = <CALL2_VAR18_local_n>;

output_return:
<CALL1_VAR1_a> = <CALL2_VAR6_n>

next_input_function:
[]

OUTPUT:
OUT1: <CALL2_VAR17_base> = n; <CALL2_VAR18_local_n> = n; <CALL2_VAR6_n> = n;
OUT2: <CALL1_VAR1_a> = n;
OUT3: []
OUT4: 9,12
OUT5: n*p,n


Example 2:

INPUT:

control_vars: n,p

source_vars:
<CALL1_VAR1_start> = n
<CALL1_VAR4_size> = p

code_lines:
line=15 | depth=0 | code=int <CALL1_VAR1_start> = <CALL1_VAR6_n>;
line=16 | depth=0 | code=[LOOP] for (... <CALL1_VAR1_start> ...)
line=18 | depth=0 | code=[LOOP] for (... <CALL1_VAR1_start> ...)
line=23 | depth=1 | code=[LOOP] for (... <CALL1_VAR1_start> ...)
line=27 | depth=2 | code=[LOOP] for (... <CALL1_VAR1_start> ...)

output_return:
[]

next_input_function:
<CALL2_VAR1_a> = <CALL1_VAR6_n>
<CALL2_VAR3_c> = <CALL1_VAR4_size>

OUTPUT:
OUT1: <CALL1_VAR6_n> = n;
OUT2: []
OUT3: <CALL2_VAR1_a> = n; <CALL2_VAR3_c> = p;
OUT4: 16,18,23,27
OUT5: n,n,n,n

Example 3 --- INVALID OUTPUT EXAMPLES (DO NOT DO THIS):

OUT1: <CALL1_VAR7_groups> = 2;   ← constant → REMOVE
OUT1: <CALL1_VAR6_n> = n*p;     ← unchanged → REMOVE

OUT3: <CALL2_VAR2_b> = ;        ← empty → REMOVE
OUT3: <CALL2_VAR3_c> = 2;       ← constant → REMOVE

CORRECT BEHAVIOR:
Only include variables that depend on control_vars AND are meaningful.
"""

#---------------------------------------------------------#
# Prompt engineering 
#---------------------------------------------------------#
SYSTEM_PROMPT = """
You are a static analysis engine for C/C++ code.

Your output is consumed by an automated pipeline.

--------------------------------------------------
CRITICAL OUTPUT RULES (MANDATORY)
--------------------------------------------------

- DO NOT include explanations
- DO NOT include markdown
- DO NOT include comments
- DO NOT include extra text
- DO NOT include labels like "Explanation"
- DO NOT include sentences

- Output ONLY raw values

- If you violate format, the system will fail

--------------------------------------------------
INPUTS
--------------------------------------------------

1. control_vars
- Base symbolic variables (e.g., n, p)

2. source_vars
- Variable definitions:
  <CALLX_VARY_name> = expression

3. code_lines
- line=<number> | depth=<level> | code=<C++ code>
- Tags:
  [LOOP]
  [LIBRARY_FUNCTION]

4. output_return
5. next_input_function

--------------------------------------------------
TASK
--------------------------------------------------

STEP 1 — VARIABLE RESOLUTION
- Resolve variables using source_vars
- Keep ONLY expressions depending on control_vars
- Final expressions MUST use ONLY control_vars

--------------------------------------------------

STEP 2 — OUTPUT RETURN
- Resolve variables
- Keep ONLY if dependent on control_vars

--------------------------------------------------

STEP 3 — NEXT INPUT
- Resolve variables
- Keep ONLY if dependent on control_vars

--------------------------------------------------

STEP 4 — PERFORMANCE (IMPORTANT CHANGE)
- Analyze EACH loop independently
- DO NOT combine nested loops
- DO NOT multiply complexities across lines

Examples:
Two nested loops:
→ return: n, n   (NOT n^2)

--------------------------------------------------

RULES
--------------------------------------------------

- Allowed symbols: control_vars only (n, p, etc.)
- NEVER output <CALL...>
- NEVER output temporary variables
- Simplify expressions:
  n*n → n^2
  (n*p)/p → n

--------------------------------------------------
OUTPUT FORMAT (STRICT)
--------------------------------------------------

OUT1:
<var> = expression

OUT2:
<var> = expression

OUT3:
<var> = expression

OUT4:
line numbers separated by comma

OUT5:
expressions separated by comma

--------------------------------------------------

FINAL RULE:
Return ONLY the output sections.
No explanations. No extra text.
"""

USER_PROMPT_TEMPLATE = """
{examples}

Now analyze the following input.

INPUT:

control_vars: {control_vars}

source_vars: {source_vars}

code_lines: {code_lines}

output_return: {output_return}

next_input_function: {next_input_function}

OUTPUT (strict format - NO EXTRA TEXT):

OUT1:
OUT2:
OUT3:
OUT4:
OUT5:
"""


#---------------------------------------------------------#
# LLM
#---------------------------------------------------------#
# Provider Configuration
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "default_model": "deepseek/deepseek-chat",
    },
    "huggingface": {
        # Direct Hugging Face OpenAI-compatible inference endpoint.
        "base_url": "https://api-inference.huggingface.co/v1",
        "api_key_env": "HF_TOKEN",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
    },
    "ghllm":{
        "base_url": "http://130.83.143.245:18000/v1/",
        "api_key_env": "GHLLM_API_KEY",
        "default_model": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    },
    "local_transformers": {
        "api_key_env": None,
        "default_model": "Qwen/Qwen2.5-Coder-32B-Instruct",
    }
}

# LLM Client
@dataclass
class Config:
    provider: str      = "huggingface"
    model: str         = "Qwen/Qwen2.5-72B-Instruct"
    temperature: float = 0.0
    max_tokens: int    = 100
    few_shot: bool     = True          


from multi_agent_prompts import (
    TRACER_SYSTEM_PROMPT, TRACER_USER_PROMPT,
    ANALYST_SYSTEM_PROMPT, ANALYST_USER_PROMPT,
    FORMATTER_SYSTEM_PROMPT, FORMATTER_USER_PROMPT,
)

class LocalTransformersClient:
    def __init__(self, cfg: Config):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception as e:
            raise ImportError(
                "Transformers backend selected but transformers is not available. "
                "Install dependencies from requirements.txt."
            ) from e

        self.cfg = cfg
        self.tokenizer = AutoTokenizer.from_pretrained(cfg.model, trust_remote_code=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            cfg.model,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        )

    def predict(self, sys_prompt: str, user_prompt: str) -> Optional[str]:
        try:
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ]

            if hasattr(self.tokenizer, "apply_chat_template"):
                prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            else:
                prompt = sys_prompt + "\n\n" + user_prompt

            inputs = self.tokenizer(prompt, return_tensors="pt")
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            generated = self.model.generate(
                **inputs,
                max_new_tokens=self.cfg.max_tokens,
                do_sample=False if self.cfg.temperature == 0.0 else True,
                temperature=self.cfg.temperature if self.cfg.temperature > 0 else None,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

            new_tokens = generated[0][inputs["input_ids"].shape[-1]:]
            return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        except Exception as e:
            print(f"Local inference error: {e}")
            return None

class LLMClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg

        if cfg.provider == "local_transformers":
            self.local_client = LocalTransformersClient(cfg)
            self.client = None
            return

        prov = PROVIDERS[cfg.provider]
        api_key = os.environ.get(prov["api_key_env"])
        if not api_key:
            raise ValueError(f"Set {prov['api_key_env']} environment variable")
        # Allow endpoint override per provider (e.g., GHLLM_BASE_URL) without code changes.
        base_url = os.environ.get(f"{cfg.provider.upper()}_BASE_URL", prov["base_url"])
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.local_client = None

    def run_llm_call(self, sys_prompt: str, user_prompt: str) -> Optional[str]:
        if self.cfg.provider == "local_transformers":
            return self.local_client.predict(sys_prompt, user_prompt)
        try:
            resp = self.client.chat.completions.create(
                model=self.cfg.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.cfg.temperature,
                max_tokens=self.cfg.max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"API error: {e}")
            return None

    def predict(self, control_vars: list[str], source_vars: list[str], code_lines: list[str], output_return: list[str], next_input_function: list[str]) -> Optional[str]:
        try:
            # ==== AGENT 1: TRACER ====
            tracer_content = TRACER_USER_PROMPT.format(
                control_vars=control_vars,
                source_vars=source_vars,
                code_lines=code_lines,
                output_return=output_return,
                next_input_function=next_input_function 
            )
            print("[DEBUG Multi-Agent] Running Agent 1 (Tracer)...")
            tracer_output = self.run_llm_call(TRACER_SYSTEM_PROMPT, tracer_content)
            if not tracer_output: return None

            # ==== AGENT 2: ANALYST ====
            analyst_content = ANALYST_USER_PROMPT.format(
                control_vars=control_vars,
                code_lines=code_lines,
                tracer_output=tracer_output
            )
            print("[DEBUG Multi-Agent] Running Agent 2 (Analyst)...")
            analyst_output = self.run_llm_call(ANALYST_SYSTEM_PROMPT, analyst_content)
            if not analyst_output: return None

            # ==== AGENT 3: FORMATTER ====
            formatter_content = FORMATTER_USER_PROMPT.format(
                control_vars=control_vars,
                code_lines=code_lines,
                analyst_output=analyst_output
            )
            print("[DEBUG Multi-Agent] Running Agent 3 (Formatter)...")
            formatter_output = self.run_llm_call(FORMATTER_SYSTEM_PROMPT, formatter_content)
            
            return formatter_output
        except Exception as e:
            print(f"Multi-Agent API error: {e}")
            return None
# ----------------------------------------------------------
# Data processing 
# ----------------------------------------------------------
def extract_control_variables(dictionary):
    main_vars = dictionary.get("main", {}).get("variable_list", [])
    control_vars = set()

    for v in main_vars:
        rhs = v.split("=", 1)[1]
        tokens = re.findall(r"[a-zA-Z]+", rhs)

        for t in tokens:
            if not t.startswith("CALL"):
                control_vars.add(t)

    return control_vars

def parse_llm_output(pred_raw):
    def extract(pattern):
        match = re.search(pattern, pred_raw, re.DOTALL)
        return match.group(1).strip() if match else ""

    out1 = extract(r"OUT1:\s*(.*?)(?=OUT2:|$)")
    out2 = extract(r"OUT2:\s*(.*?)(?=OUT3:|$)")
    out3 = extract(r"OUT3:\s*(.*?)(?=OUT4:|$)")
    out4 = extract(r"OUT4:\s*(.*?)(?=OUT5:|$)")
    out5 = extract(r"OUT5:\s*(.*)")

    return out1, out2, out3, out4, out5

def parse_variables(var_string):
    if not var_string or var_string.strip() == "[]":
        return []

    variables = []
    parts = var_string.split(";")

    for p in parts:
        p = p.strip()
        if "=" in p:
            variables.append(p)

    return variables

def update_variable_list(var_list, new_vars):
    var_map = {}

    # existing variables
    for v in var_list:
        if "=" in v:
            left, right = v.split("=", 1)
            var_map[left.strip()] = right.strip()

    # update with new variables
    for v in new_vars:
        left, right = v.split("=", 1)
        var_map[left.strip()] = right.strip()

    # rebuild list
    return [f"{k} = {v}" for k, v in var_map.items()]

def parse_complexity(out4, out5):
    if not out4 or not out5:
        return [], []

    lines = [int(x.strip()) for x in out4.split(",") if x.strip()]
    perf  = [x.strip() for x in out5.split(",") if x.strip()]

    return lines, perf
        
# ----------------------------------------------------------
# LLM call
# ----------------------------------------------------------
def execution_llm(blocks_file, dict_file, limit: int, cfg: Config, output_path: Optional[Path]):

    print(f"Provider: {cfg.provider} | Model: {cfg.model}")
    print("=" * 80)

    # Task 1. Load inputs
    with open(blocks_file) as f:
        blocks = json.load(f)
    
    with open(dict_file) as f:
        current_dictionary = json.load(f)
    
    # Print full dictionary list: every path a new dictionary instance 
    #print("[DEBUG] Initial Dictionary:")
    #print(json.dumps(current_dictionary, indent=4))

    results = []
    previous_source = None
    
    # Task 2. Extract control variables --- they are defined once in the main function
    control_vars = extract_control_variables(current_dictionary)
    print("[DEBUG] Control Vars:", control_vars)

    client = LLMClient(cfg)    

    # Task 3. Iteract over blocks 
    for idx, block in enumerate(blocks):
        
        print(f"\n[BLOCK {idx}] --------------------------")

        # ----------------------------------
        # Task 4 Extract information from the blocks: (i-1), (i), (i+1)
        # ----------------------------------        
        # Current: block(i)
        source = block.get("source")
        code_lines = block.get("code", [])
        input_function = block.get("input_function")
        output_return = block.get("output_return") 
        print("[CURRENT]")
        print("source:", source)
        print("code:", code_lines)
        print("input_function:", input_function)
        print("output_function:", output_return)

        # Previous: function that calls block(i)        
        prev_source = None
        if source and "->" in source:
            prev_source = "->".join(source.split("->")[:-1])
        print("[PREVIOUS]")
        print("prev_source:", prev_source)
        
        # Next: block(i+1)
        next_source = None
        next_input_function = None
        if idx < len(blocks) - 1:
            next_block = blocks[idx + 1]
            next_source = next_block.get("source")
            next_input_function = next_block.get("input_function")
        # Get variables for current source
        with open(dict_file) as f:
            current_dictionary = json.load(f)
        source_vars = current_dictionary.get(source, {}).get("variable_list", [])

        print("[NEXT]")
        print("control_vars:", control_vars)
        print('source_vars:',  source_vars)
        print('code_lines:',   code_lines)
        print("next_source:",  next_source)
        print("next_input_function:", next_input_function)        
        

        # ----------------------------------
        # Task 5 Check input and call LLM
        # ----------------------------------
        # The block can only be analysed if source_vars and code_lines are valid        
        if code_lines and source_vars:
            # Call LLM                     
            pred_raw = client.predict(
                            control_vars,        # Global variables
                            source_vars,         # Variables we are tracking in the block 
                            code_lines,          # C++ lines from the block 
                            output_return,       # Output value from the block 
                            next_input_function) # Input for the next block             
            
            #OUT1: <var> = expr; // New list of variables to update Block (i)
            #OUT2: <var> = expr; // New list of variables (from return) to update Block (i-1)
            #OUT3: <var> = expr; // New list of variables (from next input) to update Block (i+1)
            #OUT4: l1,l2,...     // Line numbers affected by my blocks
            #OUT5: expr,expr,... // Complexity values on each line            
            print('xxxxxxxxxxxxxxxxxxxxxxxxx')
            print("[DEBUG] LLM RAW OUTPUT:")
            #print(pred_raw)
            if pred_raw is None:
                print("[WARN] LLM call failed for this block; skipping updates.")
                continue

            # ------------------------
            # Task 6: Update JSON file 
            # ------------------------

            # Parse LLM output
            out1, out2, out3, out4, out5 = parse_llm_output(pred_raw)
            
            print(out1)
            print(out2)
            print(out3)
            print(out4)
            print(out5)

            vars1 = parse_variables(out1)
            vars2 = parse_variables(out2)
            vars3 = parse_variables(out3)

            lines, perf = parse_complexity(out4, out5)

            print("[DEBUG] Parsed:")
            print("OUT1:", vars1)
            print("OUT2:", vars2)
            print("OUT3:", vars3)
            print("LINES:", lines)
            print("PERF:", perf)

            # Load dictionary
            with open(dict_file) as f:
                dictionary = json.load(f)            
            
            # 1. Update current source (OUT1)
            if vars1:
                if source not in dictionary:
                    dictionary[source] = {"variable_list": []}

                dictionary[source]["variable_list"] = update_variable_list(
                    dictionary[source]["variable_list"],
                    vars1)
            
            # 2. Update previous source (OUT2)
            if vars2 and prev_source:
                if prev_source not in dictionary:
                    dictionary[prev_source] = {"variable_list": []}

                dictionary[prev_source]["variable_list"] = update_variable_list(
                    dictionary[prev_source]["variable_list"],
                    vars2)

            # 3. Update next source (OUT3)
            if vars3 and next_source:
                if next_source not in dictionary:
                    dictionary[next_source] = {"variable_list": []}

                dictionary[next_source]["variable_list"] = update_variable_list(
                    dictionary[next_source]["variable_list"],
                    vars3)
            
            # Save updated dictionary
            with open(dict_file, "w") as f:
                json.dump(dictionary, f, indent=4)

            print("[DEBUG] Dictionary updated.")
           
            # 4. Update complexity file
            complexity_path = os.path.join(output_path, "output_4_complexity.json")

            # Load existing data
            if os.path.exists(complexity_path):
                with open(complexity_path) as f:
                    complexity_data = json.load(f)
            else:
                complexity_data = []

            # Build current block entry
            block_entry = {
                "block_id": idx,
                "source": source,
                "lines": lines if lines else [],
                "complexity": perf if perf else []
            }

            # Append block
            complexity_data.append(block_entry)

            # Save back
            with open(complexity_path, "w") as f:
                json.dump(complexity_data, f, indent=4)

            print("[DEBUG] Complexity updated.")
            
           
    print("\n[FINAL] Execution completed.")

# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_code", required=True)
    parser.add_argument("--input_dictionary", required=True)
    parser.add_argument("--output", default="result/prompt1.txt")
    parser.add_argument(
        "--provider",
        default="local_transformers",
        choices=["deepseek", "openrouter", "huggingface", "ghllm", "local_transformers"],
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-few-shot", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    model = args.model or PROVIDERS[args.provider]["default_model"]
    cfg = Config(provider=args.provider, model=model, few_shot=True)  # not args.no_few_shot)

    # Call LLM execution
    execution_llm(
        args.input_code,
        args.input_dictionary,
        args.limit,
        cfg,
        Path(args.output) if args.output else None,
    )

if __name__ == "__main__":
    main()

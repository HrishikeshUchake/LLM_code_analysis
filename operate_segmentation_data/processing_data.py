import json
import argparse
import os
import re

CALL_COUNTER    = 0
SEGMENT_COUNTER = 0

# ----------------------------------------------------------
# COUNTERS
# ----------------------------------------------------------
def next_call():
    global CALL_COUNTER
    CALL_COUNTER += 1
    return CALL_COUNTER

def next_segment():
    global SEGMENT_COUNTER
    SEGMENT_COUNTER += 1
    return SEGMENT_COUNTER

# ----------------------------------------------------------
# LOAD METADATA
# ----------------------------------------------------------

def load_metadata(scan_file):

    with open(scan_file, "r", encoding="utf-8") as f:
        data_complete = json.load(f)

    data = data_complete.get("results", [])

    table = {}

    for func in data:
        name = func.get("name")
        if name:
            table[name] = func

    return table

# ----------------------------------------------------------
# SEGMENT CREATION
# ----------------------------------------------------------

def create_segment(segments_counter, name, depth, seg_type, code):

    segments_counter.append({
        "segmentation": next_segment(),
        "source": name,
        "depth": depth,
        "type": seg_type,
        "code": code.copy()
    })


# ----------------------------------------------------------
# PARAMETER TRANSFER
# ----------------------------------------------------------

def parameter_transfer(call, caller_map, callee_map):

    code = []

    args = call["variable_passed"]
    params = list(callee_map.keys())

    for i in range(min(len(args), len(params))):

        src = caller_map.get(args[i], args[i])
        dst = callee_map[params[i]]

        code.append(f"{dst} = {src}")

    return code

# ----------------------------------------------------------
# LOAD SOURCE FILE
# ----------------------------------------------------------
def load_source(folder, filename):
    path = os.path.join(folder, filename)
    with open(path) as f:
        return f.readlines()
    
# ----------------------------------------------------------
# VARIABLE RENAMING
# ----------------------------------------------------------
def build_var_map(meta, call_id):
    mapping = {}
    counter = 1
    for v in meta.get("all_variables", []):
        name = v["variable"]
        mapping[name] = f"<CALL{call_id}_VAR{counter}_{name}>"
        counter += 1
    return mapping

def substitute(line, mapping):
    for original, new in mapping.items():
        line = re.sub(rf"\b{original}\b", new, line)
    return line

# ----------------------------------------------------------
# CLEAN LINE
# ----------------------------------------------------------
def clean_line(line):
    line = line.strip()
    if line == "":
        return None
    if line == "{" or line == "}":
        return None
    return line

# ----------------------------------------------------------
# EXTRACT SEGMENTS 
# ----------------------------------------------------------
def compute_segments_for_line(inherited_depth, line_no, start_col, end_col, loops, calls, returns):

    segments = []
    loop_segments = []

    # -----------------------------------------
    # STEP 1: collect loop segments
    # -----------------------------------------
    loops_sorted = sorted(loops, key=lambda x: x["depth"], reverse=True)

    for loop in loops_sorted:

        d_start = loop["declare_start"]
        d_end   = loop["declare_end"]

        b_start = loop["body_start"]
        b_end   = loop["body_end"]

        local_depth = loop["depth"]
        depth = inherited_depth + local_depth

        # ---------------- LOOP DECLARATION ----------------
        if line_no == d_start["line"]:

            seg_start = max(start_col, d_start["col"])
            seg_end   = min(end_col, d_end["col"])

            if seg_start <= seg_end:
                loop_segments.append({
                    "start": seg_start,
                    "end": seg_end,
                    "type": "loop_declaration",
                    "depth": depth - 1
                })

        # ---------------- LOOP BODY ----------------
        if b_start["line"] <= line_no <= b_end["line"]:

            body_start_col = b_start["col"] if line_no == b_start["line"] else start_col
            body_end_col   = b_end["col"]   if line_no == b_end["line"]   else end_col

            seg_start = max(start_col, body_start_col)
            seg_end   = min(end_col, body_end_col)

            # remove declaration overlap
            if line_no == d_start["line"]:
                seg_start = max(seg_start, d_end["col"] + 1)

            if seg_start <= seg_end:
                loop_segments.append({
                    "start": seg_start,
                    "end": seg_end,
                    "type": "code",
                    "depth": depth
                })

    # -----------------------------------------
    # STEP 2: normalize segments (NO OVERLAP)
    # -----------------------------------------

    # Collect all boundary points
    points = set()

    for seg in loop_segments:
        points.add(seg["start"])
        points.add(seg["end"] + 1)

    points.add(start_col)
    points.add(end_col + 1)

    points = sorted(points)

    # -----------------------------------------
    # STEP 3: build minimal non-overlapping segments
    # -----------------------------------------
    segments = []

    for i in range(len(points) - 1):

        seg_start = points[i]
        seg_end   = points[i + 1] - 1

        if seg_start > seg_end:
            continue

        # -------------------------------------
        # Find covering segments
        # -------------------------------------
        covering = []

        for seg in loop_segments:
            if not (seg["end"] < seg_start or seg["start"] > seg_end):
                covering.append(seg)

        # -------------------------------------
        # Select deepest segment (highest depth)
        # -------------------------------------
        if covering:
            loop_count = sum(1 for seg in covering if seg["type"] == "code")
            has_decl = any(seg["type"] == "loop_declaration" for seg in covering)

            segments.append({
                "start": seg_start,
                "end": seg_end,
                "type": "loop_declaration" if has_decl else "code",
                "depth": inherited_depth + loop_count
            })
        else:
            # outside any loop
            segments.append({
                "start": seg_start,
                "end": seg_end,
                "type": "code",
                "depth": inherited_depth
            })

    # -----------------------------------------
    # STEP 4: REFINE (CALL + RETURN)
    # -----------------------------------------
    refined = []

    for seg in segments:

        seg_start = seg["start"]
        seg_end   = seg["end"]
        seg_depth = seg["depth"]

        classified = False

        # ---------------- CALL DETECTION ----------------
        if line_no in calls:

            for call in calls[line_no]:                
                c_start = call["start"]["col"]
                c_end   = call["end"]["col"]

                # ANY overlap → FULL segment becomes call
                if not (c_end < seg_start or c_start > seg_end):

                    refined.append({
                        "start": seg_start,
                        "end": seg_end,
                        "type": "call",
                        "depth": seg_depth,
                        "call": call
                    })

                    classified = True
                    break

        if classified:
            continue

        # ---------------- RETURN DETECTION ----------------
        if line_no in returns:

            r = returns[line_no]   # get return object

            # -------------------------------------
            # STEP 1: check if return has value
            # -------------------------------------
            ret_val = r.get("value", None)

            if not ret_val or ret_val == "none":
                continue   

            # -------------------------------------
            # STEP 2: column overlap check
            # -------------------------------------
            r_start = r["start"]["col"]
            r_end   = r["end"]["col"]

            if not (r_end < seg_start or r_start > seg_end):

                refined.append({
                    "start": seg_start,
                    "end": seg_end,
                    "type": "return",
                    "depth": seg_depth,
                    "value": ret_val
                })

                continue
                
        # ---------------- DEFAULT ----------------
        refined.append(seg)

    return refined

# ----------------------------------------------------------
# FUNCTION EXPANSION
# ----------------------------------------------------------
def expand_function(name, table, folder, code_out, segments_counter, inherited_depth, active_call, call_path_name):

    meta    = table[name]
    call_id = next_call()
    source  = load_source(folder, meta["source_file"])
    var_map = build_var_map(meta, call_id)
    loops   = meta.get("loops", [])
    #calls   = {c["start"]["line"]: c for c in meta.get("calls", [])}
    calls = {}
    for c in meta.get("calls", []):
        line = c["start"]["line"]
        calls.setdefault(line, []).append(c)    
    returns = {r["start"]["line"]: r for r in meta.get("return", [])}
    decl    = meta["function_declare"] 
       
    # ------------------------------------------------------
    # FUNCTION DECLARATION SEGMENT
    # ------------------------------------------------------
    #decl_line = source[decl["start"]["line"] - 1].strip()
    start_line = decl["start"]["line"]
    start_col  = decl["start"]["col"]
    end_line   = decl["end"]["line"]
    end_col    = decl["end"]["col"]
    raw_line   = source[start_line - 1]
    decl_line  = raw_line[start_col - 1:end_col].strip()    
    decl_line  = substitute(decl_line, var_map)  

    # Create Segment 1
    create_segment(segments_counter, call_path_name, inherited_depth, "function_declaration", [decl_line])  
    code_out.append(decl_line)      
    print(inherited_depth, "function_declaration")
    print([decl_line])    
    print()    
    

    #print(seg["depth"], seg["type"])
    #print(code)
    #print()
    
    #print("function_declaration")
    #print(decl_line)
    #print(decl_line)

    # ------------------------------------------------------
    # FUNCTION BODY
    # ------------------------------------------------------    
    body_start = meta["function_range"]["start"]["line"]
    body_end = meta["function_range"]["end"]["line"]
   
    for line_no in range(body_start, body_end + 1):

        # Update line by line
        raw = source[line_no - 1].rstrip("\n") 
        line_clean = raw.rstrip()
        start_col = len(line_clean) - len(line_clean.lstrip()) + 1
        end_col = len(line_clean)
        if raw.strip()=="":
            continue
        
        # --------------------------------------------------
        # Find segments
        # --------------------------------------------------  
        segments = compute_segments_for_line(inherited_depth, line_no, start_col, end_col, loops, calls, returns)        
                
        for seg in segments:           
             
            line = raw[seg["start"]-1:seg["end"]]
            code = substitute(line, var_map)
            code = clean_line(code)
            if code is None:
                continue    
            
            # Current depth
            #inherited_depth = seg["depth"]
            #print('----')
            #print(line_no, seg)
            #print(seg["type"])
            #print('----')
                             
            # ----------------------------------------
            # HANDLE CALL
            # ----------------------------------------
            if seg["type"] == "call":
                call   = seg["call"]
                callee = call["function"]  
                if table[callee]["library_function"] == "YES":
                    #create_segment(segments, name, depth, "library_function", [line])                    
                    # Create Segment 2
                    new_call_path_name = f"{call_path_name}->{callee}"
                    create_segment(segments_counter, new_call_path_name, seg["depth"], "library_function", [code])          
                    code_out.append(code)    
                    print(seg["depth"], "library_function")
                    print([code])
                    print()
                    #print(callee)
                else:
                    callee_meta = table[callee]
                    callee_map = build_var_map(callee_meta, CALL_COUNTER + 1)
                    transfer = parameter_transfer(call, var_map, callee_map)  
                    # Create Segment 3
                    new_call_path_name = f"{call_path_name}->{callee}"
                    create_segment(segments_counter, new_call_path_name, seg["depth"], "input_function", transfer)    
                    code_out.append(code)      
                    print(seg["depth"], "code")
                    print(transfer)
                    print()                      
                    # To operate return 
                    active_call = call.get("solution", [])
                    if active_call != []: # In this case the function is returning something 
                        active_call = substitute(active_call[0], var_map)
                    #
                    expand_function(callee, table, folder, code_out, segments_counter, seg["depth"], active_call, new_call_path_name)
                continue

            # ----------------------------------------
            # HANDLE RETURN
            # ----------------------------------------
            elif seg["type"] == "return":  
                
                # TODO: multiple returns                
                
                ret_val = seg.get("value", "none")                     
                if not active_call:
                    continue 
                if not active_call or ret_val == "none":
                    continue  
                if ret_val == "retval":
                    continue                         
                ret_val = substitute(ret_val, var_map)                
                
                # ---------------------------------------
                # SIMPLE mapping: return → solution
                # ---------------------------------------                
                output_code = f"{ret_val} = {active_call}"                
                # Create Segment 4
                create_segment(segments_counter, call_path_name, seg["depth"], "output_return", [output_code])       
                code_out.append(output_code)      
                print(seg["depth"], "output_return")
                print([output_code])
                print() 

            # ----------------------------------------
            # HANDLE EVERYTHING ELSE (CODE)
            # ----------------------------------------
            else:
                # Create Segment 5
                create_segment(segments_counter, call_path_name, seg["depth"], seg["type"], [code]) 
                code_out.append(code)          
                print(seg["depth"], seg["type"])
                print([line])
                print()  
             

# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--script_folder", required=True)
    parser.add_argument("--scan_code", required=True)
    parser.add_argument("--output", default="expanded_code.txt", help="File to store expanded code")
    args = parser.parse_args()

    table = load_metadata(args.scan_code)

    code_lines       = []
    segments_counter = []

    expand_function("main", table, args.script_folder, code_lines, segments_counter, inherited_depth=0, active_call=None, call_path_name="main")

    # -------------------------------
    # Write results
    # ------------------------------    
    output_dir = args.output
    output_file_txt = os.path.join(output_dir,  "output_2_processed_code.txt")
    output_file_json = os.path.join(output_dir, "output_2_processed_code.json")

    # Create directory if it does not exist
    os.makedirs(output_dir, exist_ok=True)

    # write combined program
    with open(output_file_txt, "w") as f:
        for line in code_lines:
            f.write(line + "\n")
    print('Output text saved in: ', output_file_txt)

    # write segmentation json
    with open(output_file_json, "w") as f:
        json.dump(segments_counter, f, indent=2)
    print('Output JSON saved in: ', output_file_json)

if __name__ == "__main__":
    main()
import json
import argparse
import os
import re

# ----------------------------------------------------------
# Processing data
# ----------------------------------------------------------
def parse_variable_file(variable_file):
    start_segment = None
    variables = []
    with open(variable_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("segmentation"):
                start_segment = int(line.split(":")[1].strip())
            else:
                _, expr = line.split(":", 1)
                variables.append(expr.strip())
    return start_segment, variables

def preprocess_segments(input_json, input_variable):
	with open(input_json, "r") as f:
		segments = json.load(f)
	start_segment, variables = parse_variable_file(input_variable)
	#print(start_segment, variables)

	input_var = []
	program   = []
	line_id   = 1

	# -----------------------------------------------------
	# Process segments
	# -----------------------------------------------------
	for seg in segments:
		seg_id = seg["segmentation"]
		# Include the variables after informed segmentation
		if seg_id <= start_segment:
			continue
		
		seg_source = seg["source"]
		seg_type   = seg["type"]
		seg_depth  = seg["depth"]

		if seg_type not in ["code", 
                            "loop_declaration", 
                            "function_declaration", 
                            "library_function", 
                            "input_function", 
                            "output_return"]:
			continue

		code_lines = seg["code"]
        
		# -------------------------------------------------
		# Avoid duplicated declaration line
		# -------------------------------------------------
		previous_line = None
		if seg_type == "function_declaration":
			previous_line = None
			for line in code_lines:
				clean_line = line.strip()

				# Avoid duplicates inside declaration
				if previous_line and clean_line == previous_line:
					continue

				program.append({
				"line_id": line_id,
				"source":  seg_source,
				"type":    seg_type,
				"depth":   seg_depth,
				"code":    clean_line
				})
				line_id += 1
				previous_line = clean_line

			continue

		for i, line in enumerate(code_lines):
			if 'previous_line' in locals() and previous_line and line.strip() == previous_line.strip():
				previous_line = None
				continue
			program.append({
				"line_id": line_id,
				"source":  seg_source,
				"type":    seg_type,
				"depth":   seg_depth,
				"code":    line.strip()
			})
			line_id += 1
			previous_line = None

	return variables, start_segment, program

def build_blocks(program):
	blocks = []
	dictionary = {}

	current_block = None
	current_source = None

	for item in program:
		src  = item["source"]
		typ  = item["type"]
		code = item["code"]
		line = item["line_id"]

		# --------------------------------------
		# Skip function declaration
		# --------------------------------------
		if typ == "function_declaration":
			continue

		# --------------------------------------
		# New block when source changes
		# --------------------------------------
		# Normalize library function names --- so the library function will be attached to the root source
		if typ == "library_function":
			if "->" in src:
				src = "->".join(src.split("->")[:-1])   

		if src != current_source:
			if current_block:
				blocks.append(current_block)

			current_block = {
				"source": src,
				"input_function": [],
				"output_return": [],
				"code": []
			}

			current_source = src

			# Add to dictionary (unique)
			if src not in dictionary:
				dictionary[src] = {"variable_list": []}

		# --------------------------------------
		# Handle types
		# --------------------------------------

		if typ == "input_function":
			current_block["input_function"].append(code)

		elif typ == "output_return":
			current_block["output_return"].append(code)

		else:
			# Build tagged line
			tag = ""
			if typ == "loop_declaration":
				tag = "[LOOP] "

			elif typ == "library_function":
				tag = "[LIBRARY_FUNCTION] "

			depth = item["depth"]
			formatted_line = f"line={line} | depth={depth} | code={tag}{code}"      
			current_block["code"].append(formatted_line)

	# append last block
	if current_block:
		blocks.append(current_block)

	return blocks, dictionary

def segment_data(input_json, input_variable):
	
	variables, start_segment, program = preprocess_segments(input_json, input_variable)
	blocks, dictionary = build_blocks(program)
      
	# Attach variables to "main"
	if "main" not in dictionary:
		dictionary["main"] = {"variable_list": []}
	dictionary["main"]["variable_list"].extend(variables)
	
	return blocks, dictionary

def run_ast_normalizer(output_dir, code_dir="../codes/code_0F/script/"):
    """
    Tree-Sitter based AST normalizer that normalizes variables globally with interprocedural parameter mapping.
    """
    try:
        from ast_normalizer import normalize_code
        
        cpp_files = [f for f in os.listdir(code_dir) if f.endswith(".cpp")]
        normalized_results = []
        
        for file in cpp_files:
            file_path = os.path.join(code_dir, file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            normalized_code = normalize_code(content)
            
            normalized_results.append({
                "function": f"file:{file}",
                "original_code": content,
                "normalized_code": normalized_code
            })
            
        out_path = os.path.join(output_dir, "output_normalized.json")
        with open(out_path, "w") as f:
            json.dump(normalized_results, f, indent=4)
        print("Output JSON saved in: ", out_path)
    except ImportError:
        print("tree-sitter or ast_normalizer not found. Skipping AST normalization.")

# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------
def main():
	
	parser = argparse.ArgumentParser()
	parser.add_argument("--input_json",     required=True)
	parser.add_argument("--input_variable", required=True)
	parser.add_argument("--output",         default="result") 
	args = parser.parse_args()

	# Call segmentation
	blocks, dictionary = segment_data(args.input_json, args.input_variable)  
	      
	# -------------------------------
	# Write results
	# ------------------------------    
	output_dir = args.output
	output_file_1 = os.path.join(output_dir, "output_3_segments.json")
	output_file_2 = os.path.join(output_dir, "output_3_dictionary.json")
	output_file_3 = os.path.join(output_dir, "output_3_dictionary_initial.json")

	# Save blocks
	with open(output_file_1, "w") as f:
		json.dump(blocks, f, indent=4)
	print('Output JSON saved in: ', output_file_1)

	# Save dictionary
	with open(output_file_2, "w") as f:
		json.dump(dictionary, f, indent=4)
	print('Output JSON saved in: ', output_file_2)

	# Save dictionary (initial version)
	with open(output_file_3, "w") as f:
		json.dump(dictionary, f, indent=4)
	print('Output JSON saved in: ', output_file_3)
	
	# Execute AST Normalizer
	code_dir = os.path.abspath(os.path.join(output_dir, "../script/"))
	run_ast_normalizer(output_dir, code_dir)

if __name__ == "__main__":
    main()
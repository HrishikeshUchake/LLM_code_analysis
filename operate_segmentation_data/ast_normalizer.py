import re
import json

try:
    import tree_sitter
    import tree_sitter_cpp
except ImportError:
    pass

def build_equivalence_sets(tree, source_code):
    def get_decl(decl):
        while decl and decl.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
            decl = decl.child_by_field_name("declarator")
        return decl

    def get_function_name(node):
        decl = get_decl(node.child_by_field_name("declarator"))
        if decl and decl.type in ("function_declarator", "pointer_declarator", "reference_declarator"):
            n = get_decl(decl.child_by_field_name("declarator"))
            if n: return n.text.decode('utf8')
        return None
        
    def get_params(node):
        params = []
        decl = get_decl(node.child_by_field_name("declarator"))
        if decl and decl.type == "function_declarator":
            plist = decl.child_by_field_name("parameters")
            if plist:
                for child in plist.children:
                    if child.type == "parameter_declaration":
                        pdecl = get_decl(child.child_by_field_name("declarator"))
                        if pdecl:
                            params.append(pdecl.text.decode('utf8'))
        return params

    func_params = {}
    for node in tree.root_node.children:
        if node.type == "function_definition":
            fname = get_function_name(node)
            if fname:
                func_params[fname] = get_params(node)

    calls = []
    def traverse_calls(node, caller):
        if node.type == "call_expression":
            callee_node = node.child_by_field_name("function")
            if callee_node and callee_node.type == "identifier":
                callee = callee_node.text.decode("utf8")
                args_node = node.child_by_field_name("arguments")
                if args_node:
                    args = []
                    for arg in args_node.children:
                        if arg.is_named:
                            if arg.type == "identifier":
                                args.append(arg.text.decode('utf8'))
                            else:
                                args.append("<EXPR>") 
                    calls.append({"caller": caller, "callee": callee, "args": args})
        for child in node.children:
            traverse_calls(child, caller)
            
    for node in tree.root_node.children:
        if node.type == "function_definition":
            fname = get_function_name(node)
            if fname:
                traverse_calls(node.child_by_field_name("body"), fname)

    parent = {}
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i])
        return parent[i]
    def union(i, j):
        if i not in parent: parent[i] = i
        if j not in parent: parent[j] = j
        root_i, root_j = find(i), find(j)
        if root_i != root_j: parent[root_i] = root_j

    for fname, params in func_params.items():
        for p in params:
            parent[(fname, p)] = (fname, p)

    for call in calls:
        caller, callee, args = call["caller"], call["callee"], call["args"]
        if callee in func_params:
            for i, arg in enumerate(args):
                if i < len(func_params[callee]) and arg != "<EXPR>":
                    param = func_params[callee][i]
                    if (caller, arg) not in parent: parent[(caller, arg)] = (caller, arg)
                    if (callee, param) not in parent: parent[(callee, param)] = (callee, param)
                    union((caller, arg), (callee, param))

    # We also want to assign names to ALL other variables (locals)
    def collect_locals(node, fn):
        if node.type == "identifier":
            id_name = node.text.decode('utf8')
            if (fn, id_name) not in parent:
                parent[(fn, id_name)] = (fn, id_name)
        for child in node.children:
            # Avoid overwriting function calls etc.
            if child.type != "call_expression":
                collect_locals(child, fn)
            else:
                args = child.child_by_field_name("arguments")
                if args: collect_locals(args, fn)
                
    for node in tree.root_node.children:
        if node.type == "function_definition":
            fname = get_function_name(node)
            if fname:
                collect_locals(node.child_by_field_name("body"), fname)

    # Note: collecting everything might rename global types or namespace functions (e.g. MPI_Init) if not filtered.
    # To be extremely safe, we only rename recognized parameters AND recognized pass arguments that were already put in `parent`.
    # And we'll selectively map locals only if they are declared locally.
    # For now, let's just stick to the params and args that were assigned!

    from collections import defaultdict
    components = defaultdict(list)
    for node in parent.keys():
        components[find(node)].append(node)
    
    mapping = {}
    var_idx = 1
    for root, nodes in components.items():
        # filter out invalid like 'std' 'cout' etc if caught simply by checking if they are not in a hardcoded list.
        # But everything we put in parent here came from param or arg list or explicit assignment.
        name_for_set = f"var_{var_idx}"
        for fn, var in nodes:
            mapping[(fn, var)] = name_for_set
        var_idx += 1
        
    return mapping

def perform_substitution(code_content, tree, mapping):
    replacements = []
    
    def get_decl(decl):
        while decl and decl.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
            decl = decl.child_by_field_name("declarator")
        return decl

    def get_function_name(node):
        decl = get_decl(node.child_by_field_name("declarator"))
        if decl and decl.type == "function_declarator":
            n = get_decl(decl.child_by_field_name("declarator"))
            if n: return n.text.decode('utf8')
        return None

    def walk_replace(node, current_func):
        if node.type == "identifier":
            var_name = node.text.decode('utf8')
            key = (current_func, var_name)
            if key in mapping:
                replacements.append({
                    "start": node.start_byte,
                    "end": node.end_byte,
                    "new_text": mapping[key]
                })
        for child in node.children:
            walk_replace(child, current_func)

    for node in tree.root_node.children:
        if node.type == "function_definition":
            fname = get_function_name(node)
            if fname:
                walk_replace(node, fname)
                
    # Sort backwards to not mess up offsets
    replacements.sort(key=lambda x: x["start"], reverse=True)
    buf = bytearray(bytes(code_content, "utf8"))
    for rep in replacements:
        buf[rep["start"]:rep["end"]] = bytes(rep["new_text"], "utf8")
        
    return buf.decode('utf8')

def normalize_code(code_str):
    try:
        LANG = tree_sitter.Language(tree_sitter_cpp.language())
        parser = tree_sitter.Parser(LANG)
        tree = parser.parse(bytes(code_str, "utf8"))
        
        mapping = build_equivalence_sets(tree, code_str)
        # Avoid rewriting standard variables 
        reserved = {"cout", "cerr", "std", "vector", "string", "endl", "MPI_COMM_WORLD"}
        for k in list(mapping.keys()):
            if k[1] in reserved:
                del mapping[k]
                
        return perform_substitution(code_str, tree, mapping)
    except Exception as e:
        print("AST Normalize error:", e)
        return code_str

if __name__ == "__main__":
    with open("codes/code_0F/script/code_experiment.cpp", "r") as f:
        print(normalize_code(f.read()))

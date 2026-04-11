import tree_sitter
import tree_sitter_cpp
from collections import defaultdict

def run_graph():
    with open("../codes/code_0F/script/code_experiment.cpp", "r") as f:
        code_content = f.read()
    
    LANG = tree_sitter.Language(tree_sitter_cpp.language())
    parser = tree_sitter.Parser(LANG)
    tree = parser.parse(bytes(code_content, "utf8"))

    func_params = {}
    
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

    for node in tree.root_node.children:
        if node.type == "function_definition":
            fname = get_function_name(node)
            fparams = get_params(node)
            func_params[fname] = fparams

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
                    calls.append({
                        "caller": caller,
                        "callee": callee,
                        "args": args
                    })
        for child in node.children:
            traverse_calls(child, caller)
            
    for node in tree.root_node.children:
        if node.type == "function_definition":
            fname = get_function_name(node)
            traverse_calls(node.child_by_field_name("body"), fname)

    # Build Graph
    parent = {}
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i])
        return parent[i]
    def union(i, j):
        root_i, root_j = find(i), find(j)
        if root_i != root_j: parent[root_i] = root_j
        
    # initialization
    for caller, calls_made in calls:
        pass # we will initialize on demand layer below
    
    # 2nd pass: initialize all variables we see.
    for fname, params in func_params.items():
        for p in params:
            parent[(fname, p)] = (fname, p)

    for call in calls:
        caller = call["caller"]
        callee = call["callee"]
        if callee in func_params:
            for i, arg in enumerate(call["args"]):
                if i < len(func_params[callee]) and arg != "<EXPR>":
                    param = func_params[callee][i]
                    node1 = (caller, arg)
                    node2 = (callee, param)
                    if node1 not in parent: parent[node1] = node1
                    if node2 not in parent: parent[node2] = node2
                    union(node1, node2)

    # Gather components
    components = defaultdict(list)
    for node in parent.keys():
        components[find(node)].append(node)

    print("COMPONENTS:")
    for root, nodes in components.items():
        print(f"{root} -> {nodes}")

run_graph()

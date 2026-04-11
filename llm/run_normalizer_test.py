import re
import json

def process_file(code_content):
    import tree_sitter
    import tree_sitter_cpp
    
    LANG = tree_sitter.Language(tree_sitter_cpp.language())
    parser = tree_sitter.Parser(LANG)
    tree = parser.parse(bytes(code_content, "utf8"))

    # We will build a list of all variable identifiers and their function scope.
    # Then we will build mappings.

    # Find functions:
    func_query = LANG.query("""
    (function_definition
      declarator: (function_declarator
        declarator: (identifier) @func.name
        parameters: (parameter_list (parameter_declaration
          declarator: [
            (identifier) @param.name
            (pointer_declarator declarator: (identifier) @param.name)
            (array_declarator declarator: (identifier) @param.name)
            (reference_declarator declarator: (identifier) @param.name)
          ]
        )*)
      )
      body: (compound_statement) @func.body
    )
    """)

    # We need to map a position to a function scope.
    funcs = {}
    for name, nodes in func_query.captures(tree.root_node).items():
        if name == "func.name":
            # wait, captures gives all func.name nodes. We need to process sequentially.
            pass

    # A simpler approach: recurse the AST natively to find definition and calls.
    def find_scope(node):
        curr = node
        while current := curr.parent:
            if current.type == "function_definition":
                decl = current.child_by_field_name("declarator")
                if decl:
                    # unwrap declarator
                    while decl.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
                        decl = decl.child_by_field_name("declarator")
                    if decl.type == "function_declarator":
                        name_node = decl.child_by_field_name("declarator")
                        if name_node:
                            return name_node.text.decode('utf8')
            curr = current
        return "global"
    
    # 1. Collect all function parameters
    func_params = {} # {func_name: [param1, param2, ...]}
    
    # Let's traverse the tree manually
    def get_function_name(node):
        decl = node.child_by_field_name("declarator")
        while decl and decl.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
            decl = decl.child_by_field_name("declarator")
        if decl and decl.type == "function_declarator":
            n = decl.child_by_field_name("declarator")
            if n: return n.text.decode('utf8')
        return None
        
    def get_params(node):
        params = []
        decl = node.child_by_field_name("declarator")
        while decl and decl.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
            decl = decl.child_by_field_name("declarator")
        if decl and decl.type == "function_declarator":
            plist = decl.child_by_field_name("parameters")
            if plist:
                for child in plist.children:
                    if child.type == "parameter_declaration":
                        pdecl = child.child_by_field_name("declarator")
                        # unwrap
                        while pdecl and pdecl.type in ("pointer_declarator", "reference_declarator", "array_declarator", "init_declarator"):
                            pdecl = pdecl.child_by_field_name("declarator")
                        if pdecl:
                            params.append(pdecl.text.decode('utf8'))
        return params

    for node in tree.root_node.children:
        if node.type == "function_definition":
            fname = get_function_name(node)
            fparams = get_params(node)
            func_params[fname] = fparams

    # Find calls
    calls = [] # [(caller, callee, [arg1, arg2,...])]
    def traverse_calls(node, caller):
        if node.type == "call_expression":
            callee_node = node.child_by_field_name("function")
            if callee_node and callee_node.type == "identifier":
                callee = callee_node.text.decode("utf8")
                args_node = node.child_by_field_name("arguments")
                if args_node:
                    args = []
                    # Just reading identifiers. Complex expressions like a+b ignored for exact mapping.
                    for arg in args_node.children:
                        if arg.is_named:
                            # if it's an identifier or has identifiers
                            if arg.type == "identifier":
                                args.append(arg.text.decode('utf8'))
                            else:
                                args.append(None) 
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

    print("PARAMS:", func_params)
    print("CALLS:", calls)
    
with open("../codes/code_0F/script/code_experiment.cpp", "r") as f:
    process_file(f.read())

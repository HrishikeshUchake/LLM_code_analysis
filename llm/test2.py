import re
import tree_sitter
import tree_sitter_cpp

def run_test():
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

    print("PARAMS:", func_params)
    print("CALLS:", calls)

run_test()

import tree_sitter
import tree_sitter_cpp

parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_cpp.language()))

with open("../codes/code_0F/script/code_experiment.cpp", "r") as f:
    content = f.read()

tree = parser.parse(bytes(content, "utf8"))
query_code = """
(function_declarator
  declarator: (identifier) @name
  parameters: (parameter_list (parameter_declaration declarator: (identifier)? @param))
)

(call_expression
  function: (identifier) @call.name
  arguments: (argument_list (_) @call.arg)
)

(declaration
  declarator: (init_declarator declarator: (identifier) @local_var)
)
"""
try:
    query = tree_sitter.Language(tree_sitter_cpp.language()).query(query_code)
    captures = query.captures(tree.root_node)
    for node, name in captures.items():
        print(f"{name}: {node.text.decode('utf8')}")
except Exception as e:
    print(e)

import sys
import ast

class ControlFlowMapper(ast.NodeVisitor):
    """Create a control flow graph"""

    def __init__(self):
        self.graphs = {}
        self.graph = None

    def visit_FunctionDef(self, node):
        self.block = []
        self.graph = {0: self.block}
        self.next_label = 1
        for stmt in node.body:
            self.visit(stmt)
        self.graphs[node.name] = self.graph
        del self.next_label
        del self.block
        self.graph = None

    def visit_Assign(self, node):
        self.block.append(node)

    def visit_AugAssign(self, node):
        self.block.append(node)

    def visit_Expr(self, node):
        self.block.append(node)

    def visit_While(self, node):
        next_block_label = self.next_label
        self.next_label += 1
        while_label = self.next_label
        self.next_label += 1
        self.block.append(while_label)
        self.block = []
        self.graph[while_label] = self.block
        self.block.append((node.test, self.next_label))
        self.block.append(next_block_label)
        self.block = []
        self.graph[self.next_label] = self.block
        self.next_label += 1
        for stmt in node.body:
            self.visit(stmt)
        self.block.append(while_label)
        self.block = []
        self.graph[next_block_label] = self.block

def pprint(graph, indent=0):
    for label, block in graph.items():
        print(f"L{label:<2}: ", end='')
        for stmt in block:
            if isinstance(stmt, ast.AST):
                print(ast.unparse(stmt))
            elif isinstance(stmt, tuple):
                print(f"IF {ast.unparse(stmt[0])} GOTO L{stmt[1]}")
            else:
                print(f"GOTO L{stmt}")
            print("     ", end='')
        print()

def test():
    assert(len(sys.argv) == 2)
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        module_ast = ast.parse(f.read(), 'test_blitter.py', 'exec')
    mapper = ControlFlowMapper()
    mapper.visit(module_ast)
    for name, graph in mapper.graphs.items():
        print(f"{name}()")
        pprint(graph)

if __name__ == '__main__':
    test()

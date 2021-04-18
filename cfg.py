import sys
import ast
from collections import deque
from dataclasses import dataclass, field

@dataclass
class BasicBlock:
    label: int
    body: list[ast.AST] = field(default_factory=list, compare=False)
    edges_out: list['BasicBlock'] = field(default_factory=list,
                                          compare = False)

    def __iter__(self):
        visited = set()
        blocks = deque([self])
        while blocks:
            next_block = blocks.popleft()
            label = next_block.label
            if label in visited:
                continue
            visited.add(label)
            yield next_block
            blocks.extend(next_block.edges_out)

    def get_identifiers(self):
        try:
            return self.identifiers
        except AttributeError:
            identifiers = set()
            for node in self.body:
                identifiers.update(n.id for n in ast.walk(node)
                                   if isinstance(n, ast.Name))
            self.identifiers = identifiers
        return identifiers

class ControlFlowMapper(ast.NodeVisitor):
    """Create a control flow graph"""

    def __init__(self):
        self.graphs = {}
        self.graph = None

    def visit_FunctionDef(self, node):
        self.block = BasicBlock(0)
        self.graph = self.block
        self.next_label = 1
        for stmt in node.body:
            self.visit(stmt)
        self.graphs[node.name] = self.graph 
        del self.next_label
        del self.block
        self.graph = None

    def visit_Assign(self, node):
        self.block.body.append(node)

    def visit_AugAssign(self, node):
        self.block.body.append(node)

    def visit_Expr(self, node):
        self.block.body.append(node)

    def visit_While(self, node):
        loop_condition_label = self.next_label
        self.next_label += 1
        loop_body_label = self.next_label
        self.next_label += 1
        loop_body = BasicBlock(loop_body_label)
        loop_condition = BasicBlock(loop_condition_label,
                                    [node.test], [loop_body])
        self.block.edges_out.append(loop_condition)
        self.block = loop_body
        for stmt in node.body:
            self.visit(stmt)
        self.block.edges_out.append(loop_condition)
        self.block = BasicBlock(self.next_label)
        self.next_label += 1
        loop_condition.edges_out.insert(0, self.block)

def pprint(graph, indent=0):
    for block in graph:
        print(f"L{block.label:<2}: ", end='')
        for node in block.body:
            code = ast.unparse(node)
            if isinstance(node, ast.stmt):
                print(code)
            else:
                print(f"IF {code} GOTO L{block.edges_out[1].label}")
            print("     ", end='')
        if block.edges_out:
            print(f"GOTO L{block.edges_out[0].label}")
        print()

def test():
    assert len(sys.argv) == 2
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        module_ast = ast.parse(f.read(), 'test_blitter.py', 'exec')
    mapper = ControlFlowMapper()
    mapper.visit(module_ast)
    for name, graph in mapper.graphs.items():
        print(f"{name}()")
        pprint(graph)

if __name__ == '__main__':
    test()

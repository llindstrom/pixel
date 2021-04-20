"""Optimizer pass, very limited

Remove inlined argument type construction assignments at the top of the
start of each function body.

At some point this should become a capable optimizer that does proper
copy propogation, constant folding, and dead code removal.
"""
import ast
from collections import Counter

def clean(module):
    """Remove some redundant identifiers"""

    # The typer ensures all assignments have defined values.
    tracer = UsageTracer()
    tracer.visit(module)
    replacer = CopyPropogate(tracer.usage)
    return replacer.visit(module)
    
class UsageTracer(ast.NodeVisitor):
    """Count variable loads and stores by function"""

    def __init__(self):
        self.usage = {}
        self.function_body = False

    def visit_FunctionDef(self, node):
        self.local_loads = Counter()
        self.local_stores = Counter()
        self.usage[node.name] = self.local_loads, self.local_stores
        self.function_body = True
        self.generic_visit(node)
        self.function_body = False

    def visit_Name(self, node):
        if not self.function_body:
            return
        if isinstance(node.ctx, ast.Load):
            self.local_loads[node.id] += 1
        else:
            self.local_stores[node.id] += 1

class CopyPropogate(ast.NodeTransformer):
    """Remove some redundant identifiers. Very limited capability"""

    def __init__(self, usage):
        self.usage = usage
        self.function_body = False

    def visit_FunctionDef(self, node):
        self.local_loads, self.local_stores = self.usage[node.name]
        self.replacements = {}
        self.function_body = True
        self.generic_visit(node)
        self.function_body = False
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        if not self.function_body:
            return node
        value = node.value
        if (isinstance(value, ast.Name) and  # Conditional and
            self.local_loads[value.id] == 1):
            for i in range(len(node.targets)-1, -1, -1):
                target = node.targets[i]
                if (isinstance(target, ast.Name) and  # Conditional and
                    self.local_stores[target.id] == 1):
                    self.replacements[target.id] = value.id
                    del node.targets[i]
            if not node.targets:
                node = None
        return node

    def visit_Name(self, node):
        if not self.function_body:
            return node
        try:
            node.id = self.replacements[node.id]
        except KeyError:
            pass
        return node

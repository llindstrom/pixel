import ast
from collections.abc import Mapping

class Singleton:
    instances = {}

    def __new__(cls, name):
        try:
            return cls.instances[name]
        except:
            pass
        self = object.__new__(cls)
        self.name = name
        return self

    def __repr__(self):
        return self.name

ZERO = Singleton("ZERO")
ONE = Singleton("ONE")
MANY = Singleton("MANY")

class CollectStats(ast.NodeVisitor):
    """Collect information on identifiers"""

    def __init__(self):
        self.loads = {}
        self.subloads = None
        self.stores = {}
        self.substores = None
        self.stats = self.loads, self.stores
        self.in_while = False
        self.in_function_def = False

    def update(self, name_node):
        if not self.in_function_def:
            return
        name = name_node.id
        if isinstance(name_node.ctx, ast.Load):
            table = self.subloads
            other_table = self.substores
        else:
            table = self.substores
            other_table = self.subloads
        try:
            state = table[name]
        except:
            table[name] = ONE
            other_table[name] = ZERO
        else:
            if state is ZERO:
                table[name] = ONE
            elif state is ONE:
                table[name] = MANY

##        ?  ## What to do about loop body assignments; it's complicated.
##        ?  ## Need some kind of embedded loop tables.

    def visit_FunctionDef(self, node):
        self.subloads = {a.arg: ZERO for a in node.args.args}
        self.substores = {a.arg: ONE for a in node.args.args}
        self.in_function_def = True
        self.generic_visit(node)
        self.in_function_def = False
        self.loads[node.name] = self.subloads
        self.subloads = None
        self.stores[node.name] = self.substores
        self.substores = None

    def visit_Name(self, node):
        self.update(node)

class RemoveRedundancies(ast.NodeTransformer):
    def __init__(self, loads, stores):
        self.loads = loads
        self.subloads = None
        self.stores = stores
        self.substores = None
        self.stats = self.loads, self.stores
        self.in_while = False
        self.in_function_def = False
        self.substitutions = {}

    def visit_FunctionDef(self, node):
        self.subloads = self.loads[node.name]
        self.substores = self.stores[node.name]
        self.in_function_def = True
        self.generic_visit(node)
        self.in_function_def = False
        self.subloads = None
        self.substores = None
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        if not self.in_function_def:
            return node
        value = node.value
        if not isinstance(value, ast.Name):  ## To be expanded
            return node
        for i in range(len(node.targets)-1, -1, -1):
            target = node.targets[i]
            if (isinstance(target, ast.Name) and  # conditional and
                self.substores[target.id] is ONE and
                self.substores[value.id] is ONE):
                    self.substitutions[target.id] = value.id
                    del node.targets[i]
        if not node.targets:
            return None
        return node

    def visit_Name(self, node):
        try:
            node.id = self.substitutions[node.id]
        except KeyError:
            pass
        return node

def pprint(mapping, indent=0):
    for key, item in mapping.items():
        print(f"{' '* indent}{key}:", end='') 
        if isinstance(item, Mapping):
            print()
            pprint(item, indent+4)
        else:
            print(f" {item}")

def test():
    with open('test_blitter.py', 'r', encoding='utf-8') as f:
        module_ast = ast.parse(f.read(), 'test_blitter.py', 'exec')
    collector = CollectStats()
    collector.visit(module_ast)
    loads, stores = collector.stats
    pprint(loads)
    pprint(stores)
    remover = RemoveRedundancies(loads, stores)
    module_ast = remover.visit(module_ast)
    print(ast.unparse(module_ast))

if __name__ == '__main__':
    test()

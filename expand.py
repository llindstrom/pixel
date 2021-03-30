"""Compile loop descriptions file into a Python module
"""

import blitkit
import ast

def expand(source, path, symbol_table):
    """expand(source: str, path: string, glbs: dict) -> str
    """

    symtab = symbol_table.copy()
    module_ast = ast.parse(source, path, 'exec')
    inline_decorators(module_ast, symtab)
    typer(module_ast, symtab)
    inline_types(module_ast, symtab)
    add_imports(module_ast, symtab)
    return ast.unparse(module_ast)

def inline_decorators(module, symtab):
    """Replace decorators with inlined code"""

    ## STUB: unfinished
    symtab = symtab.copy()
    for i in range(len(module.body)):
        stmt = module.body[i]
        if isinstance(stmt, ast.FunctionDef):
            for d in reversed(stmt.decorator_list):
                module.body[i] = evaluate(d, symtab)(stmt)

def typer(module, symtab):
    """Add type annotation"""

    ## STUB: does nothing
    return symtab

def inline_types(module, symtab):
    """Replace types with inlined code"""

    ## STUB: does nothing
    return module, symtab

def add_imports(module, symtab):
    """Insert import statements from symbol table"""

    collect_imports = ImportCollector(symtab)
    collect_imports.visit(module)
    imports = collect_imports.imports

    # Remove redundant imports
    #
    # If a submodule of a module is imported, then it is unnecessary to
    # do an import on the module, assuming no 'from' imports or 'as' clauses.
    redundant = {n
        for name in imports for n in outer_names(name) if n not in imports}
    imports -= redundant

    # Insert import statment
    if imports:
        stmt = ast.Import(names=[ast.alias(name) for name in imports])
        module.body.insert(0, stmt)

def outer_names(name):
    """Iteratate over parent import names
    
    'a' -> (,)
    'a.b.c' -> ('a', 'a.b')
    """
    elements = name.split('.')
    for i in range(1, len(elements)):
        yield '.'.join(elements[0:i])

def expression_root_id(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expression_root_id(expr.value)
    if isinstance(expr, ast.Subsript):
        return expression_root_id(expr.value)
    raise ValueError(f"Unsupported expr {expr}")

def evaluate(node, symtab):
    """eval a simple ast expression"""

    if isinstance(node, ast.Name):
        # Get value
        try:
            return symtab[node.id]
        except KeyError:
            msg = "Name {node.id} not in symbol table"
            raise blitkit.BuildError(msg)
    elif isinstance(node, ast.Attribute):
        # Get attribute
        value = evaluate(node.value, symtab)
        return getattr(value, node.attr)
    elif isinstance(node, ast.Call):
        # call function
        func = evaluate(node.func, symtab)
        args = [evaluate(a, symtab) for a in node.args]
        return func(*args)
    else:
        msg = "Unknown expression element {node}"
        raise blitkit.BuildError(msg)

class ImportCollector(ast.NodeVisitor):
    """Collect modules that need importing

    Constructed names will be fully qualified names.
    """
    def __init__(self, symbol_table):
        self.symtab = symbol_table
        self.imports = set()

    def visit_Name(self, node):
        elements = node.id.split('.')
        if len(elements) > 1:
            self.imports.add('.'.join(elements[0:-1]))

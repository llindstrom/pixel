"""Compile loop descriptions into python functions
"""

import blitkit
import transform
import ast

def compile_file(path, glbs):
    """compile_file(path: str, glbs: dict) -> {"<name>": <funtion>}"""

    return compile(open(path).read(), path, glbs)

def compile(source, path, glbs):
    """compile(source: str, path: string, glbs: dict) -> {"<name>": <funtion>}
    """

    module_ast = ast.parse(source, path, 'exec')
    module_ast, glbs, exports = inline_decorators(module_ast, glbs)
    glbs = typer(module_ast, glbs)
    module_ast, glbs = inline_types(module_ast, glbs)
    code = __builtins__['compile'](module_ast, path, 'exec')
    lcls = {}
    exec(code, glbs, lcls)
    return {name: obj for name, obj in lcls.items() if name in exports}

def inline_decorators(module, symtab):
    """Replace decorators with inlined code"""

    ## STUB: remove decorators
    exports = set()
    stripped_symtab = symtab.copy()
    for stmt in module.body:
        if isinstance(stmt, ast.FunctionDef):
            decs = []
            for d in stmt.decorator_list:
                d_id = expression_root_id(d)
                if d_id in symtab:
                    exports.add(stmt.name)
                    stripped_symtab.pop(d_id, None)
                else:
                    decs.append(d)
            stmt.decorator_list = decs
    return module, stripped_symtab, exports

def typer(module, symtab):
    """Add type annotation"""

    ## STUB: does nothing
    return symtab

def inline_types(module, symtab):
    """Replace types with inlined code"""

    ## STUB: does nothing
    return module, symtab

def expression_root_id(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expression_root_id(expr.value)
    if isinstance(expr, ast.Subsript):
        return expression_root_id(expr.value)
    raise ValueError(f"Unsupported expr {expr}")

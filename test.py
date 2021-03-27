import ast, astkit as ak
import types
def test():
    b = ak.TreeBuilder()
    b.Name('prime')
    b.Constant(1)
    b.Assign1()
    b.Name('n')
    b.Constant(1)
    b.Gt()
    b.While()
    b.Name('prime')
    b.Name('n')
    b.IMult()
    b.Name('n')
    b.Constant(1)
    b.ISub()
    b.end()
    module = b.Module()
    assert(b._lineno == 1)
    assert(module.lineno == 0)
    assert(not b._stack)
    for i, item in enumerate(module.body):
        try:
            assert(item.lineno == i + 1)
        except AssertionError:
            print(f"i = {i}, lineno = {item.lineno}")
            raise
    assert(ast.unparse(module) ==
    "prime = 1\n"
    "while n > 1:\n"
    "    prime *= n\n"
    "    n -= 1")
    code = compile(module, '<prime>', 'exec')
    lcls = {'n': 3}
    exec(code, globals(), lcls)
    assert(lcls['n'] == 1 and lcls['prime'] == 6)
    b.Name('a')
    b.Constant(2)
    b.Add()
    b.Constant(3)
    b.Mult()
    expr = b.Expression()
    assert(expr.lineno == 0)
    assert(b._lineno == 1)
    assert(ast.unparse(expr) == "(a + 2) * 3")
    code = compile(expr, '<addmult>', 'eval')
    lcls = {'a': 12}
    assert(eval(code, globals(), lcls) == 42)
    b.Name('min')
    b.Call()
    b.Constant(12)
    b.Constant(1)
    b.Constant(2)
    b.end()
    expr = b.Expression()
    assert(ast.unparse(expr) == "min(12, 1, 2)")
    code = compile(expr, '<min>', 'eval')
    assert(eval(code) == 1)
    b.identifier('foo')
    b.arguments()
    b.identifier('x')
    b.end()
    b.FunctionDef()
    b.Constant(2)
    b.Name('x')
    b.Mult()
    b.Return()
    b.end()
    b.Name('y')
    b.Name('foo')
    b.Call()
    b.Constant(12)
    b.end()
    b.Assign1()
    module = b.Module()
    assert(ast.unparse(module) ==
    "def foo(x):\n"
    "    return 2 * x\n"
    "y = foo(12)")
    code = compile(module, '<foo>', 'exec')
    lcls = {}
    exec(code, globals(), lcls)
    assert(isinstance(lcls['foo'], types.FunctionType) and lcls['y'] == 24)

if __name__ == '__main__':
    test()


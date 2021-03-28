import unittest
import ast, astkit as ak
import types

class TestBasics(unittest.TestCase):

    def test_module(self):
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
        self.assertEqual(b._lineno, 1)
        self.assertEqual(module.lineno, 0)
        self.assertFalse(b._stack)
        for i, item in enumerate(module.body, 1):
            self.assertEqual(item.lineno, i)
        self.assertEqual(ast.unparse(module), "prime = 1\n"
                                              "while n > 1:\n"
                                              "    prime *= n\n"
                                              "    n -= 1")
        code = compile(module, '<prime>', 'exec')
        lcls = {'n': 3}
        exec(code, globals(), lcls)
        self.assertEqual(lcls['n'], 1)
        self.assertEqual(lcls['prime'], 6)

    def test_expression(self):
        b = ak.TreeBuilder()
        b.Name('a')
        b.Constant(2)
        b.Add()
        b.Constant(3)
        b.Mult()
        expr = b.Expression()
        self.assertEqual(expr.lineno, 0)
        self.assertEqual(b._lineno, 1)
        self.assertEqual(ast.unparse(expr), "(a + 2) * 3")
        code = compile(expr, '<addmult>', 'eval')
        lcls = {'a': 12}
        self.assertEqual(eval(code, globals(), lcls), 42)
        b.Name('min')
        b.Call()
        b.Constant(12)
        b.Constant(1)
        b.Constant(2)
        b.end()
        expr = b.Expression()
        self.assertEqual(ast.unparse(expr), "min(12, 1, 2)")
        code = compile(expr, '<min>', 'eval')
        self.assertEqual(eval(code), 1)

    def test_function_def_and_call(self):
        b = ak.TreeBuilder()
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
        self.assertEqual(ast.unparse(module), "def foo(x):\n"
                                              "    return 2 * x\n"
                                              "y = foo(12)")
        code = compile(module, '<foo>', 'exec')
        lcls = {}
        exec(code, globals(), lcls)
        self.assertIsInstance(lcls['foo'], types.FunctionType)
        self.assertEqual(lcls['y'], 24)

if __name__ == '__main__':
    unittest.main()


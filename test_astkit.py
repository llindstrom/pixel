import unittest
import ast, loops.astkit as ak
import types

class TestBasics(unittest.TestCase):

    def test_module(self):
        b = ak.TreeBuilder()
        b.Constant(1)
        b.Name('prime')
        b.Assign1()
        b.Name('n')
        b.Constant(1)
        b.Gt()
        b.While()
        b.Name('n')
        b.Name('prime')
        b.IMult()
        b.Constant(1)
        b.Name('n')
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
        b.Name('foo')
        b.Call()
        b.Constant(12)
        b.end()
        b.Name('y')
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

    def test_defer(self):
        was_called = False
        def test(args):
            nonlocal was_called
            self.assertEqual(args, ['a', 'b'])
            was_called = True
        b = ak.TreeBuilder()
        b.defer(test)
        b.identifier('a')
        b.identifier('b')
        b.end()
        self.assertTrue(was_called)
        self.assertFalse(b._stack)

    def test_attribute(self):
        b = ak.TreeBuilder()
        b.Name('int')
        b.Attribute('__name__')
        expr = b.Expression()
        self.assertEqual(ast.unparse(expr), "int.__name__")
        code = compile(expr, '<ast>', 'eval')
        self.assertEqual(eval(code), int.__name__)

    def test_inplace_operators(self):
        b = ak.TreeBuilder()
        b.Constant(0)
        b.Name('x')
        b.Assign1()
        b.Constant(2)
        b.Name('x')
        b.IAdd()
        b.Constant(3)
        b.Name('x')
        b.IMult()
        b.Constant(1)
        b.Name('x')
        b.ISub()
        module = b.Module()
        code = compile(module, '<ast>', 'exec')
        lcls = {}
        exec(code, globals(), lcls)
        self.assertEqual(len(lcls), 1)
        self.assertEqual(lcls['x'], 5)

    def test_subscript(self):
        b = ak.TreeBuilder()
        # As value
        b.Constant(1)
        b.Constant("abc")
        b.Subscript()
        expr = b.Expression()
        code = compile(expr, '<ast>', 'eval')
        self.assertEqual(eval(code), "b")

        # As target
        b.Name('list')
        b.Call()
        b.Constant((1, 9, 3))
        b.end()
        b.Name('x')
        b.Assign1()
        b.Constant(2)
        b.Constant(1)
        b.Name('x')
        b.Subscript()
        b.Assign1()
        module = b.Module()
        code = compile(module, '<ast>', 'exec')
        gbls = {}
        exec(code, gbls)
        self.assertEqual(gbls['x'], [1, 2, 3])

if __name__ == '__main__':
    unittest.main()


from transform import TInt, CompileError
from rgba import RGBA, c_uint8
import ast

class Writer(ast.NodeVisitor):
    def __init__(self, ostream):
        self.ostream = ostream
        self.indent = ''

    def visit_FunctionDef(self, node):
        ostream = self.ostream
        c_name = node.name
        returns = node.returns
        if (isinstance(returns, ast.Constant) and # conditional and
            returns.value is None):
            c_returns = 'void'
        elif returns is None:
            c_returns = 'void'
        else:
            raise CompileError("unsupported C return type")
        ostream.write('{}{} {}('.format(self.indent, c_returns, c_name))
        self.visit(node.args)
        ostream.write(') {\n')
        self.indent += '    '
        for stmt in node.body:
            self.visit(stmt)
        self.indent = self.indent[0:-4]
        ostream.write('{}}}\n'.format(self.indent))

    def visit_arguments(self, node):
        args = node.args
        for arg in args[0:-1]:
            self.visit(arg)
            self.ostream.write(', ')
        for arg in args[-1:]:
            self.visit(arg)

    def visit_arg(self, node):
        annotation = node.annotation
        if not isinstance(annotation, ast.Name):
            raise CompileError("Unsupported argument type")
        typ = annotation.id
        if typ == 'RGBA':
            self.ostream.write('unsigned char *')
        elif typ == 'int':
            self.ostream.write('int ')
        self.ostream.write(node.arg)

    def visit_Assign(self, node):
        targets = node.targets
        if len(targets) > 1:
            raise CompileError("Multiple assignment unsupported")
        self.ostream.write(self.indent)
        self.visit(targets[0])
        self.ostream.write(' = ')
        do_cast = self._cast(node.value, targets[0])
        if do_cast:
            self.ostream.write('(')
        self.visit(node.value)
        if do_cast:
            self.ostream.write(')')
        self.ostream.write(';\n')

    def visit_If(self, node):
        indent = self.indent
        self.ostream.write('{}if ('.format(indent))
        self.visit(node.test)
        self.ostream.write(') {\n')
        self.indent += '    '
        for stmt in node.body:
            self.visit(stmt)
        self.indent = self.indent[0:-4]
        self.ostream.write('{}}}'.format(self.indent))
        if node.orelse:
            self.ostream.write(' else {\n')
            self.indent += '    '
            for stmt in node.orelse:
                self.visit(stmt)
            self.indent = self.indent[0:-4]
            self.ostream.write('{}}}'.format(self.indent))
        self.ostream.write('\n')

    def visit_Call(self, node):
        func = node.func
        if not isinstance(func, ast.Name):
            raise CompileError("Unable to handle non-name function id")
        self.ostream.write('{}('.format(func.id))
        for arg in node.args[0:-1]:
            self.visit(arg)
            self.ostream.write(', ')
        for arg in node.args[-1:]:
            self.visit(arg)
        self.ostream.write(')')

    def visit_BinOp(self, node):
        self.ostream.write('(')
        self.generic_visit(node)
        self.ostream.write(')')

    def visit_Add(self, node):
        self.ostream.write(' + ')

    def visit_Sub(self, node):
        self.ostream.write(' - ')

    def visit_Mult(self, node):
        self.ostream.write(' * ')

    def visit_FloorDiv(self, node):
        self.ostream.write(' / ')

    def visit_LShift(self, node):
        self.ostream.write(' << ')

    def visit_RShift(self, node):
        self.ostream.write(' >> ')

    def visit_Subscript(self, node):
        self.visit(node.value)
        self.ostream.write('[')
        self.visit(node.slice)
        self.ostream.write(']')

    def visit_Name(self, node):
        self.ostream.write(node.id)

    def visit_Num(self, node):
        self.ostream.write('{}'.format(node.n))

    def _cast(self, value, target):
        # To implement later
        self.ostream.write('/* cast */ ')
        return True


class Compiler:
    def __init__(self, src):
        from io import StringIO
        from transform import Typer, Degrouper
        from rgba import Coder

        self.src = src
        self.ast = ast.parse(src, '<str>', 'exec')
        self.typer = Typer()
        self.typer.visit(self.ast)
        self.degrouper = Degrouper()
        self.ast = self.degrouper.visit(self.ast)
        symtab = {'s': RGBA(c_uint8), 'd': RGBA(c_uint8), 'p': RGBA(c_uint8)}
        self.coder = Coder(symtab)
        self.ast = self.coder.visit(self.ast)
        self.ostream = StringIO()
        self.writer = Writer(self.ostream)
        self.writer.visit(self.ast)
        self.code = self.ostream.getvalue()

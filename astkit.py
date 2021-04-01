"""AST builder using postfix operations

Preliminary trial version

Examples:

    >>> import ast, astkit as ak
    >>> b = ak.TreeBuilder()
    >>> b.Name('prime').Constant(1).Assign1()
    >>> b.Name('n').Constant(1).Gt().While()
    >>> b.Name('prime').Name('n').IMult()
    >>> b.Name('n').Constant(1).ISub()
    >>> b.end()
    >>> module = b.Module()
    >>> print(ast.unparse(module))
    prime = 1
    while n > 1:
        prime *= n
        n -= 1
    >>> code = compile(module, '<prime>', 'exec')
    >>> lcls = {'n': 3}
    >>> exec(code, globals(), lcls)
    >>> print(lcls)
    {'n': 1, 'prime': 6}
    >>> b.Name('a')
    >>> b.Constant(2)
    >>> b.Add()
    >>> b.Constant(3)
    >>> b.Mult()
    >>> expr = b.Expression()
    >>> print(ast.unparse(expr))
    (a + 2) * 3
    >>> code = compile(expr, '<addmult>', 'eval')
    >>> lcls = {'a': 12}
    >>> print(eval(code, globals(), lcls))
    42

"""

import ast
import collections
import types

class BuildError(Exception):
    pass

class TreeBuilder:
    """Limited Python AST builder

    builder = TreeBuider()
    """
    def __init__(self):
        try:
            self._stack.clear()
        except AttributeError:
            # first time intialization
            self._stack = collections.deque()
            self._load = ast.Load()
            self._store = ast.Store()
            self._mult = ast.Mult()
            self._add = ast.Add()
            self._sub = ast.Sub()
            self._eq = ast.Eq()
            self._noteq = ast.NotEq()
            self._lt = ast.Lt()
            self._lte = ast.LtE()
            self._gt = ast.Gt()
            self._gte = ast.GtE()
            self._assignables = (
                    ast.Name, ast.Attribute, ast.Subscript, ast.Tuple)
        # the line number of the next instruction
        self._lineno = 1

    def push(self, arg, lineno=None, col_offset=None):
        """Place one arguemnt onto the stack

        Position information is added, when needed, and the line number
        is incremented for statements.
        """
        if isinstance(arg, ast.AST):
            if lineno is None:
                lineno = self._lineno
            if col_offset is None:
                col_offset = 0
            arg.lineno = lineno
            arg.col_offset = col_offset
            arg.end_lineno = lineno
            arg.end_col_offset = col_offset
            if isinstance(arg, ast.stmt) and lineno == self._lineno:
                self._lineno += 1
        self._stack.append(arg)

    def push_list(self, args):
        """Place a list of items onto the stack in the order given"""
        for a in args:
            self.push(a)

    def pop(self):
        """Remove and return one item from the stack"""
        try:
            return self._stack.pop()
        except IndexError:
            raise BuildError("One stack item required but the stack is empty")

    def pop_list(self, n_stack_args=None):
        """Remove and return a list of items from the stack

        The last item popped is the first item of the list. Optional argument
        n_stack_args gives the number of items to return. If omitted then
        the entire stack is returned.
        """
        if n_stack_args is None:
            items = list(self._stack)
            self._stack.clear()
        else:
            try:
                items = [self._stack.pop() for i in range(n_stack_args)]
                items.reverse()
            except IndexError:
                msg = f"Too few stack items: {n_stack_args} required"
                raise BuildError(msg)
        return items

    def defer(self, fn):
        """Place a deferred function on the stack

        The function will by method end() with the list of items between
        the defered function and stack top.
        """
        self.push_list([fn, None])

    def Expression(self):
        """Expression AST root node"""
        items = self.pop_list()
        try:
            item = items[0]
        except IndexError:
            msg = "Expression expects 1 stack item: found none"
            raise BuildError(msg)
        if len(items) > 1:
            nitems = len(items)
            msg = f"Expression expects only 1 stack item: {nitems} items found"
            raise BuildError(msg)
        return ast.Expression(items[0], **self._posn(lineno=0))

    def Constant(self, value):
        """Constant AST node"""
        self.push(ast.Constant(value))

    def Name(self, id):
        """Name AST node

        Initially assumed to be an identifier load.
        """
        if not isinstance(id, str):
            raise BuildError("Name argument must be a string")
        self.push(ast.Name(id, self._load))

    def Add(self):
        """Binary addition operation"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Add arguments must be expressions")
        self.push(ast.BinOp(left, self._add, right))

    def Sub(self):
        """Binary subtraction operation"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Sub arguments must be expressions")
        self.push(ast.BinOp(left, self._sub, right))

    def Mult(self):
        """Binary multiplication operation"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Mult arguments must be expressions")
        self.push(ast.BinOp(left, self._mult, right))

    def Eq(self):
        """Equality comparison (binary operation only)"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Eq arguments must be expressions")
        self.push(ast.Compare(left, [self._eq], [right]))

    def NotEq(self):
        """Inequality comparison (binary operation only)"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("NotEq arguments must be expressions")
        self.push(ast.Compare(left, [self._noteq], [right]))

    def Lt(self):
        """Less than comparison (binary operation only)"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Lt arguments must be expressions")
        self.push(ast.Compare(left, [self._lt], [right]))

    def LtE(self):
        """Less that or equal comparison (binary operation only)"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("LtE arguments must be expressions")
        self.push(ast.Compare(left, [self._lte], [right]))

    def Gt(self):
        """Greater than comparison (binary operation only)"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Gt arguments must be expressions")
        self.push(ast.Compare(left, [self._gt], [right]))

    def GtE(self):
        """Greater that or equal comparison (binary operation only)"""
        left, right = self.pop_list(2)
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("GtE arguments must be expressions")
        self.push(ast.Compare(left, [self._gte], [right]))

    def Attribute(self, attr):
        """Attribute access

        Initially assumed to be an attribute get.
        """
        value = self.pop()
        if not isinstance(attr, str):
            raise BuildError("Attribute identifier must be a string")
        if not isinstance(value, ast.expr):
            raise BuildError("Attribute value must be an expression")
        self.push(ast.Attribute(value, attr, self._load))

    def Tuple(self):
        """Tuple literal"""
        def do_tuple(elements):
            for e in elements:
                if not isinstance(e, ast.expr):
                    msg = f"Tuple element {e} not an expression"
                    raise BuildError(msg)
            self.push(ast.Tuple(elements, self._load))

        self.defer(do_tuple)

    def Call(self):
        """Function Call expression"""
        function = self.pop()
        def do_call(arguments):
            for item in arguments:
                if not isinstance(item, ast.expr):
                    msg = f"Function argument {item} is not an expressions"
                    raise BuildError(msg)
            self.push(ast.Call(function, arguments, []))

        if not isinstance(function, ast.expr):
            raise BuildError("The Call target must be an expression")
        self.defer(do_call)

    def Subscript(self):
        """Subscript operation

        <key>, <value> => Subscript
        """
        key, value = self.pop_list(2)
        if not isinstance(key, ast.expr):
            raise BuildError("Subscript key not an expression")
        if not isinstance(value, ast.expr):
            raise BuildError("Subscript value not an expression")
        self.push(ast.Subscript(value, key, ctx=self._load))

    def identifier(self, id_str):
        """Add an identifier string to the stack"""
        if not isinstance(id_str, str):
            raise BuildError("identifier argument must be a string")
        self.push(id_str)

    def arg(self, id_str, annotation_str=None):
        if annotation_str is not None:
            if not isinstance(annotation_str, str):
                msg = "arg only accepts a string annotation"
                raise BuildError(msg)
            a = ast.arg(id_str, ast.Constant(annotation_str))
        else:
            a = ast.arg(id_str)
        self.push(a)

    def arguments(self):
        """Function call arguments"""
        def do_arguments(args):
            arglist = []
            for a in args:
                if isinstance(a, str):
                    a = ast.arg(a, **self._posn())
                elif not isinstance(a, ast.arg):
                    msg = "arguments only allows identifiers or args in argument list"
                    raise BuildError(msg)
                arglist.append(a)
            self.push(ast.arguments([], arglist, vararg=None,
                                    kwonlyargs=[], kwarg=None,
                                    kw_defaults=[], defaults=[]))

        self.defer(do_arguments)

    # Methods beyond this point are AST statements.

    def Assign1(self):
        """Single target assignment"""
        value, target = self.pop_list(2)
        self._check_assignable(target, 'Assign1')
        set_ctx(target, self._store)
        if not isinstance(value, ast.expr):
            msg = "Assign1 value must be expressions"
            raise BuildError(msg)
        self.push(ast.Assign([target], value))

    def IAdd(self):
        """Inplace addition"""
        value, target = self.pop_list(2)
        self._check_assignable(target, 'IAdd')
        if not isinstance(value, ast.expr):
            raise BuildError("IAdd value must be an expression")
        set_ctx(target, self._store)
        self.push(ast.AugAssign(target, self._add, value))

    def ISub(self):
        """Inplace subtraction"""
        value, target = self.pop_list(2)
        self._check_assignable(target, 'ISub')
        if not isinstance(value, ast.expr):
            raise BuildError("ISub value must be an expression")
        set_ctx(target, self._store)
        self.push(ast.AugAssign(target, self._sub, value))

    def IMult(self):
        """Inplace multipilication"""
        value, target = self.pop_list(2)
        self._check_assignable(target, 'IMult')
        if not isinstance(value, ast.expr):
            raise BuildError("IMult value must be an expression")
        set_ctx(target, self._store)
        self.push(ast.AugAssign(target, self._mult, value))

    def Assign(self):
        """Multi target assignment"""
        def do_assign(args):
            if len(args) < 2:
                msg = "Assign requires one or more targets and a value"
                raise BuildError(msg)
            targets = args[0:-1]
            value = args[-1]
            if not isinstance(value, ast.expr):
                msg = f"Assignment right hand node {value} not an expression"
                raise BuildError(msg)
            for t in targets:
                self._check_assignable(t, 'Assign')
                set_ctx(t, self._store)
            return ast.Assign(targets, value, **self._posn_incr())

        self.defer(do_assign)

    def If(self):
        """If statement"""
        test = self.pop()
        def do_if(body):
            if not body:
                msg = "If statement must have at least 1 body statement"
                raise BuildError(msg)
            for item in body:
                if not isinstance(item, ast.stmt):
                    msg = f"If statement body item {item} not a statement"
                    raise BuildError(msg)
            return ast.If(test, body, [], **self._posn(lineno=lineno))

        lineno = self._lineno
        self._lineno += 1
        self.defer(do_if)

    def While(self):
        """While statement"""
        test = self.pop()
        def do_while(body):
            if not body:
                msg = "While statement must have at least 1 body statement"
                raise BuildError(msg)
            for item in body:
                if not isinstance(item, ast.stmt):
                    msg = f"While statement body item {item} not a statement"
                    raise BuildError(msg)
            self.push(ast.While(test, body, []), lineno=lineno)

        if not isinstance(test, ast.expr):
            raise BuildError("The While test must be an expression")
        lineno = self._lineno
        self._lineno += 1
        self.defer(do_while)

    def Expr(self):
        """Makes an expression a statement (e.g. a function call)"""
        expression = self.pop()
        if not isinstance(expression, ast.expr):
            raise BuildError("The Expr argument must be an expression")
        self.push(ast.Expr(expression))

    def Pass(self):
        """Pass instruction"""
        self.push(ast.Pass())

    def FunctionDef(self):
        """Function definition"""
        name, args = self.pop_list(2)
        def do_functiondef(body):
            for item in body:
                if not isinstance(item, ast.stmt):
                    msg = "Only statements allowed in FunctionDef body"
                    raise BuildError(msg)
            fd = ast.FunctionDef(name, args, body, decorator_list=[])
            self.push(fd, lineno=lineno)

        lineno = self._lineno
        self._lineno += 1
        self.defer(do_functiondef)

    def Return(self):
        """Return value"""
        value = self.pop()
        if not isinstance(value, ast.expr):
            raise BuildError("Return expects an expression")
        self.push(ast.Return(value))

    def Module(self):
        """Module AST root node"""
        items = self.pop_list()
        for item in items:
            if not isinstance(item, ast.stmt):
                msg = f"Module item {item} is not a statement"
                raise BuildError(msg)
        module = ast.Module(items, [], **self._posn(lineno=0))
        self.__init__()
        return module

    # Statement helpers.

    def end(self):
        """Evoke a While, If, Assign, FunctionDef or Call deferred method"""
        try:
            arg = self._stack.pop()
        except IndexError:
            raise BuildError("Expected something to precede end")
        args = []
        while arg is not None:
            args.append(arg)
            try:
                arg = self._stack.pop()
            except IndexError:
                raise BuildError("No corresponding block statement found")
        func = self._stack.pop()
        args.reverse()
        return func(args)

    def orelse(self):
        """Start an else block for an If statement"""
        raise NotImplementedError("ToDo")

    def elseif(self):
        """Start an elif block for an If statement"""
        raise NotImplementedError("ToDo")

    # General helpers

    def _posn(self, lineno=None, col_offset=None):
        """Return a keyword argument dictionary for AST position"""
        if lineno is None:
            lineno = self._lineno
        if col_offset is None:
            col_offset = 0
        return {'lineno': lineno,
                'col_offset': col_offset,
                'end_lineno': lineno,
                'end_col_offset': col_offset}

    def _posn_incr(self):
        """Return AST position keywords and increment line number"""
        posn = self._posn()
        self._lineno += 1
        return posn

    def _check_assignable(self, node, method_name):
        """Raise a BuildError is node is not an assignable expression"""
        if not isinstance(node, self._assignables):
            msg = f"{method_name} target {node} is not an assignable expression"
            raise BuildError(msg)

def set_ctx(node, ctx):
    node.ctx = ctx
    if isinstance(node, ast.Tuple):
        for e in node.elts:
            set_ctx(e, ctx)

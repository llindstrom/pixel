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

def stackop(method):
    """Decorate a method that replaces 1 or more items on the stack with 1 item

    The number of items popped off the stack are enough to fill the
    method's non-self arguments. The method's return value is pushed
    onto the stack.
    """
    n_stack_args = method.__code__.co_argcount - 1  # assume 'self' arg.
    if n_stack_args == 0:
        def stackop0_wrapper(self):
            self._stack.append(method(self))
        wrapper = stackop0_wrapper
    else:
        def stackopn_wrapper(self):
            try:
                items = [self._stack.pop() for i in range(n_stack_args)]
                items.reverse()
            except IndexError:
                msg = f"{method.__name__} requires {n_stack_args} stack items"
                raise BuildError(msg)
            self._stack.append(method(self, *items))
        wrapper = stackopn_wrapper

    # Update name and docs for introspection
    wrapper.__name__ = f'stackop_{method.__name__}'
    wrapper.__doc__ = method.__doc__

    return wrapper

def stackappend(method):
    """Decorate a method that adds 1 item to the stack

    The method may accept call arguments. Its return value is pushed
    onto the stack.
    """
    def stackappend_wrapper(self, *args):
        self._stack.append(method(self, *args))

    # Update name and docs for introspection
    stackappend_wrapper.__name__ = f'stackappend_{method.__name__}'
    stackappend_wrapper.__doc__ = method.__doc__

    return stackappend_wrapper

def stackflush(method):
    """Decorate an AST tree root node method

    Remove all arguments from the stack and pass to the method as a
    list with the last item off the stack the first item in the list.
    The method is expected to have two arguments, 'self' and the stack list.
    Its return value is passed back to the caller.
    """
    def stackflush_wrapper(self):
        items = list(self._stack)
        self.__init__()
        return method(self, items)

    # Update name and docs for introspection
    stackflush_wrapper.__name__ = f'stackflush_{method.__name__}'
    stackflush_wrapper.__doc__ = method.__doc__

    return stackflush_wrapper

def deferred(method):
    """Decorate a method as a block start point

    Places None on the stack as a stack start marker. This decorator
    must precede other decorators.

    eg:

        @deferred
        @stackop
        def Something(....
    """
    def deferred_wrapper(self, *args):
        retval = method(self, *args)
        self._stack.append(None)
        return retval

    # Update name and docs for introspection
    deferred_wrapper.__name__ = f'deferred_{method.__name__}'
    deferred_wrapper.__doc__ = method.__doc__

    return deferred_wrapper

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

    @stackflush
    def Expression(self, items):
        """Expression AST root node"""
        try:
            item = items[0]
        except IndexError:
            msg = "Expression expects 1 stack item: found none"
            raise BuildError(msg)
        if len(items) > 1:
            nitems = len(items)
            msg = f"Expression expects only 1 stack item: found {nitems} items"
            raise BuildError(msg)
        return ast.Expression(items[0], **self._posn(lineno=0))

    @stackappend
    def Constant(self, value):
        """Constant AST node"""
        return ast.Constant(value, **self._posn())

    @stackappend
    def Name(self, id):
        """Name AST node

        Initially assumed to be an identifier load.
        """
        if not isinstance(id, str):
            raise BuildError("Name argument must be a string")
        return ast.Name(id, self._load, **self._posn())

    @stackop
    def Add(self, left, right):
        """Binary addition operation"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Add arguments must be expressions")
        return ast.BinOp(left, self._add, right, **self._posn())

    @stackop
    def Sub(self, left, right):
        """Binary subtraction operation"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Sub arguments must be expressions")
        return ast.BinOp(left, self._sub, right, **self._posn())

    @stackop
    def Mult(self, left, right):
        """Binary multiplication operation"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Mult arguments must be expressions")
        return ast.BinOp(left, self._mult, right, **self._posn())

    @stackop
    def Eq(self, left, right):
        """Equality comparison (binary operation only)"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Eq arguments must be expressions")
        return ast.Compare(left, [self._eq], [right], **self._posn())

    @stackop
    def NotEq(self, left, right):
        """Inequality comparison (binary operation only)"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("NotEq arguments must be expressions")
        return ast.Compare(left, [self._noteq], [right], **self._posn())

    @stackop
    def Lt(self, left, right):
        """Less than comparison (binary operation only)"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Lt arguments must be expressions")
        return ast.Compare(left, [self._lt], [right], **self._posn())

    @stackop
    def LtE(self, left, right):
        """Less that or equal comparison (binary operation only)"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("LtE arguments must be expressions")
        return ast.Compare(left, [self._lte], [right], **self._posn())

    @stackop
    def Gt(self, left, right):
        """Greater than comparison (binary operation only)"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("Gt arguments must be expressions")
        return ast.Compare(left, [self._gt], [right], **self._posn())

    @stackop
    def GtE(self, left, right):
        """Greater that or equal comparison (binary operation only)"""
        if not (isinstance(left, ast.expr) or isinstance(right, ast.expr)):
            raise BuildError("GtE arguments must be expressions")
        return ast.Compare(left, [self._gte], [right], **self._posn())

    @stackop
    def Attribute(self, value, attr):
        """Attribute access

        Initially assumed to be an attribute get.
        """
        if not isinstance(attr, str):
            raise BuildError("Attribute identifier must be a string")
        if not isinstance(value, ast.expr):
            raise BuildError("Attribute value must be an expression")
        return ast.Attribute(value, attr, self._load, **self._posn())

    @deferred
    @stackop
    def Tuple(self):
        """Tuple literal"""
        def do_tuple(elements):
            for e in elements:
                if not isinstance(e, ast.expr):
                    msg = f"Tuple element {e} not an expression"
                    raise BuildError(msg)
            return ast.Tuple(elements, self._load, **self._posn())

        return do_tuple

    @deferred
    @stackop
    def Call(self, function):
        """Function Call expression"""
        def do_call(arguments):
            for item in arguments:
                if not isinstance(item, ast.expr):
                    msg = f"Function argument {item} is not an expressions"
                    raise BuildError(msg)
            return ast.Call(function, arguments, [], **self._posn())

        if not isinstance(function, ast.expr):
            raise BuildError("The Call target must be an expression")
        return do_call

    @stackappend
    def identifier(self, id_str):
        """Add an identifier string to the stack"""
        if not isinstance(id_str, str):
            raise BuildError("identifier argument must be a string")
        return id_str

    @deferred
    @stackop
    def arguments(self):
        """Function call arguments"""
        def do_arguments(args):
            arglist = []
            for a in args:
                if not isinstance(a, str):
                    msg = "arguments only allows identifiers in argument list"
                    raise BuildError(msg)
                arglist.append(ast.arg(a, **self._posn()))
            return ast.arguments([], arglist,
                                 vararg=None, kwonlyargs=[], kwarg=None,
                                 kw_defaults=[], defaults=[], **self._posn())

        return do_arguments

    # Methods beyond this point are AST statements.

    @stackop
    def Assign1(self, target, value):
        """Single target assignment"""
        self._check_assignable(target, 'Assign1')
        set_ctx(target, self._store)
        if not isinstance(value, ast.expr):
            msg = "Assign1 value must be expressions"
            raise BuildError(msg)
        return ast.Assign([target], value, **self._posn_incr())

    @stackop
    def IAdd(self, target, value):
        """Inplace addition"""
        self._check_assignable(target, 'IAdd')
        if not isinstance(value, ast.expr):
            raise BuildError("IAdd value must be an expression")
        set_ctx(target, self._store)
        return ast.AugAssign(target, self._add, value, **self._posn_incr())

    @stackop
    def ISub(self, target, value):
        """Inplace subtraction"""
        self._check_assignable(target, 'ISub')
        if not isinstance(value, ast.expr):
            raise BuildError("ISub value must be an expression")
        set_ctx(target, self._store)
        return ast.AugAssign(target, self._sub, value, **self._posn_incr())

    @stackop
    def IMult(self, target, value):
        """Inplace multipilication"""
        self._check_assignable(target, 'IMult')
        if not isinstance(value, ast.expr):
            raise BuildError("IMult value must be an expression")
        set_ctx(target, self._store)
        return ast.AugAssign(target, self._mult, value, **self._posn_incr())

    @deferred
    @stackop
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

        return do_assign

    @deferred
    @stackop
    def If(self, test):
        """If statement"""
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
        return do_if

    @deferred
    @stackop
    def While(self, test):
        """While statement"""
        def do_while(body):
            if not body:
                msg = "While statement must have at least 1 body statement"
                raise BuildError(msg)
            for item in body:
                if not isinstance(item, ast.stmt):
                    msg = f"While statement body item {item} not a statement"
                    raise BuildError(msg)
            return ast.While(test, body, [], **self._posn(lineno=lineno))

        if not isinstance(test, ast.expr):
            raise BuildError("The While test must be an expression")
        lineno = self._lineno
        self._lineno += 1
        return do_while

    @stackop
    def Expr(self, expression):
        """Makes an expression a statement (e.g. a function call)"""
        if not isinstance(expression, ast.expr):
            raise BuildError("The Expr argument must be an expression")
        return ast.Expr(expression, **self._posn_incr())

    @stackappend
    def Pass(self):
        return ast.Pass(**self._posn_incr())

    @deferred
    @stackop
    def FunctionDef(self, name, args):
        """Function definition"""
        def do_functiondef(body):
            for item in body:
                if not isinstance(item, ast.stmt):
                    msg = "Only statements allowed in FunctionDef body"
                    raise BuildError(msg)
            FD = ast.FunctionDef
            return FD(name, args, body, decorator_list=[],
                      **self._posn(lineno=lineno))

        lineno = self._lineno
        self._lineno += 1
        return do_functiondef

    @stackop
    def Return(self, value):
        """Return value"""
        if not isinstance(value, ast.expr):
            raise BuildError("Return expects an expression")
        return ast.Return(value, **self._posn_incr())

    @stackflush
    def Module(self, items):
        """Module AST root node"""
        for item in items:
            if not isinstance(item, ast.stmt):
                msg = f"Module item {item} is not a statement"
                raise BuildError(msg)
        return ast.Module(items, [], **self._posn(lineno=0))

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
        node = func(args)
        if node is not None:
            self._stack.append(node)

    def orelse(self):
        """Start an else block for an If statement"""
        raise NotImplementedError("ToDo")

    def elseif(self):
        """Start an elif block for an If statement"""
        raise NotImplementedError("ToDo")

    # General helpers

    def _posn(self, lineno=None, col_offset=None):
        if lineno is None:
            lineno = self._lineno
        if col_offset is None:
            col_offset = 0
        return {'lineno': lineno,
                'col_offset': col_offset,
                'end_lineno': lineno,
                'end_col_offset': col_offset}

    def _posn_incr(self):
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

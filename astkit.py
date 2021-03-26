"""AST builder using postfix operations

Preliminary trial version

Examples:
    
    >>> import ast, astkit as ak
    >>> build = ak.TreeBuilder()
    >>> module = (build
    ...     .Name('prime').Constant(1).Assign1()
    ...     .Name('n').While()
    ...     .Name('prime').Name('n').IMult()
    ...     .Name('n').Constant(1).ISub()
    ...     .end()
    ...     .Module())
    >>> print(ast.unparse(module))
    prime = 1
    while n:
        prime *= n
        n -= 1
    >>> code = compile(module, '<prime>', 'exec')
    >>> lcls = {'n': 3}
    >>> exec(code, globals(), lcls)
    >>> print(lcls)
    {'n': 0, 'prime': 6}
    >>> expr = (build
    ...     .Name('a')
    ...     .Constant(2)
    ...     .Add()
    ...     .Constant(3)
    ...     .Mult()
    ...     .Expression())
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
        def wrapper(self):
            self._stack.append(method(self))
            return self
    else:
        def wrapper(self):
            try:
                items = [self._stack.pop() for i in range(n_stack_args)]
                items.reverse()
            except IndexError:
                msg = f"{method.__name__} requires {n_stack_args} stack items"
                raise BuildError(msg)
            self._stack.append(method(self, *items))
            return self

    wrapper.__doc__ = method.__doc__
    return wrapper

def stackappend(method):
    """Decorate a method that adds 1 item to the stack

    The method may accept call arguments. Its return value is pushed
    onto the stack.
    """
    def wrapper(self, *args):
        self._stack.append(method(self, *args))
        return self

    wrapper.__doc__ = method.__doc__
    return wrapper

def stackflush(method):
    """Decorate an AST tree root node method

    Remove all arguments from the stack and pass to the method as a
    list with the last item off the stack the first item in the list.
    The method is expected to have two arguments, 'self' and the stack list.
    Its return value is passed back to the caller.
    """
    def wrapper(self):
        items = list(self._stack)
        self.__init__()
        return method(self, items)

    wrapper.__doc__ = method.__doc__
    return wrapper

def deferred(method):
    """Decorate a method as a block start point
    
    Places None on the stack as a stack start marker. This decorator
    must precede other decorators.

    eg:

        @deferred
        @stackop
        def Something(....
    """
    def wrapper(self, *args):
        retval = method(self, *args)
        self._stack.append(None)
        return retval

    return wrapper

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

    # Methods beyond this point are AST statements.

    @stackop
    def Assign1(self, target, value):
        """Single target assignment"""
        if isinstance(target, ast.Name):
            target.ctx = self._store
        lineno = self._lineno
        if not (target.lineno == value.lineno == lineno):
            msg = "Assign1 arguments must be expressions"
            raise BuildError(msg)
        return ast.Assign([target], value, **self._posn_incr())

    @stackop
    def IAdd(self, target, value):
        """Inplace addition"""
        if not isinstance(target, ast.expr):
            raise BuildError("IAdd target must be an expression")
        if not isinstance(value, ast.expr):
            raise BuildError("IAdd value must be an expression")
        if isinstance(target, ast.Name):
            target.ctx = self._store
        return ast.AugAssign(target, self._add, value, **self._posn_incr())

    @stackop
    def ISub(self, target, value):
        """Inplace subtraction"""
        if not isinstance(target, ast.expr):
            raise BuildError("ISub target must be an expression")
        if not isinstance(value, ast.expr):
            raise BuildError("ISub value must be an expression")
        if isinstance(target, ast.Name):
            target.ctx = self._store
        return ast.AugAssign(target, self._sub, value, **self._posn_incr())

    @stackop
    def IMult(self, target, value):
        """Inplace multipilication"""
        if not isinstance(target, ast.expr):
            raise BuildError("IMult target must be an expression")
        if not isinstance(value, ast.expr):
            raise BuildError("IMult value must be an expression")
        if isinstance(target, ast.Name):
            target.ctx = self._store
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
                if not isinstance(t, ast.expr):
                    msg = f"Assign target {t} is not an expression"
                    raise BuildError(msg)
                if isinstance(t, ast.Name):
                    t.ctx = self._store
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

    @stackop
    def Expr(self, expression):
        """Makes an expression a statement (e.g. a function call)"""
        if not isinstance(expression, ast.expr):
            raise BuildError("The Expr argument must be an expression")
        return ast.Expr(expression, **self._posn_incr())

    @stackappend
    def Pass(self):
        return ast.Pass(**self._posn_incr())

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
        self._stack.append(func(args))
        return self

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

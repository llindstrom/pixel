"""AST builder using postfix operations

Preliminary trial version

Examples:
    
    >>> import ast, astkit as ak
    >>> build = ak.TreeBuilder()
    >>> build.Constant(2)
    >>> build.Name('a')
    >>> build.Mult()
    >>> build.Constant(4)
    >>> build.Add()
    >>> expr = build.Expression()
    >>> expr
    <ast.Expression at 0xb34e9490>
    >>> print(ast.unparse(expr))
    2 * a + 4

    >>> build.Assign()
    >>> build.Name('meaning_of_life')
    >>> build.Name('the_altimate_answer')
    >>> build.Constant(42)
    >>> build.end()
    >>> module = build.Module()
    >>> print(ast.dump(module, indent=4))
    Module(
        body=[
            Assign(
                targets=[
                    Name(id='meaning_of_life', ctx=Store()),
                    Name(id='the_altimate_answer', ctx=Store())],
                value=Constant(value=42))],
        type_ignores=[])
    >>> print(ast.unparse(module))
    meaning_of_life = the_altimate_answer = 42
    
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

def stackbegin(method):
    """Decorate a method as a block start point
    
    Places None on the stack as a stack start marker. This decorator
    must follow other decorators.

    eg:

        @stackbegin
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
        return ast.Name(id, self._load, **self._posn())

    @stackop
    def Mult(self, left, right):
        """Binary multiplication operation"""
        return ast.BinOp(left, self._mult, right, **self._posn())

    @stackop
    def Add(self, left, right):
        """Binary addition operation"""
        return ast.BinOp(left, self._add, right, **self._posn())

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
        if isinstance(target, ast.Name):
            target.ctx = self._store
        lineno = self._lineno
        if not (target.lineno == value.lineno == lineno):
            msg = "IAdd arguments must be expressions"
            raise BuildError(msg)
        return ast.AugAssign(target, self._add, value, **self._posn_incr())

    @stackop
    def ISub(self, target, value):
        """Inplace subtraction"""
        if isinstance(target, ast.Name):
            target.ctx = self._store
        lineno = self._lineno
        if not (target.lineno == value.lineno == lineno):
            msg = "ISub arguments must be expressions"
            raise BuildError(msg)
        return ast.AugAssign(target, self._sub, value, **self._posn_incr())

    @stackbegin
    @stackop
    def Assign(self):
        """Multi target assignment"""
        def do_assign(args):
            if len(args) < 2:
                msg = "Assign requires one or more targets and a value"
                raise BuildError(msg)
            if self._lineno > lineno:
                msg = "Assignment arguments must be expressions only"
                raise BuildError(msg)
            targets = args[0:-1]
            value = args[-1]
            for t in targets:
                if isinstance(t, ast.Name):
                    t.ctx = self._store
            return ast.Assign(targets, value, **self._posn_incr())

        lineno = self._lineno
        return do_assign

    @stackbegin
    @stackop
    def If(self, test):
        """If statement"""
        def do_if(body):
            if not body:
                msg = "If statement must have at least 1 body statement"
                raise BuildError(msg)
            prev_lineno = self._lineno
            self._lineno = lineno
            retval = ast.If(test, body, [], **self._posn())
            self._lineno = prev_lineno
            return retval

        lineno = self._lineno
        self._lineno += 1
        return do_if

    @stackflush
    def Module(self, items):
        """Module AST root node"""
        return ast.Module(items, [], **self._posn(lineno=0))
            
    # Statement helpers.

    def end(self):
        """End a While, If, Assign, or FunctionDef statement"""
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

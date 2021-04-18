"""Determine useless names of a basic block

https://www.csd.uwo.ca/~mmorenom/CS447/Lectures/CodeOptimization.html/
node4.html#algoUuselessNamesOfABasicBlock
"""

import cfg
import sys
import ast

def lives(block):
    iblock = iter(block)

    # A is the set of variables in the block
    A = next(iblock).get_identifiers()

    # L is the collection of variables in A also in other reachable blocks.
    L = set()
    for other in iblock:
        L |= A & other.get_identifiers()
    return L

def useless(block):
    D = set()
    L = lives(block)
    for stmt in block.body[-1::-1]:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    L.add(node.id)
                else:
                    D.add(node.id)
    return D - L

def test():
    assert len(sys.argv) == 2
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        module_ast = ast.parse(f.read(), 'test_blitter.py', 'exec')
    mapper = cfg.ControlFlowMapper()
    mapper.visit(module_ast)
    graphs = mapper.graphs
    for fname, graph in graphs.items():
        print(f"{fname}()")
        cfg.pprint(graph)
        print()
        for block in graph:
            U = useless(block)
            print(f"L{block.label:<2}: {U}")

if __name__ == '__main__':
    test()

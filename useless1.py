"""Determine useless names of a basic block

https://www.csd.uwo.ca/~mmorenom/CS447/Lectures/CodeOptimization.html/
node4.html#algoUuselessNamesOfABasicBlock
"""

import cfg
import sys
import ast

def vars(node):
    return set(n.id for n in ast.walk(node) if isinstance(n, ast.Name))

def find(A, E, graph, V):
    L = set()
    if not E:
        return L
    E2 = set()
    for label in E:
        if label in V:
            continue
        block = graph[label]
        for stmt in block:
            if isinstance(stmt, tuple):
                L |= A & vars(stmt[0])
                E2.add(stmt[1])
            elif isinstance(stmt, ast.AST):
                L |= A & vars(stmt)
            else:
                E2.add(stmt)
        V.add(label)
    return L | find(A, E2, graph, V)

def lives(label, graph):
    A = set()  # All variables in the block
    E = set()  # Graph edges leaving the block as a set of labels`
    block = graph[label]
    V = set([label])  # Blocks already visited

    # Collect A and E for the block.
    for stmt in block:
        if isinstance(stmt, tuple):
            A |= vars(stmt[0])
            E.add(stmt[1])
        elif isinstance(stmt, ast.AST):
            A |= vars(stmt)
        else:
            E.add(stmt)
    
    # Build L from elements in A found in other blocks.
    return find(A, E, graph, V)

def useless(label, graph):
    block = graph[label]
    D = set()
    L = lives(label, graph)
    for stmt in block[-1::-1]:
        if isinstance(stmt, ast.Assign):
            loads = {node.id for node in ast.walk(stmt.value)
                     if isinstance(node, ast.Name)}
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    if target.id not in L:
                        D.add(target.id)
                    else:
                        L.update(loads)
                elif isinstance(target, ast.Tuple):
                    for node in target.elts:
                        if isinstance(node, ast.Name):
                            if node.id not in L:
                                D.add(node.id)
                            else:
                                L.update(loads)
        elif isinstance(stmt, ast.AugAssign):
            loads = {node.id for node in ast.walk(stmt.value)
                     if isinstance(node, ast.Name)}
            target = stmt.target
            if isinstance(target, ast.Name):
                if target.id not in L:
                    D.add(target.id)
                else:
                    L.add(target.id)
                    L.update(loads)
        # What about attribute and index assignment?
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
        for label in graph.keys():
            U = useless(label, graph)
            print(f"L{label:<2}: {U}")

if __name__ == '__main__':
    test()

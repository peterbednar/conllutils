
from . import FORM
from . import Sentence, DependencyTree

import numpy as np

DEL = "del"
INS = "ins"
SUB = "sub"
TRN = "trn"

def default_token_cost(t1, t2, opr):
    if opr == DEL:
        return 1    # insertion
    if opr == INS:
        return 1    # deletion
    if opr == TRN:
        return 1    # transposition
    return 0 if t1[FORM] == t2[FORM] else 1  # substitution

def levenshtein_distance(s1, s2, cost=default_token_cost, damerau=False, return_oprs=False):
    def _equals(t1, t2):
        return cost(t1, t2, SUB) == 0

    n = len(s1)
    m = len(s2)
    d = np.zeros((n + 1, m + 1), dtype=np.float)

    for i in range(1, n + 1):
        d[i, 0] = d[i-1, 0] + cost(s1[i-1], None, DEL)      # deletion
    for j in range(1, m + 1):
        d[0, j] = d[0, j-1] + cost(None, s2[j-1], INS)      # insertion

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i, j] = min(
                d[i-1, j] + cost(s1[i-1], None, DEL),      # deletion
                d[i, j-1] + cost(None, s2[j-1], INS),      # insertion
                d[i-1, j-1] + cost(s1[i-1], s2[j-1], SUB)  # substitution
                )
            if damerau and i > 1 and j > 1 and _equals(s1[i-1], s2[j-2]) and _equals(s1[i-2], s2[i-1]):
                d[i, j] = min(
                    d[i, j],
                    d[i-2, j-2] + cost(s1[i-2], s2[i-2], TRN)  # transposition
                    )
    if not return_oprs:
        return d[n, m]

    i = n
    j = m
    oprs = []
    while i > 0 or j > 0:
        neighbours = []
        if damerau and i > 1 and j > 1 and _equals(s1[i-1], s2[j-2]) and _equals(s1[i-2], s2[i-1]):
            neighbours.append((TRN, i-2, j-2))
        if i > 0 and j > 0:
            neighbours.append((SUB, i-1, j-1))
        if j > 0:
            neighbours.append((INS, i, j-1))
        if i > 0:
            neighbours.append((DEL, i-1, j))
        opr = min(neighbours, key=lambda x: d[x[1], x[2]])
        if d[opr[1], opr[2]] != d[i, j]:
            oprs.append(opr)
        i = opr[1]
        j = opr[2]
    oprs.reverse()

    return oprs

class _AnnotatedNode(object):

    def __init__(self, node):
        self.node = node
        self.index = -1
        self.leftmost = None
        self.children = []

    def collect(self):
        return self._collect([], [])

    def _collect(self, nodes, l):
        for child in self.children:
            nodes, l = child._collect(nodes, l)
        nodes.append(self.node)
        l.append(self.leftmost.index)
        return nodes, l

    @staticmethod
    def build(node, index=0):
        anode = _AnnotatedNode(node)
        for child in node.children:
            achild = _AnnotatedNode.build(child, index)
            index = achild.index + 1
            anode.children.append(achild)
        anode.index = index
        if anode.children:
            anode.leftmost = anode.children[0].leftmost
        else:
            anode.leftmost = anode
        return anode

def _annotate(root):
    nodes, l = _AnnotatedNode.build(root).collect()
    keyroots = []
    n = len(l)
    for i in range(n):
        is_root = True
        for j in range(i + 1, n):
            if l[i] == l[j]:
                is_root = False
                break
        if is_root:
            keyroots.append(i)
    return nodes, l, keyroots

def _treedist(i, j, l1, l2, nodes1, nodes2, TD, cost):
    n = i - l1[i] + 2
    m = j - l2[j] + 2
    d = np.zeros((n, m), dtype=np.float)
    i_off = l1[i] - 1
    j_off = l2[j] - 1

    for x in range(1, n):
        d[x, 0] = d[x-1, 0] + cost(nodes1[x+i_off], None, DEL)      # delete
    for y in range(1, m):
        d[0, y] = d[0, y-1] + cost(None, nodes2[y+j_off], INS)      # insert

    for x in range(1, n):
        for y in range(1, m):
            xi = x + i_off
            yj = y + j_off
            if l1[i] == l1[xi] and l2[j] == l2[yj]:
                d[x, y] = min(
                    d[x-1, y] + cost(nodes1[xi], None, DEL),        # delete
                    d[x, y-1] + cost(None, nodes2[yj], INS),        # insert
                    d[x-1, y-1] + cost(nodes1[xi], nodes2[yj], SUB) # substitute
                )
                TD[xi, yj] = d[x, y]
            else:
                d[x, y] = min(
                    d[x-1, y] + cost(nodes1[xi], None, DEL),
                    d[x, y-1] + cost(None, nodes2[yj], INS),
                    d[l1[xi]-1-i_off, l2[yj]-1-j_off] + TD[xi, yj]
                )

def default_node_cost(n1, n2, opr):
    t1 = None if n1 is None else n1.token
    t2 = None if n2 is None else n2.token
    return default_token_cost(t1, t2, opr)

def tree_edit_distance(t1, t2, cost=default_node_cost):

    def _get_root(t):
        if isinstance(t, DependencyTree):
            return t.root
        if isinstance(t, Sentence):
            return t.as_tree().root
        return t

    nodes1, l1, keyroots1 = _annotate(_get_root(t1))
    nodes2, l2, keyroots2 = _annotate(_get_root(t2))

    n = len(nodes1)
    m = len(nodes2)
    TD = np.zeros((n, m), dtype=np.float)
    for i in keyroots1:
        for j in keyroots2:
            _treedist(i, j, l1, l2, nodes1, nodes2, TD, cost)

    return TD[n-1, m-1]
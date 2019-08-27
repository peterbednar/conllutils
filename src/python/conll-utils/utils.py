import re
import random
import gzip
import lzma
import os
from io import  TextIOWrapper
from collections import OrderedDict, Counter 

ID, FORM, LEMMA, UPOS, XPOS, FEATS, HEAD, DEPREL, DEPS, MISC, FORM_NORM, LEMMA_NORM, \
FORM_CHARS, LEMMA_CHARS, FORM_NORM_CHARS, LEMMA_NORM_CHARS, UPOS_FEATS = range(17)

EMPTY = 0
MULTIWORD = 1

FIELD_TO_STR = ["id", "form", "lemma", "upos", "xpos", "feats", "head", "deprel", "deps", "misc",
                "form_norm", "lemma_norm", "form_chars", "lemma_chars", "form_norm_chars", "lemma_norm_chars",
                "upos_feats"]
STR_TO_FIELD = {k : v for v, k in enumerate(FIELD_TO_STR)}

def str_to_field(s):
    return STR_TO_FIELD[s.lower()]

def field_to_str(f):
    return FIELD_TO_STR[f]

class Token(dict):

    def __init(self, fields):
        super().__init__(fields)

    @property
    def is_empty(self):
        id = self[ID]
        return id[2] == EMPTY if isinstance(id, tuple) else False

    @property
    def is_multiword(self):
        id = self[ID]
        return id[2] == MULTIWORD if isinstance(id, tuple) else False

class Sentence(list):

    def __init__(self, tokens, metadata=None):
        super().__init__(tokens)
        self.tokens = self
        self.metadata = metadata

    def get(self, id):
        for token in self.tokens[id-1:]:
            if token[ID] == id:
                return token
        raise IndexError(f"token with id {id} not found")

    def as_tree(self):
        return DependencyTree(self)

class Node:

    def __init__(self, token, parent):
        self.token = token
        self.parent = parent
        self.children = []

    @property
    def is_root(self):
        return self.parent == None

    @property
    def deprel(self):
        return self.token[DEPREL]

class DependencyTree:

    def __init__(self, sentence):
        self.root = DependencyTree.build(sentence)
        self.metadata = sentence.metadata

    @staticmethod
    def build(sentence):
        return DependencyTree._build(sentence, None)

    @staticmethod
    def _build(sentence, parent):
        id = parent.token[ID] if parent is not None else 0
        
        for token in sentence:
            if token[ID] == id:
                node = Node(token, parent)
                DependencyTree._build(sentence, node)
                if parent == None:
                    return node
                else:
                    parent.children.append(node)

        return parent

_NUM_REGEX = re.compile("[0-9]+|[0-9]+\\.[0-9]+|[0-9]+[0-9,]+")
NUM_NORM = u"__number__"
_NUM_NORM_CHARS = (u"0",)

_CHARS_FIELDS = {FORM: FORM_CHARS, LEMMA: LEMMA_CHARS, FORM_NORM: FORM_NORM_CHARS, LEMMA_NORM: LEMMA_NORM_CHARS}

def normalize_lower(field, value):
    if value is None:
        return None
    if field == FORM or field == LEMMA:
        return value.lower()
    return value

def normalize_default(field, value):
    if value is None:
        return None
    if field == FORM or field == LEMMA:
        if _NUM_REGEX.match(value):
            return NUM_NORM
        return value.lower()
    return value

def splitter_default(field, value):
    if value is None:
        return None
    if (field == FORM_NORM or field == LEMMA_NORM) and value == NUM_NORM:
        return _NUM_NORM_CHARS
    return tuple(value)

def read_conllu(file, skip_empty=True, skip_multiword=True, parse_feats=False, parse_deps=False, upos_feats=True,
                normalize=normalize_default, splitter=splitter_default):

    def _parse_sentence(lines, comments):
        tokens = []
        metadata = _parse_metadata(comments)

        for line in lines:
            token = _parse_token(line)
            if skip_empty and token.is_empty:
                continue
            if skip_multiword and token.is_multiword:
                continue
            tokens.append(token)

        return Sentence(tokens, metadata)

    def _parse_metadata(comments):
        return [comment[1:].strip() for comment in comments]

    def _parse_token(line):
        fields = line.split("\t")
        fields = {f : fields[f] for f in range(max(len(fields), MISC + 1))}

        if "." in fields[ID]:
            token_id, index = fields[ID].split(".")
            id = (int(token_id), int(index), EMPTY)
        elif "-" in fields[ID]:
            start, end = fields[ID].split("-")
            id = (int(start), int(end), MULTIWORD)
        else:
            id = int(fields[ID])
        fields[ID] = id

        for f in [FORM, LEMMA, UPOS, XPOS, FEATS, HEAD, DEPREL, DEPS, MISC]:
            if f not in fields or fields[f] == "_":
                fields[f] = None

        if upos_feats:
            upos = fields[UPOS]
            feats = fields[FEATS]
            if upos:
                tag = f"POS={upos}|{feats}" if feats else f"POS={upos}"
            else:
                tag = feats
            fields[UPOS_FEATS] = tag

        if parse_feats and fields[FEATS]:
            fields[FEATS] = _parse_feats(fields[FEATS])

        if fields[HEAD]:
            fields[HEAD] = int(fields[HEAD])

        if parse_deps and fields[DEPS]:
            fields[DEPS] = _parse_deps(fields[DEPS])

        if normalize:
            fields[FORM_NORM] = normalize(FORM, fields[FORM])
            fields[LEMMA_NORM] = normalize(LEMMA, fields[LEMMA])

        if splitter:
            for (f, ch) in _CHARS_FIELDS.items():
                fields[ch] = splitter(f, fields[f])

        return Token(fields)

    def _parse_feats(str):
        feats = OrderedDict()
        for key, value in [feat.split("=") for feat in str.split("|")]:
            if "," in value:
                value = value.split(",")
            feats[key] = value
        return feats

    def _parse_deps(str):
        return list(map(lambda rel: (int(rel[0]), rel[1]), [rel.split(":") for rel in str.split("|")]))

    lines = []
    comments = []
    if isinstance(file, str):
        file = open(file, "rt", encoding="utf-8")
    with file:
        for line in file:
            line = line.rstrip("\r\n")
            if line.startswith("#"):
                comments.append(line)
            elif line.lstrip():
                lines.append(line)
            else :
                if len(lines) > 0:
                    yield _parse_sentence(lines, comments)
                    lines = []
                    comments = []
        if len(lines) > 0:
            yield _parse_sentence(lines, comments)

def write_conllu(file, sentences):

    def _write_metadata(fp, metadata):
        for comment in metadata:
            print("# " + comment, file=fp)

    def _write_tokens(fp, tokens):
        for token in tokens:
            fields = "\t".join([_field_to_str(field, token) for field in [ID, FORM, LEMMA, UPOS, XPOS, FEATS, HEAD, DEPREL, DEPS, MISC]])
            print(fields, file=fp)

    def _field_to_str(field, token):

        if field == ID:
            id = token[ID]
            if isinstance(tuple):
                return str(id[0]) + "." + str(id[1]) if id[2] == EMPTY else str(id[0] + "-" + str(id[1]))
            else:
                return str(id)

        if field not in token or token[field] is None:
            return "_"

        if field == FEATS:
            return _feats_to_str(token[FEATS])

        if field == DEPS:
            return _deps_to_str(token[DEPS])

        return str(token[field])

    def _feats_to_str(feats):
        if isinstance(feats, str):
            return feats
        feats = [key + "=" + (",".join(value) if isinstance(value, list) else value) for key, value in feats.items()]
        return "|".join(feats)        

    def _deps_to_str(deps):
        if isinstance(deps, str):
            return deps
        deps = [str(rel[0]) + ":" + str(rel[1]) for rel in deps]
        return "|".join(deps)

    if isinstance(file, str):
        file = open(file, "wt", encoding="utf-8")
    with file as fp:
        for sentence in sentences:
            _write_metadata(fp, sentence.metadata)
            _write_tokens(fp, sentence.tokens)
            print(file=fp)

def create_dictionary(sentences, fields={FORM, LEMMA, UPOS, XPOS, FEATS, DEPREL}):
    dic = {f: Counter() for f in fields}
    for sentence in sentences:
        for token in sentence:
            for f in fields:
                s = token[f]
                if isinstance(s, (list, tuple)):
                    for ch in s:
                        dic[f][ch] += 1
                else:
                    dic[f][s] += 1
    return dic

def create_index(dic, min_frequency=1):
    index = {f: Counter() for f in dic.keys()}
    for f, c in dic.items():
        ordered = c.most_common()
        min_fq = min_frequency[f] if isinstance(min_frequency, (list, tuple, dict)) else min_frequency
        for i, (s, fq) in enumerate(ordered):
            if fq >= min_fq:
                index[f][s] = i + 1
    return index

def create_inverse_index(index):
    return {f: {v: k for k, v in c.items()} for f, c in index.items()}

INDEX_FILENAME = "{0}index_{1}.txt"

_NONE_TOKEN = u"__none__"

def write_index(index, fields=None, basename=""):
    if fields is None:
        fields = index.keys()
    index = create_inverse_index(index)
    for f in fields:
        filename = INDEX_FILENAME.format(basename, field_to_str(f))
        with open(filename, "wt", encoding="utf-8") as fp:
            c = index[f]
            for i in range(1, len(c) + 1):
                token = c[i]
                if token is None:
                    token = _NONE_TOKEN
                print(token, file=fp)

def read_index(fields=None, basename=""):
    if fields is None:
        fields = range(len(FIELD_TO_STR))
    index = {}
    for f in fields:
        filename = INDEX_FILENAME.format(basename, field_to_str(f))
        if os.path.isfile(filename):
            with open(filename, "rt", encoding="utf-8") as fp:
                index[f] = Counter()
                i = 1
                for line in fp:
                    token = line.rstrip("\r\n")
                    if token == _NONE_TOKEN:
                        token = None
                    index[f][token] = i
                    i += 1
    return index

def count_frequency(sentences, index, fields=None):
    if fields is None:
        fields = index.keys()
    count = {f: Counter() for f in fields}
    for sentence in sentences:
        for token in sentence:
            for f in fields:
                s = token[f]
                if isinstance(s, (list, tuple)):
                    for ch in s:
                        i = index[f][ch]
                        count[f][i] += 1
                else:
                    i = index[f][s]
                    count[f][i] += 1
    return count

def shuffled_stream(data, size=0):
    i = 0
    while True:
        random.shuffle(data)
        for d in data:
            if size > 0 and i >= size:
                return
            i += 1
            yield d

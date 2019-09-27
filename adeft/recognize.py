"""Implements the disambiguation of shortforms based on recognizing an
explicit defining pattern in text."""

import re
import string
import logging

from nltk.stem.snowball import EnglishStemmer

from adeft.nlp import tokenize, untokenize
from adeft.util import get_candidate_fragments, get_candidate


logger = logging.getLogger(__file__)

_stemmer = EnglishStemmer()


class BaseRecognizer(object):
    def __init__(self, shortform, window=100, exclude=None):
        self.shortform = shortform
        self.window = window
        if exclude is None:
            self.exclude = set([])
        else:
            self.exclude = exclude

    def recognize(self, text):
        groundings = set()
        fragments = get_candidate_fragments(text, self.shortform,
                                            window=self.window)
        for fragment in fragments:
            if not fragment:
                continue
            tokens = get_candidate(fragment, self.exclude)
            # search for longform in trie
            longform = self._search(tuple(_stemmer.stem(token)
                                          for token in tokens[::-1]))
            # if a longform is recognized, add it to output list
            if longform:
                grounding = self._post_process(longform)
                groundings.add(grounding)
        return groundings

    def strip_defining_patterns(self, text):
        """Return text with defining patterns stripped

       This is useful for training machine learning models where training
       labels are generated by finding defining patterns (DP)s. Models must
       be trained to disambiguate texts that do not contain a defining
       pattern.

       The output on the first sentence of the previous paragraph is
       "This is useful for training machine learning models where training
       labels are generated by finding DPs."

       Parameters
       ----------
       text : str
           Text to remove defining patterns from

       Returns
       -------
       stripped_text : str
           Text with defining patterns replaced with shortform
        """
        fragments = get_candidate_fragments(text, self.shortform)
        for fragment in fragments:
            # Each fragment is tokenized and its longform is identified
            tokens = tokenize(fragment)
            longform = self._search(tuple(_stemmer.stem(token)
                                          for token, _ in tokens[::-1]
                                          if token not in string.punctuation))
            if longform is None:
                # For now, ignore a fragment if its grounding has no longform
                # from the grounding map
                continue
            # Remove the longform from the fragment, keeping in mind that
            # punctuation is ignored when extracting longforms from text
            num_words = len(longform.split())
            i = 0
            j = len(tokens) - 1
            while i < num_words:
                if re.match(r'\w+', tokens[j][0]):
                    i += 1
                j -= 1
                if i > 100:
                    break
            text = text.replace(fragment.strip(),
                                untokenize(tokens[:j+1]))
        # replace all instances of parenthesized shortform with shortform
        stripped_text = re.sub(r'\(\s*%s\s*\)'
                               % self.shortform,
                               ' ' + self.shortform + ' ', text)
        stripped_text = ' '.join(stripped_text.split())
        return stripped_text

    def _search(self, tokens):
        raise NotImplementedError

    def _post_process(self, text):
        raise NotImplementedError


class _TrieNode(object):
    """TrieNode structure for use in recognizer

    Attributes
    ----------
    longform : str or None
        Set to associated longform at leaf nodes in the trie, otherwise None.
        Each longform corresponds to a path in the trie from root to leaf.

    children : dict
        dict mapping tokens to child nodes
    """
    __slots__ = ['longform', 'children']

    def __init__(self, longform=None):
        self.longform = longform
        self.children = {}


class AdeftRecognizer(BaseRecognizer):
    """Class for recognizing longforms by searching for defining patterns (DP)

    Searches text for the pattern "<longform> (<shortform>)" for a collection
    of grounded longforms supplied by the user.

    Parameters
    ----------
    shortform : str
        shortform to be recognized
    grounding_map : dict[str, str]
        Dictionary mapping longform texts to their groundings
    window : Optional[int]
        Specifies range of characters before a defining pattern (DP)
        to consider when finding longforms. Should be set to the same value
        that was used in the AdeftMiner that was used to find longforms.
        Default: 100
    exclude : Optional[set]
        set of tokens to ignore when searching for longforms.
        Default: None

    Attributes
    ----------
    _trie : :py:class:`adeft.recognize._TrieNode`
        Trie used to search for longforms. Edges correspond to stemmed tokens
        from longforms. They appear in reverse order to the bottom of the trie
        with terminal nodes containing the associated longform in their data.
    """
    def __init__(self, shortform, grounding_map, window=100, exclude=None):
        self.grounding_map = grounding_map
        self._trie = self._init_trie()
        super().__init__(shortform, window, exclude)

    def _init_trie(self):
        """Initialize search trie with longforms in grounding map

        Returns
        -------
        root : :py:class:`adeft.recogize._TrieNode`
            Root of search trie used to recognize longforms
        """
        root = _TrieNode()
        for longform, grounding in self.grounding_map.items():
            edges = tuple(_stemmer.stem(token)
                          for token, _ in tokenize(longform))[::-1]
            current = root
            for index, token in enumerate(edges):
                if token not in current.children:
                    if index == len(edges) - 1:
                        new = _TrieNode(longform)
                    else:
                        new = _TrieNode()
                    current.children[token] = new
                    current = new
                else:
                    current = current.children[token]
        return root

    def _search(self, tokens):
        """Return longform from maximal candidate preceding shortform

        Parameters
        ----------
        tokens : tuple of str
            contains tokens that precede the occurence of the pattern
            "<longform> (<shortform>)" up until the start of the containing
            sentence or an excluded word is reached. Tokens must appear in
            reverse order.

        Returns
        -------
        str
            Agent ID corresponding to associated longform in the concept map
            if one exists, otherwise None.
        """
        current = self._trie
        for token in tokens:
            if token not in current.children:
                break
            if current.children[token].longform is None:
                current = current.children[token]
            else:
                return current.children[token].longform

    def _post_process(self, longform):
        return self.grounding_map[longform]

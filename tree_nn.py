import sys
import random
import numpy as np
from nn_model_base import NNModelBase
from utils import randvec, d_tanh, softmax

__author__ = "Christopher Potts"
__version__ = "CS224u, Stanford, Spring 2018"


class TreeNN(NNModelBase):
    def __init__(self, vocab, **kwargs):
        super(TreeNN, self).__init__(vocab, **kwargs)
        self.hidden_dim = self.embed_dim #* 2

    def initialize_parameters(self):
        # Hidden parameters for semantic composition:
        self.W = self.weight_init(self.hidden_dim, self.embed_dim)
        self.b = np.zeros(self.embed_dim)
        # Output classifier:
        self.W_hy = self.weight_init(self.embed_dim, self.output_dim)
        self.b_y = np.zeros(self.output_dim)
        self.test = 'test'

    def forward_propagation(self, subtree):
        """Forward propagation through the tree and through the
        softmax prediction layer on top. For each subtree

        [parent left right]

        we compute

        p = tanh([x_l; x_r]W + b)

        where x_l and x_r are the representations on the root of
        left and right. and [x_l; x_r] is their concatenation.

        The representation on the root is then fed to a softmax
        classifier.

        Returns
        ----------
        vectree :  np.array or tuple of tuples (of tuples ...) of np.array
            Predicted vector representation of the entire tree
        y : np.array
            The predictions made for this example, dimension
            `self.output_dim`.

        """
        vectree = self._interpret(subtree)
        root = self._get_vector_tree_root(vectree)
        y = softmax(root.dot(self.W_hy) + self.b_y)
        return vectree, y

    def _interpret(self, subtree):
        """The forward propagation through the tree itself (excluding
        the softmax prediction layer on top of this).

        Given an NLTK Tree instance `subtree`, this returns a vector
        if `subtree` is just a leaf node, else a tuple of tuples (of
        tuples ...) of vectors with the same shape as `subtree`,
        with each node now represented by vector.

        Parameters
        ----------
        subtree : nltk.tree.Tree

        Returns
        -------
        np.array or tuple-based representation of `subtree`.

        """
        # For NLTK `Tree` objects, this identifies leaf nodes:
        if isinstance(subtree, str):
            return self.get_word_rep(subtree)
        elif len(subtree) == 1:
            return self._interpret(subtree[0])
        else:
            left_subtree, right_subtree = subtree[0], subtree[1]
            # Recursive interpretation of the child trees:
            left_vectree = self._interpret(left_subtree)
            right_vectree = self._interpret(right_subtree)
            # Top representations of each child tree:
            left_rep = self._get_vector_tree_root(left_vectree)
            right_rep = self._get_vector_tree_root(right_vectree)
            # Concatenate and create the hidden representation:
            # Here we've defined W so that hidden dimensions are twice the length of the embedding dimensions.
            # This means that we can concatenate two vectors together, and these will be the right length.
            # combined = np.concatenate((left_rep, right_rep))
            # print(left_vectree)
            # print(left_rep)
            # print('test')
            combined = (left_rep + right_rep)/2
            # print(combined)
            root_rep = np.tanh(combined.dot(self.W) + self.b)
            # Return the full subtree of vectors:
            return (root_rep, left_vectree, right_vectree)

    @staticmethod
    def _get_vector_tree_root(vectree):
        """Returns `tree` if it represents only a lexical item, else
        the root (first member) of `tree`.

        Parameters
        ----------
        vectree : np.array or tuple of tuples (of tuples ...) of np.array

        Returns
        -------
        np.array

        """
        if isinstance(vectree, tuple):
            vectree[0]
            return vectree[0]
        else:
            return vectree

    def backward_propagation(self, vectree, predictions, ex, labels):
        root = self._get_vector_tree_root(vectree)
        # Output errors:
        y_err = predictions
        y_err[np.argmax(labels)] -= 1
        d_W_hy = np.outer(root, y_err)
        d_b_y = y_err
        # Internal error accumulation:
        d_W = np.zeros_like(self.W)
        d_b = np.zeros_like(self.b)
        h_err = y_err.dot(self.W_hy.T) * d_tanh(root)
        d_W, d_b = self._tree_backprop(vectree, h_err, d_W, d_b)
        return d_W_hy, d_b_y, d_W, d_b

    def _tree_backprop(self, deep_tree, h_err, d_W, d_b):
        # This is the leaf-node condition for vector trees:
        if isinstance(deep_tree, np.ndarray):
            return d_W, d_b
        else:
            # Biased gradient:
            d_b += h_err
            # Get the left and right representations:
            left_subtree, right_subtree = deep_tree[0], deep_tree[1]
            left_rep = self._get_vector_tree_root(left_subtree)
            right_rep = self._get_vector_tree_root(right_subtree)
            # Combine them and update d_W:
            # combined = np.concatenate((left_rep, right_rep))
            combined = (left_rep + right_rep)/2
            d_W += np.outer(combined, h_err)
            # Get the gradients for both child nodes:
            h_err = h_err.dot(self.W.T) * d_tanh(combined)
            # Split the gradients between the children and continue
            # backpropagation down each subtree:
            l_err = h_err[ : self.embed_dim]
            r_err = h_err[ : self.embed_dim]
            d_W, d_b = self._tree_backprop(left_subtree, l_err, d_W, d_b)
            d_W, d_b = self._tree_backprop(right_subtree, r_err, d_W, d_b)
        return d_W, d_b

    def update_parameters(self, gradients):
        d_W_hy, d_b_y, d_W, d_b = gradients
        self.W_hy -= self.eta * d_W_hy
        self.b_y -= self.eta * d_b_y
        self.W -= self.eta * d_W
        self.b -= self.eta * d_b

    def set_params(self, **params):
        super(TreeNN, self).set_params(**params)
        self.hidden_dim = self.embed_dim * 2


if __name__ == '__main__':
    from nltk.tree import Tree

    train = [
        ["(N (N 1) (B (F +) (N 1)))", "even"],
        ["(N (N 1) (B (F +) (N 2)))", "odd"],
        ["(N (N 2) (B (F +) (N 1)))", "odd"],
        ["(N (N 2) (B (F +) (N 2)))", "even"],
        ["(N (N 1) (B (F +) (N (N 1) (B (F +) (N 2)))))", "even"]
    ]

    vocab = ["1", "+", "2"]

    X, y = zip(*train)
    X = [Tree.fromstring(x) for x in X]
    model = TreeNN(vocab, embed_dim=20, max_iter=5000)
    model.fit(X, y)

    print(model.predict(X))

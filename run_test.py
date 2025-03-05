
import sys
from tests.test_compare_embedding_matrix import test_embeddings_matrix
from tests.analysis import analyze


def test(analysis=False):
    if analysis:
        analyze()
    else:
        test_embeddings_matrix()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test(sys.argv[1])
    else:
        test()


import json
import os

from compare.compare_args import CompareArgs
from compare.compare_embeddings import CompareEmbedding
from tests.analysis import print_formatted_table, convert_matrix_to_roll_index_output, table_elementwise_subtraction
from utils.utils import Utils



def test_embeddings_matrix():
    directory_to_test = input("Enter directory to test: ")
    if not os.path.exists(directory_to_test):
        raise FileNotFoundError(f"{directory_to_test} does not exist!")
    args = CompareArgs(base_dir=directory_to_test)
    args_clone = args.clone()
    args_clone.use_matrix_comparison = True
    embedding_compare = CompareEmbedding(args=args)
    embedding_compare_matrix = CompareEmbedding(args=args_clone)
    embedding_compare.get_files()
    embedding_compare_matrix.get_files()
    embedding_compare.get_data()
    embedding_compare_matrix.get_data()
    embedding_compare.run_comparison()
    embedding_compare_matrix.run_comparison()

    with open(os.path.join(Utils.get_user_dir(), "simple_image_compare", "tests", "embeddings_output.json"), "r") as f:
        embedding_compare_result = json.load(f)

    with open(os.path.join(Utils.get_user_dir(), "simple_image_compare", "tests", "embeddings_matrix_output.json"), "r") as f:
        embedding_compare_matrix_result = json.load(f)

    comparable_embedding_compare_matrix_reuslt = convert_matrix_to_roll_index_output(embedding_compare_matrix_result)
    comparison = table_elementwise_subtraction(embedding_compare_result, comparable_embedding_compare_matrix_reuslt)
    print_formatted_table(comparison, "Embedding Compare Result")



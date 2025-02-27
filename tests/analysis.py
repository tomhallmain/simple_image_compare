from copy import deepcopy
# from glob import glob
import json
# import os


#from utils.config import config


def round_table_values(table=[[]], n_digits=3):
    copy = deepcopy(table)
    for row in copy:
        for col in range(len(row)):
            try:
                value = round(float(row[col]), n_digits)
                if value == 1.0 or value == 0.0:
                    row[col] = int(value)
                else:
                    row[col] = value
            except ValueError as e:
                pass
    return copy


def reverse_table_row_order(table=[[]]):
    return table[::-1]


def print_formatted_table(table=[[]], title=None):
    if title is not None:
        print(title)
    if len(table) == 0:
        print("No data found.")
        return
    rounded = round_table_values(table)
    print("\t".join([str(i) for i in rounded[0]]))
    for row in range(1, len(rounded)):
        print("\t".join([str(cell) for cell in rounded[row]]))


def transpose_table(t):
    return [list(x) for x in zip(*t)]


def convert_matrix_to_roll_index_output(m):
    roll_index_format = []
    for i in range(len(m)):
        roll_index_row = []
        for j in range(len(m[0])):
            if j <= i:
                continue
            roll_index_row.append(m[i][j])
        for j in range(0, i):
            roll_index_row.append(m[i][j])
        roll_index_format.append(roll_index_row)
    return transpose_table(roll_index_format)

def convert_roll_index_to_matrix_output(r):
    r_t = transpose_table(r)
    matrix = []
    matrix_len = len(r_t[0]) + 1
    for i in range(matrix_len):
        matrix.append([1]*matrix_len)
    for i in range(len(r_t)):
        for j in range(len(r_t[0])):
            matrix_row = i
            matrix_col = (i+j+1)
            if matrix_row == matrix_col:
                raise Exception("equal row col")
            if matrix_col >= matrix_len:
                matrix_col = matrix_col % matrix_len
            # print(i, j, matrix_row, matrix_col, r_t[i][j])
            matrix[matrix_row][matrix_col] = r_t[i][j]
    return matrix

__ = convert_roll_index_to_matrix_output

def table_elementwise_subtraction(t1, t2):
    assert len(t1) == len(t2), f"Matrix row dimensions do not match t1: {len(t1)}x{len(t1[0])} and t2: {len(t2)}x{len(t2[0])}"
    assert len(t1[0]) == len(t2[0]), f"Matrix row dimensions do not match t1: {len(t1)}x{len(t1[0])} and t2: {len(t2)}x{len(t2[0])}"
    return [[t1[i][j] - t2[i][j] for j in range(len(t1[i]))] for i in range(len(t1))]


# def gather_files(base_dir=".", exts=config.image_types, recursive=True, include_videos=False):
#     files = []
#     recursive_str = "**/" if recursive else ""
#     exts = exts[:]
#     if include_videos:
#         for ext in config.video_types:
#             if ext not in exts:
#                 exts.append(ext)
#     else:
#         exts = [e for e in exts if e not in config.video_types]
#     for ext in exts:
#         pattern = os.path.join(base_dir, recursive_str + "*" + ext)
#         files.extend(glob(pattern, recursive=recursive))
#     return files

def analyze(in_tests_folder=False):
    tests = "tests\\" if not in_tests_folder else ""
    with open(f"{tests}embeddings_matrix_output.json", "r") as f:
        embedding_matrix_vals = json.load(f)
    with open(f"{tests}embeddings_output.json",  "r") as f:
        embedding_vals = json.load(f)
        embedding_vals = reverse_table_row_order(embedding_vals)

    print("Matrix values")
    print_formatted_table(embedding_matrix_vals)
    print("\n\nEmbedding values")
    print_formatted_table(embedding_vals)
    # print("\n\nDifference")
    # comparable_embedding_compare_matrix_reuslt = convert_matrix_to_roll_index_output(embedding_matrix_vals)
    # comparison = table_elementwise_subtraction(embedding_vals, comparable_embedding_compare_matrix_reuslt)
    # print_formatted_table(comparison)

    print("\n\nMatrix version")
    matrix_version = convert_roll_index_to_matrix_output(embedding_vals)
    print_formatted_table(matrix_version)
    print("\n\nDifference")
    comparison  = table_elementwise_subtraction(matrix_version, embedding_matrix_vals)
    print_formatted_table(comparison)

    # print("\n\nIndexed files")
    # files = gather_files(r"C:\Users\tehal\Downloads\Internet Archive\Internet-Archive-Artist-in-Residence-Mieke-Marple-wallpaper")
    # for i, _file in enumerate(files):
    #     print(i, _file)


if __name__ == "__main__":
    analyze(in_tests_folder=True)












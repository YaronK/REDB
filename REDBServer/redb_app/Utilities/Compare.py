from redb_app.models import Function, String, Call, Instruction, Executable, Graph, Description
import xlwt
import redb_app.utils
from redb_app.heuristics import GraphSimilarity
import numpy as np
import matplotlib.pyplot as plt
from difflib import SequenceMatcher
import heapq
import json
import pylab as pl
import os
import redb_app.constants as constants
NAME_SIMILARITY_THRESHOLD = 0.8
import copy
from redb_app.utils import test_log


def get_function_graph_by_id(func_id):
    return Function.objects.get(id=func_id).graph_set.all()[0].get_data()


def get_function_name_by_id(func_id):
    return Function.objects.get(id=func_id).func_name


def generate_matching_grade_by_id(a_id, b_id, test_dict=None):
    a_graph = get_function_graph_by_id(a_id)
    b_graph = get_function_graph_by_id(b_id)
    log_decisions = test_dict and "log_decisions" in test_dict
    if log_decisions:
        a_name = get_function_name_by_id(a_id)
        b_name = get_function_name_by_id(b_id)
        test_log("start: " +
                 a_name + " (" + str(a_id) + "), " +
                 b_name + " (" + str(b_id) + ")")
    similarity = GraphSimilarity(a_graph, b_graph).ratio(test_dict=test_dict)
    if log_decisions:
        test_log("finish: " +
                 a_name + " (" + str(a_id) + "), " +
                 b_name + " (" + str(b_id) + ")" + "\n")
    return similarity


EXCLUDED_ON_EXE_COMPARISON = ["unknown", "sub_"]


def get_intersecting_func_names(func_set, exe_name1, exe_name2):
    exe1_funcs = func_set.filter(exe_name=exe_name1)
    exe2_funcs = func_set.filter(exe_name=exe_name2)
    exe1_func_names = [func.func_name for func in exe1_funcs]
    exe2_func_names = [func.func_name for func in exe2_funcs]
    intersected_func_names = set(exe1_func_names) & set(exe2_func_names)
    for excluded in EXCLUDED_ON_EXE_COMPARISON:
        intersected_func_names = filter(lambda n: excluded not in n,
                                        intersected_func_names)
    exe1 = []
    exe2 = []
    for n in intersected_func_names:
        exe1.append(exe1_funcs.get(func_name=n))
        exe2.append(exe2_funcs.get(func_name=n))
    return (exe1, exe2)


def get_functions_with_similar_name(func_name, function_set):
    return filter(lambda f: SequenceMatcher(a=f.func_name,
                                            b=func_name).ratio() >=
                  NAME_SIMILARITY_THRESHOLD, function_set)


def compare_function_sets(func_set_1, func_set_2, test_dict=None):

    gmgbi = generate_matching_grade_by_id

    res_matrix = [[gmgbi(func1.id, func2.id, test_dict=test_dict)
                   for func1 in func_set_1] for func2 in func_set_2]

    return res_matrix


def get_optimal_threshold(func_set_1, func_set_2, test_dict=None):
    res_matrix = compare_function_sets(func_set_1, func_set_2,
                                       test_dict=test_dict)
    should_be_equal_grades = []
    should_be_different_grades = []

    for row in range(len(res_matrix)):
        for col in range(len(res_matrix[0])):
            grade = res_matrix[row][col]
            if row == col:
                should_be_equal_grades.append(grade)
            else:
                should_be_different_grades.append(grade)

    should_be_equal_mean = sum(should_be_equal_grades) / float(len(should_be_equal_grades))
    should_be_diff_mean = sum(should_be_different_grades) / float(len(should_be_different_grades))
    delta = should_be_equal_mean - should_be_diff_mean
    print "delta: " + str(delta)
    return delta


def compare_function_set_excel(path, func_set_1, func_set_2):
    book = xlwt.Workbook(encoding="utf-8")
    sheet1 = book.add_sheet("Sheet1")
    xlwt.Alignment.HORZ_CENTER
    xlwt.Alignment.VERT_CENTER
    res_mat = compare_function_sets(func_set_1, func_set_2)
    rows = len(res_mat)
    cols = len(res_mat[0])
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            sheet1.write(i, j, res_mat[i][j])

    for i in range(rows):
        sheet1.write(i + 1, 0, func_set_1[i].func_name)
    for j in range(cols):
        sheet1.write(0, j + 1, func_set_2[j].func_name)

    book.save(path)


def compare_function_sets_heat_map(path, func_set_1, func_set_2):
    res_mat = compare_function_sets(func_set_1, func_set_2)
    func_set_names_1 = [func.func_name for func in func_set_1]
    func_set_names_2 = [func.func_name for func in func_set_2]
    data = np.array(res_mat)
    fig, ax = plt.subplots()
    heatmap = ax.pcolor(data, cmap=plt.cm.Blues)  # @UndefinedVariable
    ax.set_xticks(np.arange(data.shape[0]) + 0.5, minor=False)
    ax.set_yticks(np.arange(data.shape[1]) + 0.5, minor=False)
    ax.invert_yaxis()
    ax.xaxis.tick_top()
    ax.set_yticklabels(func_set_names_1, minor=False)
    ax.set_xticklabels(func_set_names_2, minor=False)
    plt.xticks(rotation=90)
    plt.rcParams.update({'font.size': 4})
    # fig.tight_layout()
    plt.savefig(path, bbox_inches='tight', dpi=100)
    plt.show()


def get_top_similarities_for_single_function(num_of_tops, func, func_set):
    similarity_res = []
    for compared_func in func_set:
        print (compared_func.id, func.id)
        similarity_grade = generate_matching_grade_by_id(compared_func.id, func.id)
        similarity_res.append((similarity_grade, compared_func.func_name))

    return heapq.nlargest(num_of_tops, similarity_res)


def get_top_similarities_for_all_functions(func_set_1, func_set_2, num_of_tops, path):
    f = open(path, 'w')
    delimeter_line = \
         "\n###############################################################\n"
    for func in func_set_1:
        top_similars = get_top_similarities_for_single_function(num_of_tops, func, func_set_2)
        f.write("%s: top similars\n" % str((func.func_name, func.exe_name)))
        for item in top_similars:
            f.write("%s, %.3f\n" % (item[1], item[0]))
        expected_similarities = \
            get_functions_with_similar_name(func.func_name, func_set_2)
        f.write("Expected:\n")
        for func in expected_similarities:
            f.write(str((func.func_name, func.exe_name)) + ', ')
        f.write(delimeter_line)
    f.close()


def get_bounds(mean, deviation):
    return mean * (1 - deviation), mean * (1 + deviation)

con_db = constants.db_filter


def insns_num_filter(func, func_set,
                     deviation=con_db.MAX_NUM_INSNS_DEVIATION):
    insns_num = func.num_of_insns
    lower_bound, upper_bound = get_bounds(insns_num, deviation)
    func_set = func_set.filter(num_of_insns__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def blocks_num_filter(func, func_set,
                      deviation=con_db.MAX_NUM_BLOCKS_DEVIATION):
    num_of_blocks = func.graph_set.all()[0].num_of_blocks
    lower_bound, upper_bound = get_bounds(num_of_blocks, deviation)
    func_set = func_set.filter(graph__num_of_blocks__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def edges_num_filter(func, func_set,
                     deviation=con_db.MAX_NUM_EDGES_DEVIATION):
    num_of_edges = func.graph_set.all()[0].num_of_edges
    lower_bound, upper_bound = get_bounds(num_of_edges, deviation)
    func_set = func_set.filter(graph__num_of_edges__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def vars_size_filter(func, func_set,
                     deviation=con_db.MAX_VARS_SIZE_DEVIATION):
    vars_size = func.vars_size
    lower_bound, upper_bound = get_bounds(vars_size, deviation)
    func_set = func_set.filter(vars_size__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def args_size_filter(func, func_set,
                     deviation=con_db.MAX_ARGS_SIZE_DEVIATION):
    args_size = func.args_size
    lower_bound, upper_bound = get_bounds(args_size, deviation)
    func_set = func_set.filter(args_size__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def regs_size_filter(func, func_set,
                     deviation=con_db.MAX_REGS_SIZE_DEVIATION):
    regs_size = func.regs_size
    lower_bound, upper_bound = get_bounds(regs_size, deviation)
    func_set = func_set.filter(regs_size__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def calls_num_filter(func, func_set,
                     deviation=con_db.MAX_NUM_CALLS_DEVIATION):
    num_of_calls = func.num_of_calls
    lower_bound, upper_bound = get_bounds(num_of_calls, deviation)
    func_set = func_set.filter(num_of_calls__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def strings_num_filter(func, func_set,
                       deviation=con_db.MAX_NUM_STRINGS_DEVIATION):
    num_of_strings = func.num_of_strings
    lower_bound, upper_bound = get_bounds(num_of_strings, deviation)
    func_set = func_set.filter(num_of_strings__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def imms_num_filter(func, func_set,
                    deviation=con_db.MAX_NUM_IMMS_DEVIATION):
    num_of_imms = func.num_of_imms
    lower_bound, upper_bound = get_bounds(num_of_imms, deviation)
    func_set = func_set.filter(num_of_imms__range=  # @IgnorePep8
                               (lower_bound, upper_bound))
    return func_set


def before_after(my_func_index, filter_func, deviation=None):
    my_func = Function.objects.all()[my_func_index]
    print "Before: " + str(len(Function.objects.all()))
    if deviation != None:
        after = len(filter_func(my_func, Function.objects.all(), deviation))
    else:
        after = len(filter_func(my_func, Function.objects.all()))
    print "After: " + str(after)


def filter_stage(func, func_set, filter_func, deviation):
    before = len(func_set)
    print "before " + filter_func.__name__ + str(before)

    if deviation != None:
        func_set = filter_func(func, func_set, deviation)
    else:
        func_set = filter_func(func, func_set)

    after = len(func_set)
    print "after " + filter_func.__name__ + str(after)

    diff = before - after
    print "diff " + filter_func.__name__ + str(diff)
    return (diff, func_set)


def filter_several_stages(func_set, filter_functions, deviation=None):
    diffs = []
    for func in func_set:
        func_set_copy = copy.deepcopy(func_set)
        for filter_function in filter_functions:
            diff, func_set_copy = filter_stage(func, func_set_copy, filter_function,
                                          deviation)
            if (filter_functions.index(filter_function) ==
                len(filter_functions) - 1):  # last filter
                diffs.append(diff)

    return np.mean(diffs)


def optimal_block_sim_threshold_min_block_dist_similarity(exe_name_1,
                                                          exe_name_2,
                                                          num_of_funcs):
    func_set = Function.objects.exclude(graph__num_of_blocks=1)
    exe1, exe2 = get_intersecting_func_names(func_set, exe_name_1,
                                             exe_name_2)
    import random
    index_list = random.sample(range(len(exe1)), num_of_funcs)
    funcs1 = [exe1[i] for i in index_list];
    funcs2 = [exe2[i] for i in index_list];
    best_block_sim_threshold = 0
    best_min_block_dist_similarity = 0
    best_delta = float("-infinity")
    for block_sim_threshold in pl.frange(0, 0.8, 0.1):
        for min_block_dist_similarity in pl.frange(0.5, 0.8, 0.1):
            print ("current", block_sim_threshold, min_block_dist_similarity)
            print ("best", best_block_sim_threshold, best_min_block_dist_similarity)
            test_dict = {#"log_decisions": True,
                         "block_similarity_threshold": block_sim_threshold,
                         "min_block_dist_similarity": min_block_dist_similarity,
                         "association_graph_max_size": 5000}
            delta = \
                get_optimal_threshold(funcs1, funcs2, test_dict=test_dict)

            if best_delta < delta:
                best_delta = delta
                print "best delta: " + str(best_delta)
                best_block_sim_threshold = block_sim_threshold
                best_min_block_dist_similarity = min_block_dist_similarity

    print ("best_delta: " +
           str(best_delta) +
           ", best_block_sim_threshold: " +
           str(best_block_sim_threshold) +
           ", best_min_block_dist_similarity: " +
           str(best_min_block_dist_similarity))

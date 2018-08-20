import argparse
from itertools import compress, product
from multiprocessing import Pool
import os

import pandas as pd
import pickle
from sklearn.metrics import roc_auc_score

from collate import Dataset
from train import ARDSDetectionModel, build_parser

DF_DIR = 'data/experiment{experiment_num}/training/grid_search/{feature_set}'


def get_all_possible_features():
    """
    Get all possible feature permutations
    """
    all_possible_flow_time_features = [
        ('mean_flow_from_pef', 38), ('inst_RR', 8), ('minF_to_zero', 36),
        ('pef_+0.16_to_zero', 37), ('iTime', 6), ('eTime', 7), ('I:E ratio', 5),
        # XXX Add pressure itime eventually, altho it may only be useful for PC/PS pts.
        ('dyn_compliance', 39), ('TVratio', 11)
    ]
    # There is actually no way that we can do grid search on all possible broad features
    # because it will yield 8388608 possibilities, which is infeasible to search thru.
    # So I will only look through the ones that seem reasonable from my POV. Reducing #
    # features down to 17 possibilities still yields 262144 choices. 13 possibilities gives
    # 16384 choices
    all_possibilities = all_possible_flow_time_features + [
        ('TVi', 9), ('PIP', 15), ('PEEP', 17), ('vol_at_76', 41), ('min_pressure', 35)
    ]
    all_ft_combos = (set(compress(all_possible_flow_time_features, mask)) for mask in product(*[[0,1]]*len(all_possible_flow_time_features)))
    all_combos = (set(compress(all_possibilities, mask)) for mask in product(*[[0,1]]*len(all_possibilities)))
    return {'flow_time_gen': all_ft_combos, 'broad_gen': all_combos}


def run_model(model_args, combo, model_idx, possible_folds, out_dir):
    results = {folds: {'auc': 0} for folds in possible_folds}
    results['idx'] = model_idx
    if not combo:
        results['features'] = []
        return results
    features = [k[0] for k in combo]
    results['features'] = features

    path = os.path.join(out_dir, 'dataset-{}.pkl'.format(model_idx))
    if os.path.exists(path):
        dataset = pd.read_pickle(path)
    else:
        dataset = Dataset(model_args.cohort_description, 'custom', model_args.stacks, True, custom_features=combo).get()
        dataset.to_pickle(path)

    for folds in possible_folds:
        model_args.folds = folds
        model = ARDSDetectionModel(model_args, dataset)
        model.train_and_test()
        model_auc = roc_auc_score(model.results.patho.tolist(), model.results.prediction.tolist())
        results[folds]['auc'] = model_auc
        del model  # paranoia
    return results


def func_star(args):
    return run_model(*args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--feature-set', choices=['flow_time', 'broad'], default='flow_time')
    parser.add_argument('--experiment', choices=[1, 2], default=1, type=int)
    parser.add_argument('--threads', type=int, default=multiprocessing.cpu_count(), help="Set number of threads to use, otherwise all cores will be occupied")
    main_args = parser.parse_args()

    # We're doing this because these args are not necessary, and we can just pass them
    # easily over code because they wont be changing
    model_args = build_parser().parse_args([])
    model_args.copd_to_ctrl = True
    model_args.cross_patient_kfold = True

    results = {}
    feature_combos = get_all_possible_features()
    possible_folds = [5, 10]
    out_dir = DF_DIR.format(experiment_num=main_args.experiment, feature_set=main_args.feature_set)
    feature_gen = feature_combos['{}_gen'.format(main_args.feature_set)]

    input_gen = [(model_args, combo, idx, possible_folds, out_dir) for idx, combo in enumerate(feature_gen)]

    pool = Pool(args.threads)
    results = pool.map(func_star, input_gen)
    pool.close()
    pool.join()

    best = max([(features_run['idx'], features_run[folds]['auc']) for features_run in results for folds in possible_folds], key=lambda x: x[1])
    print('Best AUC: {}'.format(best[1]))
    print('Best features: {}'.format(results[best[0]]))
    dict_ = pickle.dumps(results)
    with open('experiment{}_{}_grid_search_results.pkl'.format(main_args.experiment, main_args.feature_set), 'w') as f:
        f.write(dict_)


if __name__ == "__main__":
    main()
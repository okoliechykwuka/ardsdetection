import argparse

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def correlation_mat(df):
    feats = [col for col in df.columns if 'nanmedian' in col]
    renaming = {f: f.replace('nanmedian_', '').replace('_', ' ') for f in feats}
    df = df.rename(columns=renaming)
    new_feat_names = list(renaming.values())
    corr_mat = df[new_feat_names].corr()
    cmap = sns.color_palette("vlag", as_cmap=True)
    sns.heatmap(corr_mat, cmap=cmap, annot=True)
    plt.tight_layout()
    plt.savefig('img/feature_correlation_matrix.png', dpi=200)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('df')
    args = parser.parse_args()

    df = pd.read_pickle(args.df)
    correlation_mat(df)


if __name__ == '__main__':
    main()
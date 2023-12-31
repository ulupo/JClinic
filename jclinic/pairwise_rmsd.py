# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/pairwise_rmsd.ipynb.

# %% auto 0
__all__ = ['make_rmsds_matrix']

# %% ../nbs/pairwise_rmsd.ipynb 3
from pathlib import Path
from warnings import warn

from itertools import combinations

from tqdm import tqdm

import numpy as np
import pandas as pd
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, dendrogram
from matplotlib import pyplot as plt

from prody import (
    confProDy,
    AtomGroup,
    matchChains,
    calcTransformation,
    calcRMSD,
    showProtein,
)


confProDy(verbosity="critical")


def _printMatch(match):
    # Source: http://prody.csb.pitt.edu/tutorials/structure_analysis/compare.html#match-chains
    print(f"Chain 1     : {match[0]}")
    print(f"Chain 2     : {match[1]}")
    print(f"Length      : {len(match[0])}")
    print(f"Seq identity: {match[2]}")
    print(f"Seq overlap : {match[3]}")


def _combine_matched_chains(matches):
    n_chains = len(matches)
    bound = matches[0][0]
    unbound = matches[0][1]
    for i in range(1, n_chains):
        bound += matches[i][0]
        unbound += matches[i][1]

    return bound, unbound

# %% ../nbs/pairwise_rmsd.ipynb 4
def make_rmsds_matrix(
    parsed_structures_prody: dict[str, AtomGroup], show: bool = False
):
    """
    Make a dissimilarity matrix by attempting to perform all-vs-all structural alignments of the
    parsed structures in `parsed_structures_prody`, and filling the matrix entries with the RMSDs
    after alignment.

    All chains are merged into one chain (named 'X') to be able to use ProDy's `matchChains` on
    homomers.

    Entries corresponding to non-alignable pairs are filled with NaN.
    """
    structure_names = list(parsed_structures_prody.keys())
    n_structures = len(structure_names)

    pairwise_rmsds = pd.DataFrame(
        data=0.0, index=structure_names, columns=structure_names, dtype=float
    )
    for name_i, name_j in tqdm(combinations(structure_names, 2)):
        structure_i = parsed_structures_prody[name_i]
        structure_j = parsed_structures_prody[name_j]
        n_chains_i = len(structure_i.getHierView())
        n_chains_j = len(structure_j.getHierView())
        combined_chains_i = structure_i.copy()
        combined_chains_j = structure_j.copy()
        combined_chains_i.setChids("X")
        combined_chains_j.setChids("X")
        combined_chains_i.setSegnames("X")
        combined_chains_j.setSegnames("X")
        matches = matchChains(combined_chains_i, combined_chains_j, subset="calpha")
        if matches is not None:
            if show:
                print(name_i, name_j)
                for match in matches:
                    _printMatch(match)
            bound_ca, unbound_ca = _combine_matched_chains(matches)
            transformation = calcTransformation(unbound_ca, bound_ca)
            unbound_ca = transformation.apply(unbound_ca)
            rmsd = calcRMSD(bound_ca, unbound_ca)
            # Visualize the superposed proteins
            if show:
                view = showProtein(structure_i, transformation.apply(structure_j))
                print(f"RMSD = {rmsd}")
                view.setStyle({"cartoon": {"color": "spectrum"}})
                view.show()
            pairwise_rmsds.loc[name_i, name_j] = rmsd
        else:
            pairwise_rmsds.loc[name_i, name_j] = np.NaN

    return pairwise_rmsds

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/sequence_embeddings.ipynb.

# %% auto 0
__all__ = ['PRETRAINED_ESM_MODELS', 'get_sequences_from_parsed_prody', 'embeddings_from_parsed_prody', 'main']

# %% ../nbs/sequence_embeddings.ipynb 3
from typing import Union, Optional
from pathlib import Path
import pickle

from tqdm import tqdm

from prody import AtomGroup, parsePDB

import torch

import esm

from fastcore.script import *

PRETRAINED_ESM_MODELS = [x for x in dir(esm.pretrained) if x.startswith("esm2")]

# %% ../nbs/sequence_embeddings.ipynb 4
def get_sequences_from_parsed_prody(parsed_structures_prody: dict[str, AtomGroup]):
    """Extract amino acid sequences from parsed ProDy structures using Ca atoms."""
    sequences = {}
    for name, structure in parsed_structures_prody.items():
        sequences[name] = {}
        for chain in structure.getHierView():
            chain_id = chain.getChid()
            chain_ca = chain.select("name CA")
            chain_seq = chain_ca.getSequence()
            sequences[name][chain_id] = chain_seq

    return sequences

# %% ../nbs/sequence_embeddings.ipynb 5
def embeddings_from_parsed_prody(
    parsed_structures_prody: dict[str, AtomGroup],
    pretrained_esm_model: str = "esm2_t36_3B_UR50D",
    repr_layers: Optional[list[int]] = None,
):
    """Return embeddings for the chosen ESM-2 model, using only the last layer by default."""
    try:
        esm2, esm2_alphabet = getattr(esm.pretrained, pretrained_esm_model)()
    except AttributeError:
        print(f"`pretrained_esm_model` must be one of {PRETRAINED_ESM_MODELS}")
        raise
    else:
        if repr_layers is None:
            repr_layers = [len(esm2.layers)]
        print(
            f"Using pretrained model {pretrained_esm_model}, "
            f"extracting representation layers {repr_layers}"
        )
        esm2 = esm2.eval()
        if torch.cuda.is_available():
            esm2.cuda()
        esm2_batch_converter = esm2_alphabet.get_batch_converter()

        sequences = get_sequences_from_parsed_prody(parsed_structures_prody)

        esm2_embeddings = {}
        with torch.no_grad():
            for name, chains in tqdm(sequences.items()):
                esm2_embeddings[name] = {}
                for chain_id, seq in chains.items():
                    (
                        esm2_batch_labels,
                        esm2_batch_strs,
                        esm2_batch_tokens,
                    ) = esm2_batch_converter([(f"{name}, chain {chain_id}", seq)])
                    esm2_batch_tokens = esm2_batch_tokens.to(
                        next(esm2.parameters()).device
                    )
                    # Extract per-residue representations (on CPU)

                    results = esm2(
                        esm2_batch_tokens,
                        repr_layers=repr_layers,
                        return_contacts=False,
                    )
                    token_representations = [
                        results["representations"][layer].cpu() for layer in repr_layers
                    ]
                    esm2_embeddings[name][chain_id] = token_representations

    return esm2_embeddings


@call_parse
def main(
    structures_dir: Param("Directory containing structures in PDB format", str),
    output_dir: Param("Output directory for the embeddings", str),
    pretrained_esm_model: Param(
        "Pretrained ESM-2 model name", str, default="esm2_t36_3B_UR50D"
    ),
):
    structures_dir = Path(structures_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    structures_paths = {
        x.name.removesuffix(".pdb"): x for x in sorted(structures_dir.glob("*.pdb"))
    }
    parsed_structures_prody = {
        name: parsePDB(str(path)) for name, path in structures_paths.items()
    }

    esm2_embeddings = embeddings_from_parsed_prody(
        parsed_structures_prody, pretrained_esm_model
    )

    for name, embeddings in esm2_embeddings.items():
        with open(output_dir / f"{name}.pkl", "wb") as f:
            pickle.dump(embeddings, f)

    return esm2_embeddings

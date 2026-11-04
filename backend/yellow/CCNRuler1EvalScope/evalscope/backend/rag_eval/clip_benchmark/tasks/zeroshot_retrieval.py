# Private iCAP Yellow implementation. Do not publish.
import logging
import torch
import torch.nn.functional as F
from contextlib import suppress
from tqdm import tqdm
from evalscope.utils.logger import get_logger
logger = get_logger()

def evaluate(model, dataloader, device, amp=True, recall_k_list=[5], limit=None):
    """
    Evaluate the model on the given dataset

    Parameters
    ----------

    model: torch.nn.Module
        CLIP-like model with `encode_image` and `encode_text`

    dataloader: torch.utils.data.Dataloader
        dataloader to use for evaluation

    tokenizer:
        text tokenizer, i.e. convert list of strings to torch.Tensor of integers

    device: cpu/cuda

    amp: whether to use automatic mixed precision

    recall_k_list: list of int
        recall@k k's to use

    limit: int
        maximum number of samples to evaluate

    Returns
    -------

    dict of retrieval metrics
    """
    batch_images_emb_list = []
    batch_texts_emb_list = []
    texts_image_index = []
    sample_count = 0
    dataloader = dataloader_with_indices(dataloader)
    for batch_images, batch_texts, inds in tqdm(dataloader):
        batch_texts_image_index = [ind for ind, texts in zip(inds, batch_texts) for text in texts]
        batch_images_emb = model.encode_image(batch_images)
        batch_texts_emb = model.encode_text(batch_texts)
        batch_images_emb_list.append(batch_images_emb.cpu())
        batch_texts_emb_list.append(batch_texts_emb.cpu())
        texts_image_index.extend(batch_texts_image_index)
        if limit is not None:
            sample_count += len(batch_images)
            if sample_count >= limit:
                break
    batch_size = len(batch_images_emb_list[0])
    images_emb = torch.cat(batch_images_emb_list)
    texts_emb = torch.cat(batch_texts_emb_list)
    scores = texts_emb @ images_emb.t()
    positive_pairs = torch.zeros_like(scores, dtype=bool)
    positive_pairs[torch.arange(len(scores)), texts_image_index] = True
    metrics = {}
    for recall_k in recall_k_list:
        metrics[f'image_retrieval_recall@{recall_k}'] = (batchify(recall_at_k, scores, positive_pairs, batch_size, device, k=recall_k) > 0).float().mean().item()
        metrics[f'text_retrieval_recall@{recall_k}'] = (batchify(recall_at_k, scores.T, positive_pairs.T, batch_size, device, k=recall_k) > 0).float().mean().item()
    return metrics

def dataloader_with_indices(dataloader):
    start = 0
    for x, y in dataloader:
        end = start + len(x)
        inds = torch.arange(start, end)
        yield (x, y, inds)
        start = end

def recall_at_k(scores, positive_pairs, k):
    """
    Compute the recall at k for each sample
    :param scores: compability score between  text and image embeddings (nb texts, nb images)
    :param k: number of images to consider per text, for retrieval
    :param positive_pairs: boolean matrix of positive pairs (nb texts, nb images)
    :return: recall at k averaged over all texts
    """
    nb_texts, nb_images = scores.shape
    topk_indices = torch.topk(scores, k, dim=1)[1]
    nb_positive = positive_pairs.sum(dim=1)
    topk_indices_onehot = torch.nn.functional.one_hot(topk_indices, num_classes=nb_images)
    positive_pairs_reshaped = positive_pairs.view(nb_texts, 1, nb_images)
    nb_true_positive = (topk_indices_onehot * positive_pairs_reshaped).sum(dim=(1, 2))
    recall_at_k = nb_true_positive / nb_positive
    return recall_at_k

def batchify(func, X, Y, batch_size, device, *args, **kwargs):
    results = []
    for start in range(0, len(X), batch_size):
        end = start + batch_size
        x = X[start:end].to(device)
        y = Y[start:end].to(device)
        result = func(x, y, *args, **kwargs).cpu()
        results.append(result)
    return torch.cat(results)

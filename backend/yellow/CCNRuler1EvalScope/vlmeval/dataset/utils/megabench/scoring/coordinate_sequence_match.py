# Private iCAP Yellow implementation. Do not publish.
import logging
from .common.conversions import str_to_coords
import numpy as np

class CoordsSequenceSimilarity:
    """
    Measure the similarity between two list of coordinates, used for keypoint estimation tasks
    """

    @staticmethod
    def compute_score(pred_keypoints, gt_keypoints, k=10):
        """
        Compute the evaluation score for keypoint estimation.

        Args:
            pred_keypoints (list or np.ndarray): List or array of predicted keypoint coordinates,
                                                 each as (x, y), normalized to [0, 1].
            gt_keypoints (list or np.ndarray): List or array of ground truth keypoint coordinates,
                                               each as (x, y), normalized to [0, 1].

        Returns:
            float: A score between 0 and 1, where 1 indicates perfect accuracy,
                   and 0 indicates completely wrong.
        """
        try:
            pred_keypoints = np.array(pred_keypoints)
        except ValueError:
            return 0
        gt_keypoints = np.array(gt_keypoints)
        if pred_keypoints.shape != gt_keypoints.shape:
            return 0
        distances = np.linalg.norm(pred_keypoints - gt_keypoints, axis=1)
        max_distance = np.sqrt(2)
        normalized_distances = distances / max_distance
        per_keypoint_scores = np.exp(-k * normalized_distances)
        score = np.mean(per_keypoint_scores)
        return score

    @classmethod
    def match(cls, responses, targets) -> float:
        """Exact match between targets and responses."""
        logging.debug(f'responses={responses!r}, targets={targets!r}')
        if not isinstance(responses, tuple | list):
            responses = str_to_coords(responses, dim=2)
        if not isinstance(targets, tuple | list):
            targets = str_to_coords(targets, dim=2)
        return cls.compute_score(responses, targets)

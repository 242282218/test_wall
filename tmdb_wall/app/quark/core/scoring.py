from typing import List

from app.quark.core.models import MatchResult


def compute_overall(confidence: float, quality_score: float, c_w: float = 0.7, q_w: float = 0.3) -> float:
    """
    计算综合评分
    
    Args:
        confidence: 置信度 (0.0-1.0)
        quality_score: 画质评分 (0.0-1.0)
        c_w: 置信度权重 (默认 0.7)
        q_w: 画质权重 (默认 0.3)
        
    Returns:
        综合评分 (0.0-1.0)
    """
    return round(confidence * c_w + quality_score * q_w, 4)


def rank_results(results: List[MatchResult], similarity_band: float = 0.06) -> List[MatchResult]:
    if not results:
        return []
    band = max(similarity_band, 0.0)
    max_confidence = max(r.confidence for r in results)

    def sort_key(result: MatchResult) -> tuple:
        if band > 0.0 and max_confidence - result.confidence <= band:
            return (1, result.quality_score, result.overall_score, result.confidence)
        return (0, result.confidence, result.overall_score, result.quality_score)

    return sorted(results, key=sort_key, reverse=True)


def mark_best(results: List[MatchResult]) -> None:
    """
    标记最佳结果
    
    Args:
        results: 匹配结果列表（假设已按 overall_score 降序排序）
    """
    if not results:
        return
    
    # 标记最高分的为最佳
    if results:
        results[0].is_best = True
        # 其他结果标记为非最佳
        for result in results[1:]:
            result.is_best = False


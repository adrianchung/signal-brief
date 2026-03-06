import logging

logger = logging.getLogger(__name__)


def rank_stories(stories: list[dict], keywords: list[str], top_n: int = 10) -> list[dict]:
    """Rank stories by keyword relevance in title, falling back to HN score as tiebreaker.

    Returns the top_n most relevant stories. If ranking fails, falls back to
    HN score ordering (i.e. the original sort order from fetch_stories).
    """
    if not stories:
        return stories

    try:
        lower_keywords = [kw.lower() for kw in keywords]

        def relevance_score(story: dict) -> tuple[int, int]:
            title = story.get("title", "").lower()
            matches = sum(1 for kw in lower_keywords if kw in title)
            return (matches, story.get("score", 0))

        ranked = sorted(stories, key=relevance_score, reverse=True)
        result = ranked[:top_n]
        logger.info(
            "Ranked %d stories → kept top %d (keyword match scores: %s)",
            len(stories),
            len(result),
            [relevance_score(s)[0] for s in result],
        )
        return result
    except Exception:
        logger.exception("Ranking failed — falling back to HN score ordering")
        return stories[:top_n]

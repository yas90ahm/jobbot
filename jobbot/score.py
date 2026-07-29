import re

STOPWORDS = {
    'with', 'from', 'have', 'that', 'this', 'will', 'work', 'team', 'experience',
    'your', 'for', 'and', 'the', 'are', 'you', 'all', 'can', 'her', 'was', 'one',
    'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new',
    'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'any', 'but', 'not',
}


def _extract_tokens(text: str) -> set[str]:
    """Extract lowercase alphabetic tokens of length >= 4, minus stopwords."""
    if not text:
        return set()
    text = text.lower()
    tokens = re.findall(r'[a-z]{4,}', text)
    return set(tokens) - STOPWORDS


def score_job(job: dict, resume_text: str, keywords: list[str]) -> float:
    """Score job match against resume.

    Args:
        job: Dict with keys title (str), description (str). Either may be empty/None.
        resume_text: Extracted resume text.
        keywords: List of keywords to search for.

    Returns:
        Float 0-100 rounded to 1 decimal place.
        - Keywords in title: +15 each, capped at 45 total.
        - Keywords in description: +5 each, capped at 20 total.
        - Resume overlap (tokens >= 4 chars minus stopwords): ratio * 175, capped at 35.
    """
    title = job.get('title') or ''
    description = job.get('description') or ''

    score = 0.0

    # whole-word match only: the keyword "AI" must not match inside "Dietary Aide"
    def hit(kw, text):
        return re.search(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])",
                         text.lower()) is not None

    title_matches = sum(1 for kw in keywords if hit(kw, title))
    score += min(title_matches * 15, 45)

    desc_matches = sum(1 for kw in keywords if hit(kw, description))
    score += min(desc_matches * 5, 20)

    resume_tokens = _extract_tokens(resume_text)
    desc_tokens = _extract_tokens(description)

    if desc_tokens:
        overlap = len(resume_tokens & desc_tokens)
        overlap_ratio = overlap / len(desc_tokens)
    else:
        overlap_ratio = 0.0

    overlap_score = min(overlap_ratio * 175, 35)
    score += overlap_score

    score = max(0.0, min(100.0, score))
    return round(score, 1)

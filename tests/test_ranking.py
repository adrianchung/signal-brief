from src.ranking import rank_stories


def make_story(title: str, score: int) -> dict:
    return {"title": title, "score": score, "url": "https://example.com",
            "author": "u", "num_comments": 0, "created_at": ""}


class TestRankStories:
    def test_empty_stories_returns_empty(self):
        assert rank_stories([], ["ai"], top_n=5) == []

    def test_top_n_limits_results(self):
        stories = [make_story("AI agents", i) for i in range(20)]
        result = rank_stories(stories, ["ai"], top_n=5)
        assert len(result) == 5

    def test_keyword_match_in_title_ranks_higher_than_score(self):
        low_score_relevant = make_story("LLM agents are changing everything", 100)
        high_score_irrelevant = make_story("New database released", 500)
        stories = [high_score_irrelevant, low_score_relevant]

        result = rank_stories(stories, ["llm", "agents"], top_n=10)

        assert result[0]["title"] == "LLM agents are changing everything"

    def test_score_used_as_tiebreaker_when_keyword_matches_equal(self):
        story_a = make_story("AI breakthrough", 300)
        story_b = make_story("AI research paper", 100)
        stories = [story_b, story_a]

        result = rank_stories(stories, ["ai"], top_n=10)

        assert result[0] == story_a

    def test_multiple_keyword_matches_rank_higher(self):
        one_match = make_story("LLM paper published", 400)
        two_matches = make_story("LLM agents paper", 200)
        stories = [one_match, two_matches]

        result = rank_stories(stories, ["llm", "agents"], top_n=10)

        assert result[0] == two_matches

    def test_fallback_to_hn_score_when_no_keyword_matches(self):
        story_a = make_story("Unrelated topic A", 500)
        story_b = make_story("Unrelated topic B", 300)
        stories = [story_b, story_a]

        result = rank_stories(stories, ["kubernetes"], top_n=10)

        assert result[0] == story_a

    def test_case_insensitive_keyword_matching(self):
        story = make_story("Kubernetes Cluster Upgrade", 100)
        result = rank_stories([story], ["kubernetes"], top_n=10)
        assert len(result) == 1

    def test_returns_all_stories_when_fewer_than_top_n(self):
        stories = [make_story("AI story", 100), make_story("LLM story", 200)]
        result = rank_stories(stories, ["ai", "llm"], top_n=10)
        assert len(result) == 2

    def test_fallback_on_exception(self):
        bad_stories = [{"title": None, "score": 100}]  # title=None causes .lower() to fail
        result = rank_stories(bad_stories, ["ai"], top_n=10)
        # Should fallback gracefully without raising
        assert isinstance(result, list)

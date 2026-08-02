import unittest
from unittest.mock import AsyncMock, patch

from scripts import binance_scraper


def _post(post_id: int) -> dict[str, str]:
    return {
        "url": f"https://www.binance.com/en/square/post/{post_id}",
        "text": "observable feed card with enough text for collection",
        "time": "1h",
        "author": "author",
    }


def _batch(posts: list[dict[str, str]], *, top: int, height: int, bottom: bool) -> dict:
    return {
        "candidateLinks": len(posts),
        "candidateBlocks": len(posts),
        "invalidUrls": 0,
        "posts": posts,
        "documentHeight": height,
        "scrollTop": top,
        "viewportHeight": 800,
        "reachedBottom": bottom,
    }


class FeedCollectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_bottom_lazy_load_uses_separate_leave_and_return_phases(self) -> None:
        first_page = [_post(index) for index in range(1, 5)]
        second_page = [_post(index) for index in range(1, 21)]
        batches = iter(
            [
                _batch(first_page, top=6794, height=7677, bottom=True),
                _batch(second_page, top=6794, height=15000, bottom=True),
            ]
        )
        expressions: list[str] = []
        waits: list[float] = []

        async def evaluator(_websocket: object, expression: str) -> dict:
            expressions.append(expression)
            if expression == binance_scraper.SCROLL_TO_TOP_JS:
                return {
                    "before": 0,
                    "after": 0,
                    "documentHeight": 7677,
                    "viewportHeight": 883,
                    "reachedBottom": False,
                }
            if expression == binance_scraper.COLLECT_POSTS_JS:
                return next(batches)
            if expression == binance_scraper.LEAVE_BOTTOM_JS:
                return {
                    "before": 6794,
                    "after": 5594,
                    "documentHeight": 7677,
                    "viewportHeight": 883,
                    "reachedBottom": False,
                }
            if expression == binance_scraper.RETURN_TO_BOTTOM_JS:
                return {
                    "before": 5594,
                    "after": 6794,
                    "documentHeight": 7677,
                    "viewportHeight": 883,
                    "reachedBottom": True,
                }
            if expression == binance_scraper.SCROLL_JS:
                raise AssertionError("bottom trigger was collapsed into one JS evaluation")
            raise AssertionError(expression)

        async def sleeper(delay: float) -> None:
            waits.append(delay)

        result = await binance_scraper.collect_feed_discovery(
            object(),
            evaluator=evaluator,
            sleeper=sleeper,
            preferred_minimum=100,
            hard_limit=200,
            max_scrolls=1,
            stagnant_rounds=10,
            scroll_delay=1.0,
            load_trigger_delay=0.35,
        )

        self.assertEqual(20, len(result.posts))
        self.assertEqual(
            "BINANCE_SQUARE_DISCOVER_DOM",
            result.discovery_result["coverage_scope"],
        )
        self.assertFalse(result.discovery_result["global_denominator_known"])
        self.assertFalse(
            result.discovery_result["pagination_api_exhaustion_verified"]
        )
        self.assertEqual(1, result.discovery_result["load_trigger_attempts"])
        self.assertEqual(
            ["LEAVE_BOTTOM", "RETURN_TO_BOTTOM"],
            [
                phase["phase"]
                for phase in result.discovery_result["load_trigger_observations"]
            ],
        )
        self.assertEqual([0.35, 1.0], waits)

    async def test_valid_post_url_is_discovered_even_when_feed_card_text_is_sparse(self) -> None:
        sparse = _post(42)
        sparse["text"] = ""

        async def evaluator(_websocket: object, expression: str) -> dict:
            if expression == binance_scraper.SCROLL_TO_TOP_JS:
                return {
                    "before": 0,
                    "after": 0,
                    "documentHeight": 1600,
                    "viewportHeight": 800,
                    "reachedBottom": False,
                }
            if expression == binance_scraper.COLLECT_POSTS_JS:
                return _batch([sparse], top=0, height=1600, bottom=False)
            raise AssertionError(expression)

        result = await binance_scraper.collect_feed_discovery(
            object(),
            evaluator=evaluator,
            sleeper=lambda _delay: _no_wait(),
            preferred_minimum=1,
            hard_limit=1,
            max_scrolls=0,
            stagnant_rounds=2,
        )

        self.assertEqual(1, len(result.posts))
        self.assertEqual(
            "https://www.binance.com/en/square/post/42", result.posts[0]["url"]
        )

    async def test_middle_stagnation_does_not_stop_before_later_posts_arrive(self) -> None:
        batches = iter(
            [
                _batch([_post(1)], top=0, height=8000, bottom=False),
                _batch([_post(1)], top=1200, height=8000, bottom=False),
                _batch([_post(1)], top=2400, height=8000, bottom=False),
                _batch([_post(1), _post(2)], top=3600, height=10000, bottom=False),
                _batch([_post(1), _post(2)], top=4800, height=10000, bottom=False),
            ]
        )
        scroll_top = {
            "before": 7568,
            "after": 0,
            "documentHeight": 8451,
            "viewportHeight": 800,
            "reachedBottom": False,
        }
        scrolls = iter(
            {
                "before": position,
                "after": position + 1200,
                "documentHeight": height,
                "viewportHeight": 800,
                "reachedBottom": False,
            }
            for position, height in (
                (0, 8000),
                (1200, 8000),
                (2400, 8000),
                (3600, 10000),
            )
        )

        async def evaluator(_websocket: object, expression: str) -> dict:
            if expression == binance_scraper.SCROLL_TO_TOP_JS:
                return scroll_top
            if expression == binance_scraper.COLLECT_POSTS_JS:
                return next(batches)
            if expression == binance_scraper.SCROLL_JS:
                return next(scrolls)
            raise AssertionError(f"unexpected expression: {expression}")

        result = await binance_scraper.collect_feed_discovery(
            object(),
            evaluator=evaluator,
            sleeper=lambda _delay: _no_wait(),
            preferred_minimum=4,
            hard_limit=200,
            max_scrolls=4,
            stagnant_rounds=2,
        )

        self.assertEqual(
            [1, 2],
            [int(post["url"].rsplit("/", 1)[1]) for post in result.posts],
        )
        self.assertEqual("SCROLL_LIMIT", result.discovery_result["termination_reason"])
        self.assertEqual(4, result.discovery_result["scroll_rounds"])

    async def test_exhaustion_cannot_be_complete_when_top_reset_fails(self) -> None:
        batches = iter(
            [
                _batch([_post(1), _post(2)], top=300, height=1100, bottom=True),
                _batch([_post(1), _post(2)], top=300, height=1100, bottom=True),
                _batch([_post(1), _post(2)], top=300, height=1100, bottom=True),
            ]
        )

        async def evaluator(_websocket: object, expression: str) -> dict:
            if expression == binance_scraper.SCROLL_TO_TOP_JS:
                return {
                    "before": 7568,
                    "after": 300,
                    "documentHeight": 1100,
                    "viewportHeight": 800,
                    "reachedBottom": True,
                }
            if expression == binance_scraper.COLLECT_POSTS_JS:
                return next(batches)
            if expression == binance_scraper.LEAVE_BOTTOM_JS:
                return {
                    "before": 300,
                    "after": 0,
                    "documentHeight": 1100,
                    "viewportHeight": 800,
                    "scrollRange": 300,
                    "reachedBottom": False,
                }
            if expression == binance_scraper.RETURN_TO_BOTTOM_JS:
                return {
                    "before": 0,
                    "after": 300,
                    "documentHeight": 1100,
                    "viewportHeight": 800,
                    "scrollRange": 300,
                    "reachedBottom": True,
                }
            raise AssertionError(expression)

        result = await binance_scraper.collect_feed_discovery(
            object(),
            evaluator=evaluator,
            sleeper=lambda _delay: _no_wait(),
            preferred_minimum=2,
            hard_limit=200,
            max_scrolls=5,
            stagnant_rounds=2,
        )

        self.assertEqual("PARTIAL", result.discovery_result["coverage_status"])
        self.assertEqual("STAGNANT", result.discovery_result["termination_reason"])

    async def test_exhausted_hard_limit_and_scroll_limit_are_distinct(self) -> None:
        top = {
            "before": 500,
            "after": 0,
            "documentHeight": 1600,
            "viewportHeight": 800,
            "reachedBottom": False,
        }

        async def collect_with(
            batches: list[dict],
            *,
            preferred_minimum: int,
            hard_limit: int,
            max_scrolls: int,
            stagnant_rounds: int = 2,
        ):
            pending = iter(batches)

            async def evaluator(_websocket: object, expression: str) -> dict:
                if expression == binance_scraper.SCROLL_TO_TOP_JS:
                    return top
                if expression == binance_scraper.COLLECT_POSTS_JS:
                    return next(pending)
                if expression == binance_scraper.LEAVE_BOTTOM_JS:
                    return {
                        "before": 800,
                        "after": 0,
                        "documentHeight": 1600,
                        "viewportHeight": 800,
                        "scrollRange": 800,
                        "reachedBottom": False,
                    }
                if expression == binance_scraper.RETURN_TO_BOTTOM_JS:
                    return {
                        "before": 0,
                        "after": 800,
                        "documentHeight": 1600,
                        "viewportHeight": 800,
                        "scrollRange": 800,
                        "reachedBottom": True,
                    }
                raise AssertionError(expression)

            return await binance_scraper.collect_feed_discovery(
                object(),
                evaluator=evaluator,
                sleeper=lambda _delay: _no_wait(),
                preferred_minimum=preferred_minimum,
                hard_limit=hard_limit,
                max_scrolls=max_scrolls,
                stagnant_rounds=stagnant_rounds,
            )

        exhausted = await collect_with(
            [
                _batch([_post(1), _post(2)], top=800, height=1600, bottom=True),
                _batch([_post(1), _post(2)], top=800, height=1600, bottom=True),
                _batch([_post(1), _post(2)], top=800, height=1600, bottom=True),
            ],
            preferred_minimum=2,
            hard_limit=200,
            max_scrolls=5,
        )
        capped = await collect_with(
            [_batch([_post(1), _post(2)], top=0, height=1600, bottom=False)],
            preferred_minimum=2,
            hard_limit=2,
            max_scrolls=5,
        )
        scroll_limited = await collect_with(
            [_batch([_post(1)], top=0, height=1600, bottom=False)],
            preferred_minimum=2,
            hard_limit=200,
            max_scrolls=0,
        )

        self.assertEqual(
            ("BOUNDED_COMPLETE", "EXHAUSTED"),
            (
                exhausted.discovery_result["coverage_status"],
                exhausted.discovery_result["termination_reason"],
            ),
        )
        self.assertEqual(
            ("CAPPED", "HARD_LIMIT", True),
            (
                capped.discovery_result["coverage_status"],
                capped.discovery_result["termination_reason"],
                capped.discovery_result["truncated"],
            ),
        )
        self.assertEqual(
            ("PARTIAL", "SCROLL_LIMIT"),
            (
                scroll_limited.discovery_result["coverage_status"],
                scroll_limited.discovery_result["termination_reason"],
            ),
        )

    async def test_runtime_evaluate_exception_details_fail_explicitly(self) -> None:
        response = {
            "exceptionDetails": {
                "text": "Uncaught",
                "exception": {"description": "ReferenceError: feed is not defined"},
            },
            "result": {"type": "undefined"},
        }
        with patch.object(binance_scraper, "cdp", AsyncMock(return_value=response)):
            with self.assertRaisesRegex(
                RuntimeError, "ReferenceError: feed is not defined"
            ):
                await binance_scraper.evaluate_value(object(), "feed")


async def _no_wait() -> None:
    return None


if __name__ == "__main__":
    unittest.main()

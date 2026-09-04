import argparse
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("generate_video.py")
SPEC = importlib.util.spec_from_file_location("atlas_video_gen", SCRIPT)
atlas_video_gen = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(atlas_video_gen)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class AtlasVideoGenTests(unittest.TestCase):
    def test_payload_matches_vetted_veo_lite_schema(self):
        args = argparse.Namespace(
            prompt="A lighthouse at sunrise",
            ratio="16:9",
            duration=4,
            resolution="720p",
            seed=-1,
        )
        self.assertEqual(
            atlas_video_gen.build_payload(args),
            {
                "model": "google/veo3.1-lite/text-to-video",
                "prompt": "A lighthouse at sunrise",
                "aspect_ratio": "16:9",
                "duration": 4,
                "resolution": "720p",
                "seed": -1,
            },
        )

    @mock.patch.object(atlas_video_gen.urllib.request, "urlopen")
    def test_submission_posts_once_and_accepts_wrapped_response(self, urlopen):
        urlopen.return_value = FakeResponse(
            {"code": 200, "data": {"id": "prediction-123", "status": "created"}}
        )

        prediction_id = atlas_video_gen.submit_prediction(
            "secret", {"model": atlas_video_gen.MODEL, "prompt": "test"}
        )

        self.assertEqual(prediction_id, "prediction-123")
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertNotIn("secret", request.data.decode("utf-8"))

    @mock.patch.object(atlas_video_gen, "_request_json")
    def test_polling_accepts_flat_completed_response(self, request_json):
        request_json.side_effect = [
            {"status": "processing", "outputs": []},
            {"status": "completed", "outputs": ["https://example.com/video.mp4"]},
        ]
        ticks = iter([0.0, 0.0, 1.0])

        outputs = atlas_video_gen.poll_prediction(
            "secret",
            "prediction-123",
            poll_interval=1,
            timeout=10,
            sleep=lambda _seconds: None,
            clock=lambda: next(ticks),
        )

        self.assertEqual(outputs, ["https://example.com/video.mp4"])
        self.assertEqual(request_json.call_count, 2)
        self.assertTrue(all(call.kwargs["attempts"] == 3 for call in request_json.call_args_list))

    def test_preview_does_not_read_credentials_or_use_network(self):
        with mock.patch.dict(atlas_video_gen.os.environ, {}, clear=True), mock.patch.object(
            atlas_video_gen, "submit_prediction"
        ) as submit:
            exit_code = atlas_video_gen.main(
                ["A lighthouse at sunrise", "--output", "preview.mp4"]
            )

        self.assertEqual(exit_code, 2)
        submit.assert_not_called()

    def test_1080p_requires_eight_seconds(self):
        args = argparse.Namespace(
            prompt="test",
            ratio="16:9",
            duration=6,
            resolution="1080p",
            seed=-1,
        )
        with self.assertRaisesRegex(atlas_video_gen.AtlasVideoError, "duration 8"):
            atlas_video_gen.build_payload(args)


if __name__ == "__main__":
    unittest.main()

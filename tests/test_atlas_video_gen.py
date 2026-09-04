import importlib.util
from pathlib import Path


SCRIPT_TEST = (
    Path(__file__).resolve().parents[1]
    / "skills/atlas-video-gen/scripts/test_generate_video.py"
)
SPEC = importlib.util.spec_from_file_location("atlas_video_gen_tests", SCRIPT_TEST)
atlas_video_gen_tests = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(atlas_video_gen_tests)

AtlasVideoGenTests = atlas_video_gen_tests.AtlasVideoGenTests

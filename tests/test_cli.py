import pytest

from prinfo import __version__
from prinfo.cli import build_parser


def test_build_parser_supports_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit, match="0"):
        parser.parse_args(["--version"])

    captured = capsys.readouterr()
    assert captured.out.strip() == f"prinfo {__version__}"

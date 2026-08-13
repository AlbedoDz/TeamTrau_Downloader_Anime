from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from downloader.cli import app

runner = CliRunner()


@patch("downloader.cli.BatchDownloader")
def test_cli_arguments_propagation(mock_downloader_cls) -> None:
    # Set up mock instance
    mock_downloader = MagicMock()
    mock_downloader_cls.return_value = mock_downloader

    # Run command with all the new flags
    runner.invoke(
        app,
        [
            "-u",
            "https://anikototv.to/watch/haibara-s-teenage-new-game-8axzw",
            "-e",
            "1",
            "-x",
            "HD-1,VidCloud-1",
            "-p",
            "vidplay,vidstream",
            "-i",
            "-s",
            "vidplay",
            "--sub-only",
        ],
    )

    # CLI runs but might exit or raise if execution fails further down,
    # but the downloader creation happens before the loop.
    assert mock_downloader_cls.called

    # Get the arguments passed to BatchDownloader instantiation
    _init_args, init_kwargs = mock_downloader_cls.call_args
    assert init_kwargs["exclude_servers"] == ["HD-1", "VidCloud-1"]
    assert init_kwargs["server_priority"] == ["vidplay", "vidstream"]
    assert init_kwargs["interactive"] is True
    assert init_kwargs["only_server"] == "vidplay"

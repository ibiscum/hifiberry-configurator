from pathlib import Path
from unittest.mock import MagicMock, patch
import logging

from configurator.soundcard_detector import SoundcardDetector


def _detector(tmp_path: Path) -> SoundcardDetector:
    cfg = tmp_path / "config.txt"
    cfg.write_text("# test\n", encoding="utf-8")
    return SoundcardDetector(config_file=str(cfg))


def test_detect_card_uses_configdb_pin_before_hardware_detection(tmp_path: Path) -> None:
    det = _detector(tmp_path)

    with patch("configurator.soundcard_detector.ConfigDB") as mock_db_cls, \
         patch.object(det, "detect_from_config_txt_comment") as mock_comment, \
         patch.object(det, "_map_hat_to_overlay") as mock_hat_map, \
         patch.object(det, "_probe_i2c") as mock_i2c, \
         patch.object(det, "_find_hifiberry_card_from_aplay") as mock_aplay:
        mock_db = MagicMock()
        mock_db.get.return_value = "DAC+ Pro"
        mock_db_cls.return_value = mock_db

        det.detect_card()

    assert det.detected_card == "DAC+ Pro"
    assert det.detected_overlay is None
    mock_comment.assert_not_called()
    mock_hat_map.assert_not_called()
    mock_i2c.assert_not_called()
    mock_aplay.assert_not_called()


def test_detect_card_uses_comment_pin_when_configdb_empty(tmp_path: Path) -> None:
    det = _detector(tmp_path)

    with patch("configurator.soundcard_detector.ConfigDB") as mock_db_cls, \
         patch.object(det, "detect_from_config_txt_comment", return_value="Amp3") as mock_comment, \
         patch.object(det, "_map_hat_to_overlay") as mock_hat_map:
        mock_db = MagicMock()
        mock_db.get.return_value = None
        mock_db_cls.return_value = mock_db

        det.detect_card()

    assert det.detected_card == "Amp3"
    assert det.detected_overlay is None
    mock_comment.assert_called_once_with()
    mock_hat_map.assert_not_called()


def test_detect_card_ignore_pin_skips_configdb_and_comment(tmp_path: Path) -> None:
    det = _detector(tmp_path)

    with patch("configurator.soundcard_detector.ConfigDB") as mock_db_cls, \
         patch.object(det, "detect_from_config_txt_comment") as mock_comment, \
         patch("configurator.soundcard_detector.get_hat_info", return_value={"product": None}), \
         patch.object(det, "_map_hat_to_overlay", return_value=None), \
         patch.object(det, "_probe_i2c", return_value=None), \
         patch.object(det, "_find_hifiberry_card_from_aplay", return_value="card 0: snd_rpi_hifiberry_dacplus"), \
         patch.object(det, "_detect_from_arecord", return_value=None), \
         patch.object(det, "_probe_dsp", return_value=None), \
         patch.object(det, "_validate_detected_card", return_value=True), \
         patch.object(det, "_get_card_name", return_value="DAC+ Standard"):
        det.detect_card(ignore_pin=True)

    assert det.detected_overlay == "dacplus-std"
    assert det.detected_card == "DAC+ Standard"
    mock_db_cls.assert_not_called()
    mock_comment.assert_not_called()


def test_run_command_uses_subprocess_run_without_shell(tmp_path: Path) -> None:
    det = _detector(tmp_path)

    with patch("configurator.soundcard_detector.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="ok\n")

        result = det._run_command(["aplay", "-l"])

    assert result == "ok"
    _, kwargs = mock_run.call_args
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert "shell" not in kwargs


def test_probe_i2c_does_not_persist_config_changes(tmp_path: Path) -> None:
    det = _detector(tmp_path)
    det.config = MagicMock()

    with patch.object(det, "_run_command", return_value="0x07"):
        result = det._probe_i2c()

    assert result == "dacplusadcpro"
    det.config.enable_i2c.assert_not_called()
    det.config.save.assert_not_called()


def test_setup_hifiberry_logger_replaces_stale_file_handler(tmp_path: Path) -> None:
    log1 = str(tmp_path / "hifiberry-1.log")
    log2 = str(tmp_path / "hifiberry-2.log")
    logger = logging.getLogger("hifiberry_events")

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    with patch("configurator.soundcard_detector.ConfigTxt", return_value=MagicMock(lines=[])):
        SoundcardDetector(config_file=str(tmp_path / "config.txt"), hifiberry_log_file=log1)
        SoundcardDetector(config_file=str(tmp_path / "config.txt"), hifiberry_log_file=log2)

    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]

    assert len(file_handlers) == 1
    assert Path(file_handlers[0].baseFilename) == Path(log2)

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

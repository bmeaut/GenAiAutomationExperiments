import pytest
from llm_bug_analysis.core import logger
from unittest.mock import Mock


class TestLogger:

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        logger.reset()
        yield
        logger.reset()

    def test_log_prints_to_console_by_default(self, capsys):
        logger.log("Hello universe!")
        captured = capsys.readouterr()
        assert "Hello universe!" in captured.out

    def test_log_with_callback_does_not_print(self, capsys):
        messages = []
        logger.set_callback(messages.append)
        logger.log("Test message")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert messages == ["Test message"]

    def test_reset_clears_callback(self, capsys):
        messages = []
        logger.set_callback(messages.append)
        logger.log("this")

        logger.reset()
        logger.log("that")

        assert messages == ["this"]
        captured = capsys.readouterr()
        assert "that" in captured.out

    def test_multiple_messages_to_callback(self):
        messages = []
        logger.set_callback(messages.append)

        logger.log("first")
        logger.log("second")
        logger.log("third")

        assert messages == ["first", "second", "third"]

    @pytest.mark.parametrize(
        "message",
        [
            "Simple message",
            "Emojis (suprising amounts of commits use these): 🎉",
            "Multiline message:\nLine 1\nLine 2",
            "",
            " " * 1000,
        ],
    )
    # TODO: add unicode special characters?
    def test_log_handles_various_message_formats(self, message, capsys):
        logger.log(message)

        captured = capsys.readouterr()
        assert message in captured.out

    def test_callback_exception_falls_back_to_console(self, capsys):
        def broken_callback(msg):
            raise ValueError("Callback failed!")

        logger.set_callback(broken_callback)
        logger.log("this should not crash")

        captured = capsys.readouterr()
        assert "ERROR: Logging callback failed:" in captured.out
        assert "Original message: this should not crash" in captured.out

    def test_callback_with_mock(self):
        mock_callback = Mock()
        logger.set_callback(mock_callback)

        logger.log("test message")

        mock_callback.assert_called_once_with("test message")

    def test_callback_called_multiple_times(self):
        mock_callback = Mock()
        logger.set_callback(mock_callback)

        logger.log("first")
        logger.log("second")
        logger.log("third")

        assert mock_callback.call_count == 3

        mock_callback.assert_any_call("first")
        mock_callback.assert_any_call("second")
        mock_callback.assert_any_call("third")

    def test_set_callback_replaces_previous(self):
        first_callback = Mock()
        second_callback = Mock()

        logger.set_callback(first_callback)
        logger.log("first message")

        logger.set_callback(second_callback)
        logger.log("second message")

        first_callback.assert_called_once_with("first message")
        second_callback.assert_called_once_with("second message")

"""Pytest testcases for exercising rrdd.py - API().lazy_complete_init()"""
import io
import sys
from contextlib import contextmanager
from warnings import catch_warnings, simplefilter

# Handle DeprecationWarning from importing imp (it was removed with Python 3.12)
with catch_warnings():
    simplefilter(action="ignore", category=DeprecationWarning)
    import rrdd


# pylint: disable-next=redefined-outer-name  # pytest fixture, see above
def test_lazy_complete_init(tmp_path):  # type(Path)
    """Test the method rrdd.API().lazy_complete_init()"""

    temporary_filepath = (tmp_path / "new_subdir_to_create" / "file").as_posix()

    # Touchstone analysis function for testing rrdd.API().lazy_complete_init()
    def handle_lazy_complete_init_calls(dispatcher_and_methodname, args):
        """Callback, called by the Fake dispatcher's method-__call__ handler"""

        assert dispatcher_and_methodname.split(".")[0] == "dispatcher"
        called_methodname = dispatcher_and_methodname.split(".")[1]

        if called_methodname == "get_path":
            assert args[0]["uid"] == "fake_plugin_id"
            return temporary_filepath

        if called_methodname == "get_header":
            return "header"

        if called_methodname == "deregister":  # called by finalizer api.__del__():
            return "return a string for pylint: [inconsistent-return-statements]"

        raise NotImplementedError(called_methodname)

    # Prepare
    @contextmanager
    def rrdd_api_testee():
        """Test context manager ensuring testee creation and teardown"""

        api = rrdd.API("fake_plugin_id")
        api.dispatcher = rrdd.Dispatcher(handle_lazy_complete_init_calls, "dispatcher")

        # Verify - Pre-Step:
        assert not hasattr(api, "dest")
        assert not hasattr(api, "header")
        assert not hasattr(api, "path")

        # Act - Test initial fdopen to create a file at the temporary_filepath:
        api.lazy_complete_init()

        yield api  # Execute the test step

        # Verify - Post-Step:

        # Check that the touchstone analysis function calls were applied by test:
        assert hasattr(api, "header")  # tells pytype that api.header exists now.
        assert api.header == "header"
        assert api.path == temporary_filepath

        # Test api.dest to be of the expected binary random access file type:
        if sys.version_info > (3,):
            assert isinstance(api.dest, io.BufferedRandom)
        else:
            assert isinstance(api.dest, file)  # pylint: disable=undefined-variable
            assert "b" in api.dest.mode

        # Close the file, ensuring that data is written and finalize the object
        api.dest.close()
        del api

    # Legend of the 3 step test process:

    # Step 1 write: older data
    # Step 2 write: newer
    # Step 3 reads: newer data (and asserts this expected result)

    # Step 1:
    with rrdd_api_testee() as api:  # Create  file in tmp_path
        api.dest.write(b"#older ")  # Write "#older " at pos 0
        api.dest.write(b"content")  # Write "content" after it

    # Step 2:
    with rrdd_api_testee() as api:  # Open existing file, not truncating it
        api.dest.write(b"#newer ")  # Write "newer " at pos 0

    # Step 3:
    with rrdd_api_testee() as api:  # Assert the expected result:
        assert api.dest.read() == b"#newer content"

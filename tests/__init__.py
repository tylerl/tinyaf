import pytest

pytest.register_assert_rewrite("tests.helper")
# pytest.register_assert_rewrite("tests.util.pytest_compare")
pytest.register_assert_rewrite("tests.util.wsgi")
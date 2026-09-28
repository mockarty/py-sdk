"""Small Test IT style pytest case reported to Mockarty.

Install ``mockarty`` with the pytest extra instead of the Test IT adapter,
then set ``MOCKARTY_BASE_URL``, ``MOCKARTY_API_KEY`` and
``MOCKARTY_NAMESPACE``. Run::

    pytest --testit -q examples/testit_pytest_transition.py

The test's import is the only code change from a Test IT style test. The
``--testit`` flag keeps the familiar command, but reports only to Mockarty.
"""

import mockarty.testit as testit


@testit.displayName("Login smoke")
@testit.externalId("login-smoke")
def test_login_smoke():
    with testit.step("Check response"):
        testit.addAttachments("Synthetic response OK", is_text=True, name="response.txt")
        assert 2 + 2 == 4

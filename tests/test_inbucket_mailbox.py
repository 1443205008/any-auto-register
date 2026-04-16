import unittest
from unittest.mock import patch

from core.base_mailbox import MailboxAccount, create_mailbox


class InbucketMailboxTests(unittest.TestCase):
    def _build_mailbox(self, **extra):
        config = {
            "inbucket_api_url": "https://mail.example.com",
            "inbucket_domain": "mail.example.com",
        }
        config.update(extra)
        return create_mailbox("inbucket", extra=config)

    def test_get_email_composes_local_address(self):
        mailbox = self._build_mailbox()

        with patch.object(type(mailbox), "_generate_local_part", return_value="demo1234"):
            account = mailbox.get_email()

        self.assertEqual(account.email, "demo1234@mail.example.com")
        self.assertEqual(account.account_id, "demo1234@mail.example.com")
        self.assertEqual(account.extra["mailbox_name"], "demo1234")
        self.assertEqual(account.extra["mailbox_naming"], "local")

    def test_get_email_can_use_specified_full_address(self):
        mailbox = self._build_mailbox(inbucket_email="fixed-user@alt.example.com")

        account = mailbox.get_email()

        self.assertEqual(account.email, "fixed-user@alt.example.com")
        self.assertEqual(account.account_id, "fixed-user@alt.example.com")
        self.assertEqual(account.extra["mailbox_name"], "fixed-user")

    def test_get_email_can_use_specified_local_part(self):
        mailbox = self._build_mailbox(inbucket_email="fixed-user")

        account = mailbox.get_email()

        self.assertEqual(account.email, "fixed-user@mail.example.com")
        self.assertEqual(account.account_id, "fixed-user@mail.example.com")
        self.assertEqual(account.extra["mailbox_name"], "fixed-user")

    @patch("requests.request")
    def test_get_current_ids_uses_full_mailbox_name_when_configured(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = [
            {"id": "m1", "subject": "Hello"},
            {"id": "m2", "subject": "World"},
        ]
        mock_request.return_value.text = ""

        mailbox = self._build_mailbox(inbucket_mailbox_naming="full")
        ids = mailbox.get_current_ids(MailboxAccount(email="demo@mail.example.com"))

        self.assertEqual(ids, {"m1", "m2"})
        mock_request.assert_called_once_with(
            "GET",
            "https://mail.example.com/api/v1/mailbox/demo@mail.example.com",
            params=None,
            json=None,
            headers={"accept": "application/json"},
            proxies=None,
            timeout=10,
        )

    @patch("time.sleep", return_value=None)
    @patch("requests.request")
    def test_wait_for_code_reads_detail_and_skips_excluded_codes(self, mock_request, _sleep):
        mock_request.side_effect = [
            _response(
                [
                    {"id": "m1", "subject": "Your code 111111"},
                ]
            ),
            _response(
                {
                    "id": "m1",
                    "subject": "Your code 111111",
                    "body": {"text": "111111"},
                }
            ),
            _response(
                [
                    {"id": "m1", "subject": "Your code 111111"},
                    {"id": "m2", "subject": "Your code 222222"},
                ]
            ),
            _response(
                {
                    "id": "m2",
                    "subject": "Verification code",
                    "body": {"text": "Your verification code is 222222"},
                }
            ),
        ]

        mailbox = self._build_mailbox()
        code = mailbox.wait_for_code(
            MailboxAccount(email="demo@mail.example.com"),
            timeout=5,
            exclude_codes={"111111"},
        )

        self.assertEqual(code, "222222")
        self.assertEqual(mock_request.call_count, 4)

    @patch("time.sleep", return_value=None)
    @patch("requests.request")
    def test_wait_for_code_filters_other_recipient_when_domain_mailbox_is_shared(self, mock_request, _sleep):
        mock_request.side_effect = [
            _response(
                [
                    {"id": "m2", "subject": "Your code 222222"},
                    {"id": "m1", "subject": "Your code 111111"},
                ]
            ),
            _response(
                {
                    "id": "m2",
                    "subject": "Your code 222222",
                    "header": {"To": ["other@mail.example.com"]},
                    "body": {"text": "Your verification code is 222222"},
                }
            ),
            _response(
                {
                    "id": "m1",
                    "subject": "Your code 111111",
                    "header": {"To": ["demo@mail.example.com"]},
                    "body": {"text": "Your verification code is 111111"},
                }
            ),
        ]

        mailbox = self._build_mailbox(inbucket_mailbox_naming="domain")
        code = mailbox.wait_for_code(
            MailboxAccount(email="demo@mail.example.com"),
            timeout=5,
        )

        self.assertEqual(code, "111111")
        self.assertEqual(mock_request.call_count, 3)


def _response(payload, status_code=200):
    response = unittest.mock.Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = ""
    return response


if __name__ == "__main__":
    unittest.main()

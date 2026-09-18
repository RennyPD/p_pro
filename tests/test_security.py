import unittest

from app.security import create_totp_secret, verify_totp


class SecurityTests(unittest.TestCase):
    def test_totp_generation_and_rfc_vector(self) -> None:
        self.assertGreaterEqual(len(create_totp_secret()), 32)
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        self.assertTrue(verify_totp(secret, "287082", timestamp=59))
        self.assertFalse(verify_totp(secret, "000000", timestamp=59))


if __name__ == "__main__":
    unittest.main()

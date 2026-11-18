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


def test_validation_messages_are_spanish():
    from app.validation_messages import spanish_message

    assert (
        spanish_message({"type": "missing", "loc": ("body", "email")}) == "Correo: es obligatorio"
    )
    assert (
        spanish_message(
            {"type": "string_too_short", "loc": ("body", "password"), "ctx": {"min_length": 8}}
        )
        == "Contraseña: debe tener al menos 8 caracteres"
    )
    assert (
        spanish_message({"type": "value_error", "msg": "Value error, Escribe un título"})
        == "Escribe un título"
    )

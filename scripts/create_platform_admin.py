"""Create a platform (super administration) account (Fase 4 B).

    python -m scripts.create_platform_admin admin@nexo.do "Nombre Apellido"

Asks for the password and prints the second-factor secret (TOTP) once: add it
to an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password).
The second factor is mandatory for every platform sign-in.
"""

import getpass
import sys
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.db.database import engine
from app.security import create_totp_secret
from app.services.platform import create_admin


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    email, name = sys.argv[1], sys.argv[2]
    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if len(password) < 12 or password != getpass.getpass("Repite la contraseña: "):
        raise SystemExit("La contraseña no coincide o es muy corta")
    secret = create_totp_secret()
    with Session(bind=engine) as db:
        create_admin(db, email, name, password, secret)
        db.commit()
    uri = f"otpauth://totp/Nexo%20Plataforma:{quote(email)}?secret={secret}&issuer=Nexo"
    print("Cuenta creada. Segundo factor (guárdalo ahora, no se vuelve a mostrar):")
    print(f"  Secreto: {secret}")
    print(f"  URI: {uri}")


if __name__ == "__main__":
    main()

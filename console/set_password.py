"""Interactive setup: writes only a salted scrypt verifier into .env."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server import hash_password


def main():
    envpath = Path(__file__).resolve().parent.parent / '.env'
    if not envpath.is_file():
        sys.exit('Bitte zuerst scripts/init.sh ausführen')
    pw = getpass.getpass('Passwort für die Light Console (mindestens 12 Zeichen): ')
    if pw != getpass.getpass('Passwort wiederholen: '):
        sys.exit('Passwörter stimmen nicht überein')
    try:
        hashed = hash_password(pw)
    except ValueError as exc:
        sys.exit(str(exc))
    lines = [s for s in envpath.read_text().splitlines() if not s.startswith('CONSOLE_PASSWORD_HASH=')]
    lines.append('CONSOLE_PASSWORD_HASH=' + hashed)
    envpath.write_text('\n'.join(lines) + '\n')
    envpath.chmod(0o600)
    print('Scrypt-Prüfwert in .env gespeichert (kein Klartextpasswort).')


if __name__ == '__main__':
    main()

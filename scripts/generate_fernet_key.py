"""Print a new Fernet key for ENCRYPTION_SECRET_KEY."""

from cryptography.fernet import Fernet


def main() -> None:
    print(Fernet.generate_key().decode("ascii"))


if __name__ == "__main__":
    main()

import argparse

from sqlalchemy import select

from auth.service import hash_password
from db.database import SessionLocal
from db.models import User


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update bootstrap admin user")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--email", default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == args.username))
        if user:
            user.email = args.email
            user.hashed_password = hash_password(args.password)
            user.role = "admin"
            user.is_active = True
            db.add(user)
            db.commit()
            print(f"Updated admin user: {user.username}")
            return

        user = User(
            username=args.username,
            email=args.email,
            hashed_password=hash_password(args.password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created admin user: {user.username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

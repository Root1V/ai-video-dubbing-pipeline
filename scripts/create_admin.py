#!/usr/bin/env python3
"""Bootstrap del primer usuario admin del dashboard web (no hay auto-registro).

Uso:
    python scripts/create_admin.py --email admin@example.com --password secret123 --name "Admin"

Crea las tablas si no existen (Base.metadata.create_all) -- bootstrap simple
para M1; las migraciones de Alembic siguen siendo el camino real para
despliegues (ver alembic/).
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from video_translator.web.db.base import Base
from video_translator.web.db.models import User, UserRole
from video_translator.web.db.session import engine
from video_translator.web.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un usuario admin del dashboard web.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        existing = session.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if existing is not None:
            print(f"Error: ya existe un usuario con email '{args.email}'.", file=sys.stderr)
            raise SystemExit(1)

        user = User(
            email=args.email,
            hashed_password=hash_password(args.password),
            name=args.name,
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        session.commit()

    print(f"Usuario admin creado: {args.email}")


if __name__ == "__main__":
    main()

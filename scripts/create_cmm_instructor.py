"""Da de alta un instructor en la base de datos del Sistema CMM.

Herramienta operativa del Zajuna Monitor mientras el equipo ADSO construye
su módulo de administración (M2). Crea el usuario con rol `instructor`
directamente en la tabla `users` del Postgres del CMM, con hash bcrypt
compatible con su backend (passlib/bcrypt, $2b$).

Uso:
    python scripts/create_cmm_instructor.py "Nombre Completo" correo@sena.edu.co [contraseña]

- Si no se pasa contraseña, se genera una temporal y se imprime.
- Requiere: pip install psycopg[binary] bcrypt
- Config de conexión vía env vars CMM_PG_* (defaults del docker-compose CMM).
"""

import os
import secrets
import string
import sys

import bcrypt
import psycopg

PG_HOST = os.environ.get("CMM_PG_HOST", "localhost")
PG_PORT = int(os.environ.get("CMM_PG_PORT", "5432"))
PG_USER = os.environ.get("CMM_PG_USER", "postgres")
PG_PASSWORD = os.environ.get("CMM_PG_PASSWORD", "postgres")
PG_DB = os.environ.get("CMM_PG_DB", "sena_cmm")


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    full_name = sys.argv[1]
    email = sys.argv[2].strip().lower()
    password = sys.argv[3] if len(sys.argv) > 3 else generate_password()

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    conn_str = (
        f"host={PG_HOST} port={PG_PORT} user={PG_USER} "
        f"password={PG_PASSWORD} dbname={PG_DB}"
    )
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, role FROM users WHERE email = %s", (email,))
            existing = cur.fetchone()
            if existing:
                print(f"Ya existe un usuario con ese email (id={existing[0]}, rol={existing[1]}).")
                sys.exit(1)

            cur.execute(
                """
                INSERT INTO users (full_name, email, hashed_password, role, is_active, email_verified)
                VALUES (%s, %s, %s, 'instructor', TRUE, TRUE)
                RETURNING id
                """,
                (full_name, email, hashed),
            )
            new_id = cur.fetchone()[0]
        conn.commit()

    print(f"Instructor creado (id={new_id})")
    print(f"  Email:      {email}")
    print(f"  Contraseña: {password}")
    print("Compártela por un canal seguro; el instructor puede cambiarla con el enlace mágico del login.")


if __name__ == "__main__":
    main()

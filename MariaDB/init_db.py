from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = ROOT_DIR / "schema.sql"
DEFAULT_DB_NAME = os.getenv("MARIADB_DATABASE", "weather_viewer")
DEFAULT_HOST = os.getenv("MARIADB_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("MARIADB_PORT", "3306"))
DEFAULT_USER = os.getenv("MARIADB_USER", "root")
DEFAULT_PASSWORD = os.getenv("MARIADB_PASSWORD", "")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Create MariaDB database and provider tables.")
	parser.add_argument("--host", default=DEFAULT_HOST, help="MariaDB host")
	parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="MariaDB port")
	parser.add_argument("--user", default=DEFAULT_USER, help="MariaDB username")
	parser.add_argument("--password", default=DEFAULT_PASSWORD, help="MariaDB password")
	parser.add_argument("--database", default=DEFAULT_DB_NAME, help="Database name to create/use")
	parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="Path to schema.sql")
	return parser.parse_args()


def load_sql_statements(schema_path: Path, database_name: str) -> list[str]:
	raw_sql = schema_path.read_text(encoding="utf-8")
	raw_sql = raw_sql.replace("__DB_NAME__", database_name)

	cleaned_lines: list[str] = []
	for line in raw_sql.splitlines():
		stripped = line.strip()
		if stripped.startswith("--"):
			continue
		cleaned_lines.append(line)

	cleaned_sql = "\n".join(cleaned_lines)
	return [statement.strip() for statement in cleaned_sql.split(";") if statement.strip()]


def execute_schema(
	host: str,
	port: int,
	user: str,
	password: str,
	database_name: str,
	schema_path: Path,
) -> list[str]:
	import pymysql

	statements = load_sql_statements(schema_path, database_name)
	connection = pymysql.connect(
		host=host,
		port=port,
		user=user,
		password=password,
		charset="utf8mb4",
		autocommit=True,
	)
	try:
		with connection.cursor() as cursor:
			for statement in statements:
				cursor.execute(statement)
			cursor.execute(f"USE `{database_name}`")
			cursor.execute("SHOW TABLES")
			tables = [row[0] for row in cursor.fetchall()]
	finally:
		connection.close()

	return tables


def format_table_list(tables: Iterable[str]) -> str:
	return "\n".join(f" - {table}" for table in tables)


def main() -> int:
	args = parse_args()
	schema_path = Path(args.schema).resolve()

	if not schema_path.exists():
		raise FileNotFoundError(f"Schema file not found: {schema_path}")

	tables = execute_schema(
		host=args.host,
		port=args.port,
		user=args.user,
		password=args.password,
		database_name=args.database,
		schema_path=schema_path,
	)

	print(f"Database '{args.database}' is ready.")
	print("Available tables:")
	print(format_table_list(tables))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())


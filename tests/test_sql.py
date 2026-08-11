import unittest
from pathlib import Path

import sqlglot


class BigQuerySqlTest(unittest.TestCase):
    def test_all_sql_files_parse_as_bigquery(self):
        sql_files = sorted(Path("projects").rglob("*.sql"))
        self.assertGreaterEqual(len(sql_files), 5)

        for sql_file in sql_files:
            with self.subTest(sql_file=str(sql_file)):
                statements = sqlglot.parse(
                    sql_file.read_text(encoding="utf-8"),
                    read="bigquery",
                )
                self.assertGreaterEqual(len(statements), 1)


if __name__ == "__main__":
    unittest.main()

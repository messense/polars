import os
from pathlib import Path

import pytest

import polars as pl


# TODO: Do not rely on I/O for these tests
@pytest.fixture()
def foods_ipc_path() -> str:
    return str(Path(os.path.dirname(__file__)) / "io" / "files" / "foods1.ipc")


def test_sql_groupby(foods_ipc_path: Path) -> None:
    c = pl.SQLContext()

    lf = pl.scan_ipc(foods_ipc_path)
    c.register("foods", lf)

    out = c.query(
        """
        SELECT
            category,
            count(category) as n,
            max(calories),
            min(fats_g)
        FROM foods
        GROUP BY category
        HAVING n > 5
        ORDER BY n, category DESC
        """
    )
    assert out.to_dict(False) == {
        "category": ["vegetables", "fruit", "seafood"],
        "n": [7, 7, 8],
        "calories": [45, 130, 200],
        "fats_g": [0.0, 0.0, 1.5],
    }

    lf = pl.LazyFrame(
        {
            "group": ["a", "b", "c", "c", "b"],
            "attr": ["x", "y", "x", "y", "y"],
        }
    )
    c.register("test", lf)
    out = c.query(
        """
        SELECT
            group,
            COUNT(DISTINCT attr) AS n_dist_attr
        FROM test
        GROUP BY group
        HAVING n_dist_attr > 1
        """
    )
    assert out.to_dict(False) == {"group": ["c"], "n_dist_attr": [2]}


def test_sql_join(foods_ipc_path: Path) -> None:
    lf = pl.scan_ipc(foods_ipc_path)

    c = pl.SQLContext()
    c.register_many(foods1=lf, foods2=lf)
    out = c.query(
        """
        SELECT * FROM
        foods1 INNER JOIN foods2 ON foods1.category = foods2.category
        LIMIT 2
        """
    )
    assert out.to_dict(False) == {
        "category": ["vegetables", "vegetables"],
        "calories": [45, 20],
        "fats_g": [0.5, 0.0],
        "sugars_g": [2, 2],
        "calories_right": [45, 45],
        "fats_g_right": [0.5, 0.5],
        "sugars_g_right": [2, 2],
    }


def test_sql_is_between(foods_ipc_path: Path) -> None:
    c = pl.SQLContext()

    lf = pl.scan_ipc(foods_ipc_path)
    c.register("foods1", lf)

    out = c.query(
        """
        SELECT * FROM foods1
        WHERE foods1.calories BETWEEN 20 AND 31
        LIMIT 4
        """
    )

    assert out.to_dict(False) == {
        "category": ["fruit", "vegetables", "fruit", "vegetables"],
        "calories": [30, 25, 30, 22],
        "fats_g": [0.0, 0.0, 0.0, 0.0],
        "sugars_g": [5, 2, 3, 3],
    }

    out = c.query(
        """
        SELECT * FROM foods1
        WHERE calories NOT BETWEEN 20 AND 31
        LIMIT 4
        """
    )

    assert out.to_dict(False) == {
        "category": ["vegetables", "seafood", "meat", "fruit"],
        "calories": [45, 150, 100, 60],
        "fats_g": [0.5, 5.0, 5.0, 0.0],
        "sugars_g": [2, 0, 0, 11],
    }


def test_sql_trim(foods_ipc_path: Path) -> None:
    c = pl.SQLContext()

    lf = pl.scan_ipc(foods_ipc_path)
    c.register("foods1", lf)

    out = c.query(
        """
        SELECT TRIM(LEADING 'v' FROM category) FROM foods1
        LIMIT 2
        """
    )
    assert out.to_dict(False) == {"category": ["egetables", "seafood"]}

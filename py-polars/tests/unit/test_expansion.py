from typing import Any

import pytest

import polars as pl
from polars import NUMERIC_DTYPES
from polars.testing import assert_frame_equal


def test_regex_exclude() -> None:
    df = pl.DataFrame({f"col_{i}": [i] for i in range(5)})

    assert df.select(pl.col("^col_.*$").exclude("col_0")).columns == [
        "col_1",
        "col_2",
        "col_3",
        "col_4",
    ]


def test_regex_in_filter() -> None:
    df = pl.DataFrame(
        {
            "nrs": [1, 2, 3, None, 5],
            "names": ["foo", "ham", "spam", "egg", None],
            "flt": [1.0, None, 3.0, 1.0, None],
        }
    )

    res = df.filter(
        pl.fold(
            acc=False, function=lambda acc, s: acc | s, exprs=(pl.col("^nrs|flt*$") < 3)
        )
    ).row(0)
    expected = (1, "foo", 1.0)
    assert res == expected


def test_regex_selection() -> None:
    ldf = pl.LazyFrame(
        {
            "foo": [1],
            "fooey": [1],
            "foobar": [1],
            "bar": [1],
        }
    )
    assert ldf.select([pl.col("^foo.*$")]).columns == ["foo", "fooey", "foobar"]


def test_exclude_selection() -> None:
    ldf = pl.LazyFrame({"a": [1], "b": [1], "c": [True]})

    assert ldf.select([pl.exclude("a")]).columns == ["b", "c"]
    assert ldf.select(pl.all().exclude(pl.Boolean)).columns == ["a", "b"]
    assert ldf.select(pl.all().exclude([pl.Boolean])).columns == ["a", "b"]
    assert ldf.select(pl.all().exclude(NUMERIC_DTYPES)).columns == ["c"]


def test_struct_name_resolving_15430() -> None:
    q = pl.LazyFrame([{"a": {"b": "c"}}])
    a = (
        q.with_columns(pl.col("a").struct.field("b"))
        .drop("a")
        .collect(projection_pushdown=True)
    )

    b = (
        q.with_columns(pl.col("a").struct[0])
        .drop("a")
        .collect(projection_pushdown=True)
    )

    assert a["b"].item() == "c"
    assert b["b"].item() == "c"
    assert a.columns == ["b"]
    assert b.columns == ["b"]


def test_exclude_keys_in_aggregation_16170() -> None:
    df = pl.DataFrame({"A": [4, 4, 3], "B": [1, 2, 3], "C": [5, 6, 7]})

    # wildcard excludes aggregation column
    assert df.lazy().group_by("A").agg(pl.all().name.prefix("agg_")).columns == [
        "A",
        "agg_B",
        "agg_C",
    ]

    # specifically named columns are not excluded
    assert df.lazy().group_by("A").agg(
        pl.col("B", "C").name.prefix("agg_")
    ).columns == ["A", "agg_B", "agg_C"]

    assert df.lazy().group_by("A").agg(
        pl.col("A", "C").name.prefix("agg_")
    ).columns == ["A", "agg_A", "agg_C"]


@pytest.mark.parametrize(
    "field",
    [
        ["aaa", "ccc"],
        [["aaa", "ccc"]],
        [["aaa"], "ccc"],
        [["^aa.+|cc.+$"]],
    ],
)
def test_struct_field_expand(field: Any) -> None:
    df = pl.DataFrame(
        {
            "aaa": [1, 2],
            "bbb": ["ab", "cd"],
            "ccc": [True, None],
            "ddd": [[1, 2], [3]],
        }
    )
    struct_df = df.select(pl.struct(["aaa", "bbb", "ccc", "ddd"]).alias("struct_col"))
    res_df = struct_df.select(pl.col("struct_col").struct.field(*field))
    assert_frame_equal(res_df, df.select("aaa", "ccc"))


def test_struct_field_expand_star() -> None:
    df = pl.DataFrame(
        {
            "aaa": [1, 2],
            "bbb": ["ab", "cd"],
            "ccc": [True, None],
            "ddd": [[1, 2], [3]],
        }
    )
    struct_df = df.select(pl.struct(["aaa", "bbb", "ccc", "ddd"]).alias("struct_col"))
    assert_frame_equal(struct_df.select(pl.col("struct_col").struct.field("*")), df)


def test_struct_field_expand_rewrite() -> None:
    df = pl.DataFrame({"A": [1], "B": [2]})
    assert df.select(
        pl.struct(["A", "B"]).struct.field("*").name.prefix("foo_")
    ).to_dict(as_series=False) == {"foo_A": [1], "foo_B": [2]}


def test_struct_field_expansion_16410() -> None:
    q = pl.LazyFrame({"coords": [{"x": 4, "y": 4}]})

    assert q.with_columns(
        pl.col("coords").struct.with_fields(pl.field("x").sqrt()).struct.field("*")
    ).collect().to_dict(as_series=False) == {
        "coords": [{"x": 4, "y": 4}],
        "x": [2.0],
        "y": [4],
    }

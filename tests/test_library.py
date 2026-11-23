from research_engine import library


# ---- filters -------------------------------------------------------------------------------


def ids(df):
    return list(df["arxiv_id"])


def test_no_filters_keeps_everything(library_df):
    assert len(library.apply_filters(library_df)) == 3


def test_filter_by_category(library_df):
    result = library.apply_filters(library_df, categories=["stat.ME", "q-fin.TR"])
    assert set(ids(result)) == {"2301.00002", "2302.00003"}


def test_filter_by_year_range_is_inclusive(library_df):
    assert ids(library.apply_filters(library_df, year_range=(2021, 2021))) == ["2101.00001"]
    assert len(library.apply_filters(library_df, year_range=(2021, 2023))) == 3


def test_filter_by_author_is_a_case_insensitive_substring(library_df):
    assert set(ids(library.apply_filters(library_df, author="smith"))) == {"2101.00001", "2302.00003"}
    assert ids(library.apply_filters(library_df, author="  CAROL ")) == ["2301.00002"]


def test_filters_combine(library_df):
    result = library.apply_filters(library_df, categories=["stat.ME"], year_range=(2023, 2023), author="alice")
    assert ids(result) == ["2302.00003"]


def test_filters_can_leave_nothing(library_df):
    assert library.apply_filters(library_df, categories=["math.PR"]).empty


# ---- search --------------------------------------------------------------------------------


def test_search_ranks_the_obvious_paper_first_and_drops_non_matches(library_df):
    assert ids(library.search(library_df, "volatility forecasting")) == ["2101.00001"]
    assert ids(library.search(library_df, "shrinkage covariance"))[0] == "2302.00003"


def test_search_matches_record_text_not_just_the_title(library_df):
    # "Ledoit-Wolf" appears only in the methods list of the shrinkage paper.
    assert ids(library.search(library_df, "ledoit")) == ["2302.00003"]


def test_search_with_no_match_returns_nothing(library_df):
    assert library.search(library_df, "zebra").empty


def test_empty_query_returns_all_newest_first(library_df):
    assert ids(library.search(library_df, "  ")) == ["2302.00003", "2301.00002", "2101.00001"]


def test_search_on_an_empty_library(library_df):
    assert library.search(library_df.iloc[0:0], "volatility").empty


def test_search_after_filtering(library_df):
    filtered = library.apply_filters(library_df, categories=["q-fin.TR"])
    assert library.search(filtered, "volatility").empty  # the volatility paper was filtered out


# ---- CSV -----------------------------------------------------------------------------------


def test_csv_frame_is_flat_text(library_df):
    frame = library.to_csv_frame(library_df)
    assert list(frame.columns) == library.CSV_COLUMNS
    assert len(frame) == 3
    first = frame[frame["arxiv_id"] == "2101.00001"].iloc[0]
    assert first["authors"] == "Alice Smith; Bob Jones"
    assert first["published"] == "2021-05-01"
    assert first["key_concepts"] == "realised volatility: Volatility measured from intraday returns."
    assert first["keywords"] == "volatility; har"
    # every cell is plain text or a number, nothing that would print as a Python list or object
    assert not frame.map(lambda cell: isinstance(cell, (list, dict))).any().any()


def test_csv_text_round_trips_through_pandas(library_df):
    import io

    import pandas as pd

    text = library.to_csv_frame(library_df).to_csv(index=False)
    assert len(pd.read_csv(io.StringIO(text))) == 3


def test_csv_frame_of_an_empty_library_keeps_the_columns(library_df):
    frame = library.to_csv_frame(library_df.iloc[0:0])
    assert frame.empty and list(frame.columns) == library.CSV_COLUMNS

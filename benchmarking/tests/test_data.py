import data


def test_extract_informal_and_lean_filters_missing_values():
    dataset = [
        {"informal_description": "desc 1", "type": "type 1"},
        {"informal_description": "", "type": "type 2"},
        {"informal_description": "desc 3", "type": None},
        {"informal_description": "desc 4", "type": "type 4"},
    ]

    extracted = data.extract_informal_and_lean_from_hf_dataset(
        dataset,
        informal_key="informal_description",
        lean_key="type",
    )

    assert extracted == [
        {"informal": "desc 1", "lean": "type 1", "row_index": 0},
        {"informal": "desc 4", "lean": "type 4", "row_index": 3},
    ]

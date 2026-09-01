from breakdown_agent.chunking import chunk_script

_TWO_SCENES = """\
INT. FERRY - NIGHT

Dana stares at the water.

EXT. DOCK - NIGHT

The ferry approaches the dock.
"""


def test_chunks_one_scene_per_heading():
    chunks = chunk_script(_TWO_SCENES)
    assert len(chunks) == 2
    assert chunks[0].startswith("INT. FERRY - NIGHT")
    assert chunks[1].startswith("EXT. DOCK - NIGHT")


def test_never_splits_a_scene_mid_scene():
    chunks = chunk_script(_TWO_SCENES)
    assert "Dana stares at the water." in chunks[0]
    assert "EXT. DOCK" not in chunks[0]


def test_script_with_no_recognizable_headings_becomes_one_chunk():
    chunks = chunk_script("Just some prose with no scene headings at all.")
    assert len(chunks) == 1


def test_empty_script_produces_no_chunks():
    assert chunk_script("") == []
    assert chunk_script("   \n\n  ") == []


def test_pathologically_long_scene_is_sub_split_on_paragraph_boundaries():
    long_scene = "INT. FERRY - NIGHT\n\n" + "\n\n".join(f"Paragraph {i}." * 400 for i in range(20))
    chunks = chunk_script(long_scene)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_case_insensitive_and_ext_int_slash_variant():
    text = "int./ext. car - continuous\n\nAction happens."
    chunks = chunk_script(text)
    assert len(chunks) == 1

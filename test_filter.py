
def test_filtering():
    ai_data = {"used_sources": ["file1.pdf", "file2.pdf"]}
    real_sources = [
        {"title": "file1.pdf", "url": "url1"},
        {"title": "file3.pdf", "url": "url3"},
        {"title": "file2.pdf", "url": "url2"}
    ]

    print(f"Before: {real_sources}")

    # Logic from views.py
    llm_selected_files = ai_data.get("used_sources", [])
    if llm_selected_files and isinstance(llm_selected_files, list):
        filtered_sources = []
        selected_set = {s.strip() for s in llm_selected_files}
        for src in real_sources:
            if src['title'] in selected_set:
                filtered_sources.append(src)
        real_sources = filtered_sources
    
    elif "used_sources" in ai_data and not llm_selected_files:
        real_sources = []

    print(f"After: {real_sources}")
    
    assert len(real_sources) == 2
    assert real_sources[0]['title'] == "file1.pdf"
    assert real_sources[1]['title'] == "file2.pdf"
    print("Test Passed")

test_filtering()

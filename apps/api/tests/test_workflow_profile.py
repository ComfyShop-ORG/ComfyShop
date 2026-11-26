def test_description_author_filter_and_favorite_count(authenticated, graph):
    client = authenticated
    workflow = client.post("/api/v1/workflows", json={"name": "简介", "graph": graph}).json()
    assert workflow["description"] == "" and workflow["popularity"] == 0
    described = client.patch(
        f"/api/v1/workflows/{workflow['id']}", json={"description": "  生成自然光人像  "}
    ).json()
    assert described["description"] == "生成自然光人像"
    assert client.put(f"/api/v1/workflows/{workflow['id']}/favorite").status_code == 204
    detail = client.get(f"/api/v1/workflows/{workflow['id']}").json()
    assert (detail["popularity"], detail["runs"]) == (1, 0)

    def mine(author):
        page = client.get("/api/v1/workflows", params={"scope": "mine", "author": author})
        return [item["id"] for item in page.json()["items"]]

    assert mine("owner") == [workflow["id"]] and mine("someone-else") == []
    cleared = client.patch(f"/api/v1/workflows/{workflow['id']}", json={"description": ""})
    assert cleared.json()["description"] == ""


def test_official_categories_are_saved_and_filtered(authenticated, graph):
    client = authenticated
    categories = (
        "image",
        "image_tool",
        "video",
        "video_tool",
        "audio",
        "3d",
        "vector",
        "llm",
        "node_basics",
        "product_ads",
        "character_fashion",
        "brand_design",
    )
    workflow_ids = {}
    for category in categories:
        response = client.post(
            "/api/v1/workflows", json={"name": category, "category": category, "graph": graph}
        )
        assert response.status_code == 201, response.text
        assert response.json()["category"] == category
        workflow_ids[category] = response.json()["id"]

    def filtered(category):
        response = client.get("/api/v1/workflows", params={"scope": "mine", "category": category})
        assert response.status_code == 200, response.text
        return {item["id"] for item in response.json()["items"]}

    for category, workflow_id in workflow_ids.items():
        assert filtered(category) == {workflow_id}
    for path in ("/api/v1/workflows", "/api/v1/works"):
        assert client.get(path, params={"category": "tool"}).status_code == 422
    invalid = {"name": "旧分类", "graph": graph, "category": "tool"}
    assert client.post("/api/v1/workflows", json=invalid).status_code == 422
    assert (
        client.patch(
            f"/api/v1/workflows/{workflow_ids['image']}", json={"category": "tool"}
        ).status_code
        == 422
    )
    revised = client.patch(f"/api/v1/workflows/{workflow_ids['image']}", json={"category": "llm"})
    assert revised.status_code == 200, revised.text
    assert filtered("llm") == {workflow_ids["image"], workflow_ids["llm"]}

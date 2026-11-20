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

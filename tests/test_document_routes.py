from math import ceil

import pytest
from meilisearch_python_async.errors import MeiliSearchApiError


def generate_test_movies(num_movies=50):
    movies = []
    # Each moves is ~ 174 bytes
    for i in range(num_movies):
        movie = {
            "id": i,
            "title": "test",
            "poster": "test",
            "overview": "test",
            "release_date": 1551830399,
            "pk_test": i + 1,
            "genre": "test",
        }
        movies.append(movie)

    return movies


@pytest.mark.asyncio
async def test_get_documents_none(empty_index, test_client):
    uid, _ = empty_index
    response = await test_client.get(f"/documents/{uid}")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
async def test_add_documents(
    primary_key, expected_primary_key, empty_index, small_movies, test_client
):
    uid, index = empty_index
    document = {"uid": uid, "documents": small_movies, "primaryKey": primary_key}
    response = await test_client.post("/documents", json=document)
    assert "updateId" in response.json()
    update = await index.wait_for_pending_update(response.json()["updateId"])
    assert await index.get_primary_key() == expected_primary_key
    assert update.status == "processed"


@pytest.mark.asyncio
@pytest.mark.parametrize("max_payload, expected_batches", [(None, 1), (3500, 2), (2500, 3)])
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("pk_test", "pk_test"), (None, "id")]
)
async def test_add_documents_auto_batch(
    empty_index, max_payload, expected_batches, primary_key, expected_primary_key, test_client
):
    documents = generate_test_movies()

    uid, index = empty_index
    if max_payload:
        document = {
            "uid": uid,
            "documents": documents,
            "maxPayloadSize": max_payload,
            "primaryKey": primary_key,
        }
    else:
        document = {"uid": uid, "documents": documents, "primaryKey": primary_key}

    response = await test_client.post("/documents/auto-batch", json=document)

    assert len(response.json()) == expected_batches

    for r in response.json():
        update = await index.wait_for_pending_update(r["updateId"])
        assert update.status == "processed"

    assert await index.get_primary_key() == expected_primary_key


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("batch_size", [2, 3, 1000])
async def test_add_documents_in_batches(
    primary_key, expected_primary_key, batch_size, empty_index, small_movies, test_client
):
    uid, index = empty_index
    document = {
        "uid": uid,
        "documents": small_movies,
        "batch_size": batch_size,
        "primary_key": primary_key,
    }
    response = await test_client.post("/documents/batches", json=document)
    assert ceil(len(small_movies) / batch_size) == len(response.json())

    for r in response.json():
        update = await index.wait_for_pending_update(r["updateId"])
        assert update.status == "processed"

    assert await index.get_primary_key() == expected_primary_key


@pytest.mark.asyncio
async def test_delete_document(test_client, index_with_documents):
    uid, index = index_with_documents
    response = await test_client.delete(f"/documents/{uid}/500682")
    await index.wait_for_pending_update(response.json()["updateId"])
    with pytest.raises(MeiliSearchApiError):
        await test_client.get(f"/documents/{uid}/500682")


@pytest.mark.asyncio
async def test_delete_documents(test_client, index_with_documents):
    to_delete = ["522681", "450465", "329996"]
    uid, index = index_with_documents
    delete_info = {
        "uid": uid,
        "document_ids": to_delete,
    }
    response = await test_client.post("/documents/delete", json=delete_info)
    await index.wait_for_pending_update(response.json()["updateId"])
    documents = await test_client.get(f"/documents/{uid}")
    ids = [x["id"] for x in documents.json()]
    assert to_delete not in ids


@pytest.mark.asyncio
async def test_delete_all_documents(test_client, index_with_documents):
    uid, index = index_with_documents
    response = await test_client.delete(f"/documents/{uid}")
    await index.wait_for_pending_update(response.json()["updateId"])
    response = await test_client.get(f"/documents/{uid}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_document(test_client, index_with_documents):
    uid, _ = index_with_documents
    response = await test_client.get(f"documents/{uid}/500682")
    assert response.json()["title"] == "The Highwaymen"


@pytest.mark.asyncio
async def test_get_document_nonexistent(test_client, empty_index):
    with pytest.raises(MeiliSearchApiError):
        uid, _ = empty_index
        await test_client.get(f"documents/{uid}/123")


@pytest.mark.asyncio
async def test_get_documents_populated(test_client, index_with_documents):
    uid, _ = index_with_documents
    response = await test_client.get(f"documents/{uid}")
    assert len(response.json()) == 20


@pytest.mark.asyncio
async def test_get_documents_offset_optional_params(test_client, index_with_documents):
    uid, _ = index_with_documents
    response = await test_client.get(f"/documents/{uid}")
    assert len(response.json()) == 20

    response_offset_limit = await test_client.get(
        f"documents/{uid}?limit=3&offset=1&attributes_to_retrieve=title"
    )
    assert len(response_offset_limit.json()) == 3
    assert response_offset_limit.json()[0]["title"] == response.json()[1]["title"]


@pytest.mark.asyncio
async def test_update_documents(test_client, index_with_documents, small_movies):
    uid, index = index_with_documents
    response = await test_client.get(f"documents/{uid}")
    response_docs = response.json()
    response_docs[0]["title"] = "Some title"
    update_body = {"uid": uid, "documents": response_docs}
    update = await test_client.put("/documents", json=update_body)
    await index.wait_for_pending_update(update.json()["updateId"])
    response = await test_client.get(f"/documents/{uid}")
    assert response.json()[0]["title"] == "Some title"
    update_body = {"uid": uid, "documents": small_movies}
    update = await test_client.put("/documents", json=update_body)
    await index.wait_for_pending_update(update.json()["updateId"])
    response = await test_client.get(f"/documents/{uid}")
    assert response.json()[0]["title"] != "Some title"


@pytest.mark.asyncio
async def test_update_documents_with_primary_key(test_client, empty_index, small_movies):
    primary_key = "release_date"
    uid, index = empty_index
    document_info = {"uid": uid, "documents": small_movies, "primaryKey": primary_key}
    update = await test_client.put("/documents", json=document_info)
    await index.wait_for_pending_update(update.json()["updateId"])
    assert await index.get_primary_key() == primary_key


@pytest.mark.asyncio
@pytest.mark.parametrize("max_payload, expected_batches", [(None, 1), (3500, 2), (2500, 3)])
async def test_update_documents_auto_batch(empty_index, max_payload, expected_batches, test_client):
    documents = generate_test_movies()

    uid, index = empty_index
    document = {"uid": uid, "documents": documents}
    response = await test_client.post("/documents", json=document)
    await index.wait_for_pending_update(response.json()["updateId"])

    response = await test_client.get(f"documents/{uid}?limit={len(documents)}")
    response_docs = response.json()
    assert "Some title" != response_docs[0]["title"]

    response_docs[0]["title"] = "Some title"
    if max_payload:
        update_body = {
            "uid": uid,
            "documents": response_docs,
            "maxPayloadSize": max_payload,
        }
    else:
        update_body = {"uid": uid, "documents": response_docs}

    response = await test_client.put("/documents/auto-batch", json=update_body)

    assert len(response.json()) == expected_batches

    for r in response.json():
        update = await index.wait_for_pending_update(r["updateId"])
        assert update.status == "processed"


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_size", [2, 3, 1000])
async def test_update_documents_in_batches(
    batch_size, test_client, index_with_documents, small_movies
):
    uid, index = index_with_documents
    response = await test_client.get(f"documents/{uid}")
    response_docs = response.json()
    response_docs[0]["title"] = "Some title"
    update_body = {"uid": uid, "documents": response_docs}
    update = await test_client.put("/documents", json=update_body)
    await index.wait_for_pending_update(update.json()["updateId"])
    response = await test_client.get(f"/documents/{uid}")
    assert response.json()[0]["title"] == "Some title"
    update_body = {"uid": uid, "batch_size": batch_size, "documents": small_movies}
    updates = await test_client.put("/documents/batches", json=update_body)

    for update in updates.json():
        await index.wait_for_pending_update(update["updateId"])

    response = await test_client.get(f"/documents/{uid}")
    assert response.json()[0]["title"] != "Some title"

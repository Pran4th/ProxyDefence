from fastapi import APIRouter, HTTPException, Query
from backend.api_service.main import app

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/")
async def search_articles(q: str = Query(..., min_length=2)):
    try:
        response = await app.state.es_client.search(
            index="processed_articles",
            body={
                "query": {
                    "multi_match": {
                        "query": q,
                        "fields": ["title", "content", "source"]
                    }
                }
            }
        )

        return {
            "query": q,
            "total_results": response['hits']['total']['value'],
            "results": [hit["_source"] for hit in response['hits']['hits']]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
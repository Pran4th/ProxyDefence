from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/")
async def search_articles(request: Request, q: str = Query(..., min_length=2)):
    try:
        response = await request.app.state.es_client.search(
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

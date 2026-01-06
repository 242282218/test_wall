from fastapi import APIRouter, Depends

from app.quark.deps import get_db
from app.quark.schemas.search import SearchByTmdbIdRequest, SearchByTitleRequest, SearchResponse
from app.quark.services.search_service import SearchService

router = APIRouter(tags=["search"])
service = SearchService()


@router.post("/search/by-tmdb-id", response_model=SearchResponse)
async def search_by_tmdb_id(payload: SearchByTmdbIdRequest, db=Depends(get_db)):
    return await service.search_by_tmdb_id(
        payload.tmdb_id, 
        payload.max_results, 
        db,
        media_type=payload.media_type or "movie"  # 如果不提供则默认 movie，会在服务中自动检测
    )


@router.post("/search/by-title", response_model=SearchResponse)
async def search_by_title(payload: SearchByTitleRequest, db=Depends(get_db)):
    return await service.search_by_title(payload.title, payload.year, payload.max_results, db)


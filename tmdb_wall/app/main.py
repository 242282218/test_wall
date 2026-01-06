import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError

from .config import get_settings
from .tmdb import TmdbClient, adapt_poster, gather_sections

# 夸克搜索模块
from app.quark.api.routes import search, health, media, rename
from app.quark.error_handlers import (
    quark_search_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.quark.utils.exceptions import QuarkSearchException
from app.quark.models.database import Base, engine
from app.quark.models import media as media_model
from app.quark.models import resource as resource_model
from app.quark.models import search_history as search_history_model

settings = get_settings()
logger = logging.getLogger(__name__)
tmdb_client = TmdbClient(
    settings.tmdb_api_key,
    api_base=settings.tmdb_api_base,
    image_base=settings.tmdb_image_base,
    language=settings.default_language,
)
section_keys = ["trending", "popular", "top_rated", "now_playing"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库表
    startup_ok = False
    try:
        Base.metadata.create_all(bind=engine)
        startup_ok = True
        yield
    except Exception:
        if not startup_ok:
            logger.exception("Database initialization failed")
        raise
    finally:
        await tmdb_client.close()


app = FastAPI(title="TMDB 海报墙", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 注册夸克搜索路由
prefix = settings.quark_search_api_prefix
app.include_router(health.router, prefix=prefix, tags=["夸克搜索"])
app.include_router(search.router, prefix=prefix, tags=["夸克搜索"])
app.include_router(media.router, prefix=prefix, tags=["夸克搜索"])
app.include_router(rename.router, prefix=prefix, tags=["夸克搜索"])

# 注册异常处理器
app.add_exception_handler(QuarkSearchException, quark_search_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

@app.get("/health")
async def health_root() -> Dict[str, int]:
    return {"status": "ok", "time": int(time.time())}


def adapt_detail(item: Dict, client: TmdbClient) -> Dict:
    title = item.get("title") or item.get("name") or "未命名"
    date_field = item.get("release_date") or item.get("first_air_date") or ""
    year = date_field.split("-")[0] if date_field else ""
    genres = [g.get("name") for g in item.get("genres", []) if g.get("name")]
    runtime = item.get("runtime") or (item.get("episode_run_time") or [None])[0]
    vote = item.get("vote_average")

    cast_raw = (item.get("credits") or {}).get("cast") or []
    cast = []
    for c in cast_raw[:12]:
        cast.append(
            {
                "id": c.get("id"),
                "name": c.get("name") or "",
                "character": c.get("character") or "",
                "profile_url": client.image_url(c.get("profile_path"), "w300"),
            }
        )

    videos_raw = (item.get("videos") or {}).get("results") or []
    videos = []
    for v in videos_raw:
        if v.get("site") != "YouTube" or not v.get("key"):
            continue
        videos.append(
            {
                "key": v.get("key"),
                "name": v.get("name") or "",
                "type": v.get("type") or "",
                "official": v.get("official") or False,
            }
        )
    videos = videos[:2]

    recommendations = (item.get("recommendations") or {}).get("results") or []
    if not recommendations:
        recommendations = (item.get("similar") or {}).get("results") or []

    return {
        "id": item.get("id"),
        "media_type": item.get("media_type") or ("movie" if "title" in item else "tv"),
        "title": title,
        "year": year,
        "genres": genres,
        "runtime": runtime,
        "vote": vote,
        "tagline": item.get("tagline") or "",
        "overview": item.get("overview") or "",
        "poster_url": client.image_url(item.get("poster_path")),
        "backdrop_url": client.image_url(item.get("backdrop_path")),
        "cast": cast,
        "videos": videos,
        "recommendations": recommendations,
    }


def adapt_person(person: Dict, client: TmdbClient, credits: List[Dict]) -> Dict:
    profile_url = client.image_url(person.get("profile_path"), "w500")
    # 评分/人气/日期排序选择代表作
    def credit_score(c: Dict) -> tuple:
        va = c.get("vote_average") or 0
        pop = c.get("popularity") or 0
        date = c.get("release_date") or c.get("first_air_date") or ""
        return (va, pop, date)

    filtered = []
    for c in credits:
        mt = c.get("media_type") or ("movie" if "title" in c else "tv")
        if mt not in ("movie", "tv") or not c.get("id"):
            continue
        filtered.append(c)

    top_sorted = sorted(filtered, key=credit_score, reverse=True)[:12]
    top_credits = []
    for c in top_sorted:
        adapted = adapt_poster(c, client)
        top_credits.append(adapted)

    # 全部作品分组（按年份倒序）
    all_credits = []
    for c in filtered:
        mt = c.get("media_type") or ("movie" if "title" in c else "tv")
        title = c.get("title") or c.get("name") or "未命名"
        date_field = c.get("release_date") or c.get("first_air_date") or ""
        year = date_field.split("-")[0] if date_field else ""
        role = c.get("character") or c.get("job") or ""
        all_credits.append(
            {
                "id": c.get("id"),
                "media_type": mt,
                "title": title,
                "year": year,
                "role": role,
            }
        )
    all_credits.sort(key=lambda x: x.get("year") or "", reverse=True)

    return {
        "id": person.get("id"),
        "name": person.get("name") or "",
        "known_for": person.get("known_for_department") or "",
        "biography": person.get("biography") or "",
        "birthday": person.get("birthday") or "",
        "place_of_birth": person.get("place_of_birth") or "",
        "profile_url": profile_url,
        "top_credits": top_credits,
        "all_credits": all_credits,
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    try:
        sections_raw = await asyncio.wait_for(gather_sections(tmdb_client), timeout=10)
    except asyncio.TimeoutError:
        sections_raw = {key: [] for key in section_keys}
    except httpx.HTTPError:
        sections_raw = {key: [] for key in section_keys}

    sections = {
        key: [adapt_poster(item, tmdb_client) for item in value if item.get("id")]
        for key, value in sections_raw.items()
    }
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "sections": sections,
            "page_title": "TMDB 海报墙",
        },
    )


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: Optional[str] = "") -> HTMLResponse:
    posters: List[Dict] = []
    if q:
        try:
            results = await tmdb_client.search_multi(q)
        except httpx.HTTPError:
            results = []
        posters = [
            adapt_poster(item, tmdb_client)
            for item in results
            if item.get("id") and (item.get("media_type") in ("movie", "tv"))
        ]
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q or "",
            "posters": posters,
            "page_title": f"搜索：{q}" if q else "搜索",
        },
    )


@app.get("/person/{person_id}", response_class=HTMLResponse)
async def person_detail(request: Request, person_id: int) -> HTMLResponse:
    try:
        data = await tmdb_client.person(person_id)
        # 如果简介/图片为空，再尝试英文兜底
        if not data.get("biography") or not data.get("profile_path"):
            try:
                data_en = await tmdb_client.person(person_id, language_override="en-US")
                data["biography"] = data.get("biography") or data_en.get("biography")
                data["profile_path"] = data.get("profile_path") or data_en.get("profile_path")
                data["combined_credits"] = data.get("combined_credits") or data_en.get("combined_credits")
            except httpx.HTTPError:
                pass
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="TMDB error") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="TMDB unavailable") from exc

    combined = data.get("combined_credits") or {}
    credits_cast = combined.get("cast") or []
    credits_crew = combined.get("crew") or []
    credits = credits_cast + credits_crew
    if not credits and combined:
        credits = credits_cast or credits_crew
    person_data = adapt_person(data, tmdb_client, credits)
    return templates.TemplateResponse(
        "person.html",
        {
            "request": request,
            "person": person_data,
            "page_title": person_data.get("name", ""),
        },
    )


@app.get("/{media_type}/{item_id}", response_class=HTMLResponse)
async def detail(request: Request, media_type: str, item_id: int) -> HTMLResponse:
    if media_type not in ("movie", "tv"):
        raise HTTPException(status_code=404, detail="Unsupported media type")
    try:
        data = await tmdb_client.details(media_type, item_id)
        # 如果本地语言下视频/推荐为空，再尝试英文兜底
        need_fallback = False
        videos_has = (data.get("videos") or {}).get("results")
        rec_has = (data.get("recommendations") or {}).get("results")
        sim_has = (data.get("similar") or {}).get("results")
        if not videos_has or not rec_has:
            need_fallback = True
        if need_fallback:
            try:
                data_en = await tmdb_client.details(media_type, item_id, language_override="en-US")
                if not videos_has:
                    data["videos"] = data_en.get("videos") or {}
                if not rec_has:
                    data["recommendations"] = data_en.get("recommendations") or {}
                if not sim_has:
                    data["similar"] = data_en.get("similar") or {}
            except httpx.HTTPError:
                pass
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="TMDB error") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="TMDB unavailable") from exc

    detail_data = adapt_detail(data, tmdb_client)
    rec_posters = [
        adapt_poster(rec, tmdb_client) for rec in detail_data.get("recommendations", []) if rec.get("id")
    ][:12]
    video_previews = rec_posters[:2]
    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "item": detail_data,
            "recommendations": rec_posters,
            "video_previews": video_previews,
            "page_title": detail_data.get("title", ""),
        },
    )


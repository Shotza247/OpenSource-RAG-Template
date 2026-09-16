"""Local-only collection and approved ingestion endpoints."""

import logging
from contextlib import contextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from faq_agent.config import get_settings
from faq_agent.ingestion.service import MAX_BYTES, Library

router = APIRouter(tags=["Document library"])
logger = logging.getLogger("faq_agent")


@contextmanager
def redact_errors():
    try:
        yield
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - redact upstream exceptions at the API boundary
        request_id = str(uuid4())
        logger.warning("library_failed id=%s error_type=%s", request_id, type(exc).__name__)
        raise HTTPException(
            503, {"message": "Document library operation failed.", "request_id": request_id}
        ) from None


def get_library():
    with redact_errors():
        library = Library(get_settings())
        try:
            yield library
        finally:
            library.close()


LibraryDependency = Annotated[Library, Depends(get_library)]


class CollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,47}$")


class CommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preview_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    approved: bool


@router.get("/collections")
def collections(library: LibraryDependency):
    return library.list_collections()


@router.post("/collections", status_code=201)
def create_collection(body: CollectionRequest, library: LibraryDependency):
    return library.create(body.name)


@router.get("/collections/{collection_id}/documents")
def documents(collection_id: str, library: LibraryDependency):
    return library.documents(collection_id)


@router.post("/collections/{collection_id}/uploads/preview")
def preview(collection_id: str, file: UploadFile, library: LibraryDependency):
    """Extract and chunk locally. Does not call the embedding or chat model."""
    try:
        return library.preview(
            collection_id, file.filename or "upload", file.file.read(MAX_BYTES + 1)
        )
    finally:
        file.file.close()


@router.post("/collections/{collection_id}/documents")
def commit(collection_id: str, body: CommitRequest, library: LibraryDependency):
    """Embed the approved preview and store it; repeated submissions do not duplicate points."""
    return library.commit(collection_id, body.preview_id, body.approved)

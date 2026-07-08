from typing import Any

from fastapi import HTTPException

from backend.api.cases.repository import CaseRepository


class CaseService:
    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def ensure_access(self, case: dict, current_user: dict) -> None:
        if current_user.get("role") == "admin":
            return
        if case.get("owner_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Case access denied")

    async def create_case(self, title: str, description: str | None, owner_id: int | None, priority: str) -> dict[str, Any]:
        return await self.repository.create_case(title, description, owner_id, priority)

    async def get_case(self, case_id: int) -> dict[str, Any] | None:
        return await self.repository.get_case(case_id)

    async def list_cases(self, owner_id: int | None, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.list_cases(owner_id, status, limit, offset)

    async def add_case_item(self, case_id: int, item_type: str, item_id: int) -> dict[str, Any]:
        return await self.repository.add_case_item(case_id, item_type, item_id)

    async def remove_case_item(self, case_id: int, item_type: str, item_id: int) -> dict[str, Any]:
        return await self.repository.remove_case_item(case_id, item_type, item_id)

    async def add_case_note(self, case_id: int, note_text: str, created_by: int | None) -> dict[str, Any]:
        return await self.repository.add_case_note(case_id, note_text, created_by)

    async def list_case_notes(self, case_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.list_case_notes(case_id, limit, offset)

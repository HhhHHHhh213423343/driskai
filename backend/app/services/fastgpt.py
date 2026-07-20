from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class FastGPTService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_dataset_payload(
        self,
        *,
        company_name: str,
        system_prompt: str,
        risk_digest: list[dict[str, str]],
    ) -> dict:
        return {
            "dataset_id": self.settings.fastgpt_dataset_id,
            "document_id": company_name,
            "title": f"{company_name} 实时风险画像",
            "metadata": {
                "company_name": company_name,
                "source": "postgresql:risk_events",
                "risk_event_count": len(risk_digest),
            },
            "content": system_prompt,
            "blocks": risk_digest,
        }

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.fastgpt_api_key:
            headers["Authorization"] = f"Bearer {self.settings.fastgpt_api_key}"
        return headers

    def _build_url(self, path: str) -> str:
        if not self.settings.fastgpt_base_url:
            raise ValueError("FASTGPT_BASE_URL 未配置。")
        if not path:
            raise ValueError("FastGPT 接口路径未配置。")
        return f"{self.settings.fastgpt_base_url}{path}"

    @staticmethod
    def _extract_chat_answer(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        raise ValueError("FastGPT 没有返回可用内容。")

    async def create_chat_completion(
        self,
        *,
        company_name: str,
        question: str,
        system_prompt: str,
        risk_digest: list[dict[str, str]],
    ) -> str:
        url = self._build_url(self.settings.fastgpt_chat_path)
        payload = {
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or "请结合企业风险、财务与舆情上下文进行回答。",
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
            "variables": {
                "companyName": company_name,
                "riskDigest": risk_digest,
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._build_headers(),
            )
            response.raise_for_status()
            data = response.json()

        return self._extract_chat_answer(data)

    async def sync_dataset_payload(self, payload: dict) -> tuple[str, int | None]:
        if not self.settings.fastgpt_base_url or not self.settings.fastgpt_dataset_upsert_path:
            return "payload_only", None

        url = self._build_url(self.settings.fastgpt_dataset_upsert_path)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._build_headers(),
            )
            response.raise_for_status()
        return "synced", response.status_code

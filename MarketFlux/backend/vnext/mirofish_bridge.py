from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


class MiroFishBridgeClient:
    """External-service bridge for MiroFish scenario simulations.

    We keep this as a service boundary instead of vendoring MiroFish into the
    MarketFlux codebase so the existing product remains stable and licensing
    responsibilities stay explicit.
    """

    def __init__(self, base_url: Optional[str] = None, bearer_token: Optional[str] = None):
        self.base_url = (base_url or os.getenv("MIROFISH_BASE_URL") or "").rstrip("/")
        self.bearer_token = bearer_token or os.getenv("MIROFISH_BEARER_TOKEN") or ""

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    async def _post_json(self, path: str, payload: Dict[str, Any], timeout: float = 90.0) -> Dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "status": "bridge_unavailable",
                "message": "MiroFish bridge is not configured yet.",
            }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
            data["configured"] = True
            return data

    async def health(self) -> Dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "status": "bridge_unavailable",
                "message": "Set MIROFISH_BASE_URL to enable the scenario lab.",
            }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.base_url}/health", headers=self._headers())
            response.raise_for_status()
            data = response.json()
            data["configured"] = True
            return data

    async def generate_ontology(
        self,
        *,
        simulation_requirement: str,
        project_name: str,
        seed_materials: List[str],
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "status": "bridge_unavailable",
                "message": "MiroFish bridge is not configured yet.",
            }

        content = "\n\n".join(chunk.strip() for chunk in seed_materials if chunk and chunk.strip())
        if not content:
            return {
                "configured": True,
                "success": False,
                "error": "At least one seed material block is required.",
            }

        multipart_files = [
            (
                "files",
                ("marketflux_seed.md", content.encode("utf-8"), "text/markdown"),
            )
        ]
        form_data = {
            "simulation_requirement": simulation_requirement,
            "project_name": project_name,
            "additional_context": additional_context or "",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/graph/ontology/generate",
                headers=self._headers(),
                data=form_data,
                files=multipart_files,
            )
            response.raise_for_status()
            data = response.json()
            data["configured"] = True
            return data

    async def build_graph(
        self,
        *,
        project_id: str,
        graph_name: Optional[str] = None,
        chunk_size: int = 700,
        chunk_overlap: int = 80,
        force: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "project_id": project_id,
            "graph_name": graph_name or f"{project_id}-graph",
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "force": force,
        }
        return await self._post_json("/api/graph/build", payload)

    async def create_simulation(
        self,
        *,
        project_id: str,
        graph_id: Optional[str] = None,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ) -> Dict[str, Any]:
        payload = {
            "project_id": project_id,
            "graph_id": graph_id,
            "enable_twitter": enable_twitter,
            "enable_reddit": enable_reddit,
        }
        return await self._post_json("/api/simulation/create", payload)

    async def prepare_simulation(
        self,
        *,
        simulation_id: str,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "simulation_id": simulation_id,
            "force_regenerate": force_regenerate,
        }
        return await self._post_json("/api/simulation/prepare", payload, timeout=120.0)

    async def generate_report(
        self,
        *,
        simulation_id: str,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "simulation_id": simulation_id,
            "force_regenerate": force_regenerate,
        }
        return await self._post_json("/api/report/generate", payload, timeout=120.0)

    async def get_report_status(
        self,
        *,
        simulation_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {}
        if simulation_id:
            payload["simulation_id"] = simulation_id
        if task_id:
            payload["task_id"] = task_id
        return await self._post_json("/api/report/generate/status", payload)

    async def create_financial_scenario(
        self,
        *,
        project_name: str,
        simulation_requirement: str,
        seed_materials: List[str],
        additional_context: Optional[str] = None,
        enable_twitter: bool = False,
        enable_reddit: bool = False,
    ) -> Dict[str, Any]:
        ontology = await self.generate_ontology(
            simulation_requirement=simulation_requirement,
            project_name=project_name,
            seed_materials=seed_materials,
            additional_context=additional_context,
        )
        if not ontology.get("success"):
            return {
                "configured": self.configured,
                "stage": "ontology_failed",
                "ontology": ontology,
            }

        project_data = (ontology.get("data") or {})
        project_id = project_data.get("project_id")
        if not project_id:
            return {
                "configured": self.configured,
                "stage": "ontology_failed",
                "ontology": ontology,
                "message": "MiroFish did not return a project_id.",
            }

        graph = await self.build_graph(
            project_id=project_id,
            graph_name=f"{project_name} scenario graph",
        )
        simulation = await self.create_simulation(
            project_id=project_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
        )

        simulation_id = ((simulation.get("data") or {}).get("simulation_id"))
        preparation = (
            await self.prepare_simulation(simulation_id=simulation_id)
            if simulation_id
            else {"success": False, "error": "simulation_id missing from create_simulation response"}
        )

        return {
            "configured": True,
            "stage": "simulation_preparing",
            "project_id": project_id,
            "ontology": ontology,
            "graph": graph,
            "simulation": simulation,
            "preparation": preparation,
            "next_step": "Poll preparation/report status and trigger report generation once the scenario is ready.",
        }

#  coding=utf-8
#  Copyright 2021-present, the Recognai S.L. team.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import itertools
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import StreamingResponse

from argilla.server.apis.v0.handlers import (
    metrics,
    token_classification_dataset_settings,
)
from argilla.server.apis.v0.models.commons.model import BulkResponse
from argilla.server.apis.v0.models.commons.params import (
    CommonTaskHandlerDependencies,
    RequestPagination,
)
from argilla.server.apis.v0.models.token_classification import (
    TokenClassificationAggregations,
    TokenClassificationBulkRequest,
    TokenClassificationQuery,
    TokenClassificationRecord,
    TokenClassificationSearchRequest,
    TokenClassificationSearchResults,
)
from argilla.server.apis.v0.validators.token_classification import DatasetValidator
from argilla.server.commons.config import TasksFactory
from argilla.server.commons.models import TaskType
from argilla.server.errors import EntityNotFoundError
from argilla.server.helpers import takeuntil
from argilla.server.responses import StreamingResponseWithErrorHandling
from argilla.server.schemas.datasets import CreateDatasetRequest
from argilla.server.security import auth
from argilla.server.security.model import User
from argilla.server.services.datasets import DatasetsService, ServiceBaseDataset
from argilla.server.services.tasks.token_classification import (
    TokenClassificationService,
)
from argilla.server.services.tasks.token_classification.metrics import (
    TokenClassificationMetrics,
)
from argilla.server.services.tasks.token_classification.model import (
    ServiceTokenClassificationQuery,
    ServiceTokenClassificationRecord,
)


def configure_router():
    task_type = TaskType.token_classification
    base_endpoint = f"/{{name}}/{task_type}"
    new_base_endpoint = f"/{task_type}/{{name}}"

    TasksFactory.register_task(
        task_type=task_type,
        query_request=TokenClassificationQuery,
        record_class=ServiceTokenClassificationRecord,
        metrics=TokenClassificationMetrics,
    )

    router = APIRouter(tags=[task_type], prefix="/datasets")

    @router.post(
        path=f"{base_endpoint}:bulk",
        operation_id="bulk_records",
        response_model=BulkResponse,
        response_model_exclude_none=True,
    )
    async def bulk_records(
        name: str,
        bulk: TokenClassificationBulkRequest,
        common_params: CommonTaskHandlerDependencies = Depends(),
        service: TokenClassificationService = Depends(TokenClassificationService.get_instance),
        datasets: DatasetsService = Depends(DatasetsService.get_instance),
        validator: DatasetValidator = Depends(DatasetValidator.get_instance),
        current_user: User = Security(auth.get_user, scopes=[]),
    ) -> BulkResponse:
        task = task_type
        workspace = current_user.check_workspace(common_params.workspace)
        try:
            dataset = datasets.find_by_name(
                current_user,
                name=name,
                task=task,
                workspace=workspace,
            )
            datasets.update(
                user=current_user,
                dataset=dataset,
                tags=bulk.tags,
                metadata=bulk.metadata,
            )
        except EntityNotFoundError:
            dataset = CreateDatasetRequest(name=name, workspace=workspace, task=task, **bulk.dict())
            dataset = datasets.create_dataset(user=current_user, dataset=dataset)

        records = [ServiceTokenClassificationRecord.parse_obj(r) for r in bulk.records]
        # TODO(@frascuchon): validator can be applied in service layer
        await validator.validate_dataset_records(
            user=current_user,
            dataset=dataset,
            records=records,
        )

        result = await service.add_records(
            dataset=dataset,
            records=records,
        )
        return BulkResponse(
            dataset=name,
            processed=result.processed,
            failed=result.failed,
        )

    @router.post(
        path=f"{base_endpoint}:search",
        response_model=TokenClassificationSearchResults,
        response_model_exclude_none=True,
        operation_id="search_records",
    )
    def search_records(
        name: str,
        search: TokenClassificationSearchRequest = None,
        common_params: CommonTaskHandlerDependencies = Depends(),
        include_metrics: bool = Query(
            default=False,
            description="If enabled, return related record metrics",
        ),
        pagination: RequestPagination = Depends(),
        service: TokenClassificationService = Depends(TokenClassificationService.get_instance),
        datasets: DatasetsService = Depends(DatasetsService.get_instance),
        current_user: User = Security(auth.get_user, scopes=[]),
    ) -> TokenClassificationSearchResults:
        search = search or TokenClassificationSearchRequest()
        query = search.query or TokenClassificationQuery()

        dataset = datasets.find_by_name(
            user=current_user,
            name=name,
            task=task_type,
            workspace=common_params.workspace,
        )
        results = service.search(
            dataset=dataset,
            query=ServiceTokenClassificationQuery.parse_obj(query),
            sort_by=search.sort,
            record_from=pagination.from_,
            size=pagination.limit,
            exclude_metrics=not include_metrics,
        )

        return TokenClassificationSearchResults(
            total=results.total,
            records=[TokenClassificationRecord.parse_obj(r) for r in results.records],
            aggregations=TokenClassificationAggregations.parse_obj(results.metrics) if results.metrics else None,
        )

    def scan_data_response(
        data_stream: Iterable[TokenClassificationRecord],
        chunk_size: int = 1000,
        limit: Optional[int] = None,
    ) -> StreamingResponseWithErrorHandling:
        """Generate an textual stream data response for a dataset scan"""

        async def stream_generator(stream):
            """Converts dataset scan into a text stream"""

            def grouper(n, iterable, fillvalue=None):
                args = [iter(iterable)] * n
                return itertools.zip_longest(fillvalue=fillvalue, *args)

            if limit:
                stream = takeuntil(stream, limit=limit)

            for batch in grouper(
                n=chunk_size,
                iterable=stream,
            ):
                filtered_records = filter(lambda r: r is not None, batch)
                yield "\n".join(
                    map(
                        lambda r: r.json(by_alias=True, exclude_none=True),
                        filtered_records,
                    )
                ) + "\n"

        return StreamingResponseWithErrorHandling(stream_generator(data_stream), media_type="application/json")

    @router.post(
        path=f"{base_endpoint}/data",
        deprecated=True,
        operation_id="stream_data",
    )
    async def stream_data(
        name: str,
        query: Optional[TokenClassificationQuery] = None,
        common_params: CommonTaskHandlerDependencies = Depends(),
        limit: Optional[int] = Query(None, description="Limit loaded records", gt=0),
        service: TokenClassificationService = Depends(TokenClassificationService.get_instance),
        datasets: DatasetsService = Depends(DatasetsService.get_instance),
        current_user: User = Security(auth.get_user, scopes=[]),
        id_from: Optional[str] = None,
    ) -> StreamingResponse:
        """
            Creates a data stream over dataset records

        Parameters
        ----------
        name
            The dataset name
        query:
            The stream data query
        common_params:
            Common query params
        limit:
            The load number of records limit. Optional
        service:
            The dataset records service
        datasets:
            The datasets service
        current_user:
            Request user
        id_from:
            If provided, read the samples after this record ID

        """
        query = query or TokenClassificationQuery()
        dataset = datasets.find_by_name(
            user=current_user,
            name=name,
            task=task_type,
            workspace=common_params.workspace,
        )
        data_stream = map(
            TokenClassificationRecord.parse_obj,
            service.read_dataset(
                dataset=dataset,
                query=ServiceTokenClassificationQuery.parse_obj(query),
                id_from=id_from,
                limit=limit,
            ),
        )

        return scan_data_response(
            data_stream=data_stream,
            limit=limit,
        )

    token_classification_dataset_settings.configure_router(router)
    metrics.configure_router(
        router,
        cfg=TasksFactory.get_task_by_task_type(task_type),
    )

    return router


router = configure_router()

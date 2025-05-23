from typing import List, Optional

from datetime import datetime, timedelta, timezone

from gql import gql
from specklepy.api import operations
from specklepy.core.api.client import SpeckleClient
from specklepy.core.api.inputs.version_inputs import CreateVersionInput
from specklepy.core.api.models import Branch, Project, ResourceCollection
from specklepy.core.api.responses import DataResponse
from specklepy.logging.exceptions import GraphQLException, SpeckleException
from specklepy.objects.base import Base
from specklepy.transports.server.server import ServerTransport


def get_filtered_projects(
    automate_context, speckle_client: SpeckleClient, workspace_id: str
) -> List[str]:

    filtered_projects = []
    projects = get_projects_from_workspace(speckle_client, workspace_id)

    for project in projects:
        if isinstance(project, Project):

            one_hour_before_now = datetime.now(timezone.utc) - timedelta(hours=1)
            if (
                project.workspaceId == workspace_id
                and project.updatedAt >= one_hour_before_now
                and project.id != automate_context.automation_run_data.project_id
            ):
                filtered_projects.append(project)

    return filtered_projects


def create_new_version_in_other_project(
    automate_context,
    speckle_client: SpeckleClient,
    root_object: Base,
    project_id: str,
    model_name: str,
    version_message: str = "",
) -> None:

    branch = speckle_client.branch.get(project_id, model_name, 1)
    model_id = ""
    if isinstance(branch, Branch):
        if not branch.id:
            raise ValueError("Cannot use the branch without its id")
        matching_trigger = [
            t
            for t in automate_context.automation_run_data.triggers
            if t.payload.model_id == branch.id
        ]
        if matching_trigger:
            raise ValueError(
                f"The target model: {model_name} cannot match the model"
                f" that triggered this automation:"
                f" {matching_trigger[0].payload.model_id}"
            )
        model_id = branch.id

    else:
        # we just check if it exists
        branch_create = speckle_client.branch.create(
            project_id,
            model_name,
        )
        if isinstance(branch_create, Exception):
            raise branch_create
        model_id = branch_create

    transport = ServerTransport(
        client=speckle_client,
        account=speckle_client.account,
        stream_id=project_id,
    )

    root_object_id = operations.send(
        root_object,
        [transport],
        use_default_cache=False,
    )

    version_id = speckle_client.version.create(
        CreateVersionInput(
            projectId=project_id,
            objectId=root_object_id,
            modelId=model_id,
            message=version_message,
            sourceApplication="SpeckleAutomate",
        )
    )

    if isinstance(version_id, SpeckleException):
        raise version_id


def get_projects_from_workspace(
    speckle_client: SpeckleClient, workspace_id: str
) -> ResourceCollection[Project]:

    QUERY = gql(
        """
        query Workspace($id: String!) {
            data:workspace (id: $id){
                    data:projects
                    {
                        totalCount
                        cursor
                        items
                        {
                            id
                            name
                            sourceApps
                            allowPublicComments
                            createdAt
                            description
                            role
                            updatedAt
                            visibility
                            workspaceId
                        }
                    }
            }
        }
        """
    )

    variables = {
        "id": workspace_id,
    }

    response = speckle_client.active_user.make_request_and_parse_response(
        DataResponse[Optional[DataResponse[ResourceCollection[Project]]]],
        QUERY,
        variables,
    )

    if response.data is None:
        raise GraphQLException(
            "GraphQL response indicated that the ActiveUser could not be found"
        )

    return response.data.data.items

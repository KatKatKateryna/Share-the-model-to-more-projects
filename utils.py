from typing import List

from specklepy.api import operations

from datetime import datetime, timedelta, timezone

from specklepy.core.api.models import Branch
from specklepy.logging.exceptions import SpeckleException
from specklepy.objects.base import Base
from typing import List

from specklepy.core.api.inputs.version_inputs import CreateVersionInput
from specklepy.core.api.models.current import Project
from specklepy.transports.server.server import ServerTransport


def get_projects_from_client(automate_context, workspace_id: str) -> List[str]:

    filtered_projects = []
    projects: List[Project] = (
        automate_context.speckle_client.active_user.get_projects().items
    )

    for project in projects:
        if isinstance(project, Project):

            one_hour_before_now = datetime.now(timezone.utc) - timedelta(hours=1)
            if (
                project.workspaceId == workspace_id
                and project.updatedAt >= one_hour_before_now
            ):
                filtered_projects.append(project)

    return filtered_projects


def create_new_version_in_other_project(
    automate_context: "AutomationContext",
    root_object: Base,
    project_id: str,
    model_name: str,
    version_message: str = "",
) -> None:
    """Save a base model to a new version on the project.

    Args:
        root_object (Base): The Speckle base object for the new version.
        model_id (str): For now please use a `branchName`!
        version_message (str): The message for the new version.
    """
    if project_id == automate_context.automation_run_data.project_id:
        # don't do anything for the same project
        return

    branch = automate_context.speckle_client.branch.get(project_id, model_name, 1)
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
        branch_create = automate_context.speckle_client.branch.create(
            project_id,
            model_name,
        )
        if isinstance(branch_create, Exception):
            raise branch_create
        model_id = branch_create

    transport = ServerTransport(
        client=automate_context.speckle_client,
        account=automate_context.speckle_client.account,
        stream_id=project_id,
    )

    root_object_id = operations.send(
        root_object,
        [transport],
        use_default_cache=False,
    )
    print("_________________________________________________________________")
    print(root_object_id)
    print(automate_context.speckle_client)

    version_id = automate_context.speckle_client.version.create(
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

    automate_context._automation_result.result_versions.append(version_id)

"""This module contains the function's business logic.

Use the automation_context module to wrap your function in an Automate context helper.
"""

from typing import List
from pydantic import Field, SecretStr
from speckle_automate import (
    AutomateBase,
    AutomationContext,
    execute_automate_function,
)

from specklepy.core.api.models.current import Project
from specklepy.api.client import SpeckleClient
from utils import create_new_version_in_other_project, get_filtered_projects


class FunctionInputs(AutomateBase):
    """These are function author-defined values.

    Automate will make sure to supply them matching the types specified here.
    Please use the pydantic model schema to define your inputs:
    https://docs.pydantic.dev/latest/usage/models/
    """

    speckle_token: SecretStr = Field(
        title="Speckle token",
        default=SecretStr(""),
    )


def automate_function(
    automate_context: AutomationContext,
    function_inputs: FunctionInputs,
) -> None:
    """This is an example Speckle Automate function.

    Args:
        automate_context: A context-helper object that carries relevant information
            about the runtime context of this function.
            It gives access to the Speckle project data that triggered this run.
            It also has convenient methods for attaching result data to the Speckle model.
        function_inputs: An instance object matching the defined schema.
    """
    # The context provides a convenient way to receive the triggering version.
    version_root_object = automate_context.receive_version()

    speckle_client = SpeckleClient()
    speckle_client.authenticate_with_token(
        function_inputs.speckle_token.get_secret_value()
    )

    workspace_id: str = speckle_client.project.get(
        automate_context.automation_run_data.project_id
    ).workspaceId

    model_name = speckle_client.model.get(
        automate_context.automation_run_data.triggers[0].payload.model_id,
        automate_context.automation_run_data.project_id,
    ).name

    projects: List[Project] = get_filtered_projects(
        automate_context, speckle_client, workspace_id
    )

    for project in projects:
        create_new_version_in_other_project(
            automate_context,
            speckle_client,
            version_root_object,
            project.id,
            model_name,
        )

    automate_context.mark_run_success(
        f"Model successfully shared to {len(projects)} projects in the workspace {workspace_id}. All Projects: {[x.name for x in projects]}"
    )

    # If the function generates file results, this is how it can be
    # attached to the Speckle project/model
    # automate_context.store_file_result("./report.pdf")


def automate_function_without_inputs(automate_context: AutomationContext) -> None:
    """A function example without inputs.

    If your function does not need any input variables,
     besides what the automation context provides,
     the inputs argument can be omitted.
    """
    pass


# make sure to call the function with the executor
if __name__ == "__main__":
    # NOTE: always pass in the automate function by its reference; do not invoke it!

    # Pass in the function reference with the inputs schema to the executor.
    execute_automate_function(automate_function, FunctionInputs)

    # If the function has no arguments, the executor can handle it like so
    # execute_automate_function(automate_function_without_inputs)

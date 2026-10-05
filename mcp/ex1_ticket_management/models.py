from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PatchFileChange(BaseModel):
    """One file operation in a remediation change set."""

    application_name: str = Field(min_length=1)
    host_name: str = Field(default="localhost", min_length=1)
    filename: str = Field(min_length=1)
    operation: Literal["create", "update", "delete"]
    content: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "PatchFileChange":
        if self.operation == "delete" and self.content is not None:
            raise ValueError("delete operations cannot include file content")
        if self.operation != "delete" and self.content is None:
            raise ValueError(
                "create and update operations require file content"
            )
        return self


class PatchProposal(BaseModel):
    """File-level remediation details associated with a ticket."""

    changes: list[PatchFileChange] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_filenames(self) -> "PatchProposal":
        file_targets = [
            (change.host_name, change.application_name, change.filename)
            for change in self.changes
        ]
        if len(file_targets) != len(set(file_targets)):
            raise ValueError("a patch can only change each target file once")
        return self


class ApplicationContext(BaseModel):
    """An application and host where a ticket's source code is deployed."""

    application_name: str = Field(min_length=1)
    host_name: str = Field(default="localhost", min_length=1)


class SourceFile(BaseModel):
    """File content used to seed or inspect the patch workspace."""

    application_name: str = Field(min_length=1)
    host_name: str = Field(default="localhost", min_length=1)
    filename: str = Field(min_length=1)
    content: str


class SourceFileListing(BaseModel):
    """Files available within one application and host workspace."""

    application_name: str
    host_name: str = "localhost"
    files: list[str]


class Ticket(BaseModel):
    """Incident data with remediation stored as a multi-file change set."""

    id: str = Field(description="Unique ticket identifier, e.g. TICK-101")
    title: str = Field(description="Short summary of the issue")
    description: str | None = Field(
        default=None,
        description="Observed behavior, impact, and expected behavior",
    )
    applications: list[ApplicationContext] = Field(default_factory=list)
    status: str = Field(description="Current lifecycle status, e.g. OPEN")
    error_code: str = Field(
        description="Known error code associated with the issue"
    )
    patch_details: PatchProposal | None = None
    patch_result: str | None = None
    patch_status: Literal["SUCCESS", "FAILURE"] | None = None
    patch_error: str | None = None
    rca_report: str | None = None

    @model_validator(mode="after")
    def validate_unique_applications(self) -> "Ticket":
        targets = [
            (application.host_name, application.application_name)
            for application in self.applications
        ]
        if len(targets) != len(set(targets)):
            raise ValueError("ticket application targets must be unique")
        return self

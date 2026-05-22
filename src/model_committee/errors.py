class ModelCommitteeError(Exception):
    pass


class ConfigError(ModelCommitteeError):
    pass


class ParseError(ModelCommitteeError):
    pass


class ConsistencyError(ModelCommitteeError):
    pass


class ProviderError(ModelCommitteeError):
    def __init__(
        self,
        message: str,
        *,
        exit_status: int | None = None,
        timeout_seconds: int | None = None,
        stderr_path: str | None = None,
        response_path: str | None = None,
    ):
        super().__init__(message)
        self.exit_status = exit_status
        self.timeout_seconds = timeout_seconds
        self.stderr_path = stderr_path
        self.response_path = response_path


class ModelOutputError(ModelCommitteeError):
    def __init__(
        self,
        message: str,
        *,
        stderr_path: str | None = None,
        response_path: str | None = None,
    ):
        super().__init__(message)
        self.stderr_path = stderr_path
        self.response_path = response_path


class PatchValidationError(ModelCommitteeError):
    pass


class SelectionError(ModelCommitteeError):
    pass


class HumanReviewRequired(ModelCommitteeError):
    pass

class ModelCommitteeError(Exception):
    pass


class ConfigError(ModelCommitteeError):
    pass


class ParseError(ModelCommitteeError):
    pass


class ConsistencyError(ModelCommitteeError):
    pass


class ProviderError(ModelCommitteeError):
    pass


class ModelOutputError(ModelCommitteeError):
    pass


class PatchValidationError(ModelCommitteeError):
    pass


class SelectionError(ModelCommitteeError):
    pass

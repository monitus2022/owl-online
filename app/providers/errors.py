"""Provider error types. Adapters translate vendor errors into these.
"""


class ProviderError(Exception):
    """Base for a normalized provider failure."""


class ProviderTimeout(ProviderError):
    """The provider did not answer in time."""


class ProviderRateLimited(ProviderError):
    """The provider rejected the call for rate or credit reasons."""
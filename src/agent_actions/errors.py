"""Errors that stop a run. The CLI prints the message and exits with code 1."""


class AgentActionsError(Exception):
    """Base class for all framework errors."""


class IncompatibleProcessError(AgentActionsError):
    """A process cannot attach to a hook, or the harness cannot deliver what it returns."""


class IncompatibleResultError(AgentActionsError):
    """A process returned a verdict or a context that the hook cannot deliver."""


class ProcessFailedError(AgentActionsError):
    """A process raised an exception on a hook that cannot block."""


class RunnerFileError(AgentActionsError):
    """The runner file is missing, fails, or does not call `agent_actions.run(context)`."""


class StateError(AgentActionsError):
    """A state file is corrupt, or a state variable is not JSON-serializable."""


class PayloadError(AgentActionsError):
    """The hook payload is not a JSON object."""

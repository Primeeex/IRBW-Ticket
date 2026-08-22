from __future__ import annotations


class TicketBotError(Exception):
    """Base exception for the ticket bot."""

    def __init__(self, message: str = "An error occurred.") -> None:
        self.message = message
        super().__init__(self.message)


class ConfigurationError(TicketBotError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str = "Configuration error.") -> None:
        super().__init__(message)


class TicketNotFoundError(TicketBotError):
    """Raised when a ticket is not found."""

    def __init__(self, ticket_id: str = "") -> None:
        super().__init__(f"Ticket '{ticket_id}' not found." if ticket_id else "Ticket not found.")


class PermissionDeniedError(TicketBotError):
    """Raised when a user lacks required permissions."""

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message)


class MaxTicketsReachedError(TicketBotError):
    """Raised when a user has reached the maximum number of tickets."""

    def __init__(self, max_tickets: int = 1) -> None:
        super().__init__(f"You have reached the maximum number of active tickets ({max_tickets}).")


class TicketAlreadyClaimedError(TicketBotError):
    """Raised when a ticket is already claimed by another staff member."""

    def __init__(self, claimer_id: int = 0) -> None:
        super().__init__(f"This ticket is already claimed by another staff member.")


class TicketAlreadyRespondedError(TicketBotError):
    """Raised when trying to respond to an already responded ticket."""

    def __init__(self) -> None:
        super().__init__("This ticket has already been responded to.")


class InvalidTicketStateError(TicketBotError):
    """Raised when an operation is invalid for the current ticket state."""

    def __init__(self, message: str = "This operation is not valid for the current ticket state.") -> None:
        super().__init__(message)


class ChannelNotFoundError(TicketBotError):
    """Raised when a configured channel is not found."""

    def __init__(self, channel_type: str = "channel") -> None:
        super().__init__(f"Configured {channel_type} not found.")


class RoleNotFoundError(TicketBotError):
    """Raised when a configured role is not found."""

    def __init__(self) -> None:
        super().__init__("Configured role not found.")


class DMFailedError(TicketBotError):
    """Raised when a DM cannot be sent to a user."""

    def __init__(self) -> None:
        super().__init__("Could not send DM to the user. Their DMs may be closed.")


class TranscriptError(TicketBotError):
    """Raised when transcript generation fails."""

    def __init__(self, message: str = "Failed to generate transcript.") -> None:
        super().__init__(message)

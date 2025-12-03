from typing import Optional, Dict, Any


class Event:
    """
    Represents a discrete event in the traffic simulation system.
    
    Events are used in a priority queue (heapq) and are processed in order
    of time. If two events have the same time, they are ordered by priority.
    
    Attributes:
        time: The simulation time when the event occurs (seconds from start)
        event_type: The type of event (use class constants)
        priority: Priority for tie-breaking when times are equal (lower = higher priority)
        data: Dictionary containing event-specific data
    
    Example:
        >>> event = Event(100.5, Event.BUS_ARRIVAL, {"bus_id": "B1"})
        >>> event.time
        100.5
    """
    
    # Event type constants
    BUS_ARRIVAL = "BUS_ARRIVAL"
    MINIBUS_ARRIVAL = "MINIBUS_ARRIVAL"
    PASSENGER_APPEAR = "PASSENGER_APPEAR"
    OPTIMIZE_CALL = "OPTIMIZE_CALL"
    SIMULATION_END = "SIMULATION_END"
    
    # Default priorities for each event type
    _DEFAULT_PRIORITIES = {
        BUS_ARRIVAL: 0,
        MINIBUS_ARRIVAL: 1,
        PASSENGER_APPEAR: 2,
        OPTIMIZE_CALL: 3,
        SIMULATION_END: 10,
    }
    
    def __init__(
        self,
        time: float,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        priority: Optional[int] = None
    ):
        """
        Initialize an Event instance.
        
        Args:
            time: The simulation time when the event occurs (must be >= 0)
            event_type: The type of event (use class constants)
            data: Optional dictionary containing event-specific data
            priority: Optional priority for ordering. If None, uses default based on event_type
            
        Raises:
            ValueError: If time is negative
        """
        # Validate time
        if time < 0:
            raise ValueError(f"Event time must be non-negative, got {time}")
        
        self.time = time
        self.event_type = event_type
        self.data = data if data is not None else {}
        
        # Set priority: use provided priority, or default based on event_type, or 5 as fallback
        if priority is not None:
            self.priority = priority
        else:
            self.priority = self._DEFAULT_PRIORITIES.get(event_type, 5)
    
    def __lt__(self, other: 'Event') -> bool:
        """
        Compare events for ordering in priority queue (heapq).
        
        Events are ordered by:
        1. Time (earlier times first)
        2. Priority (lower priority numbers first, if times are equal)
        
        
        Args:
            other: Another Event instance to compare with
            
        Returns:
            True if this event should be processed before the other event
        """
        # First compare by time
        if self.time != other.time:
            return self.time < other.time
        
        # If times are equal, compare by priority (lower number = higher priority)
        return self.priority < other.priority
    
    def __eq__(self, other: 'Event') -> bool:
        """
        Check if two events are equal.
        
        Events are considered equal if they have the same time, event_type, and priority.
        
        Args:
            other: Another Event instance to compare with
            
        Returns:
            True if events are equal
        """
        if not isinstance(other, Event):
            return False
        
        return (
            self.time == other.time
            and self.event_type == other.event_type
            and self.priority == other.priority
        )
    
    def __repr__(self) -> str:
        """
        Return a string representation of the event.
        
        Returns:
            A readable string representation of the event
        """
        return f"Event(time={self.time}, type={self.event_type}, priority={self.priority})"
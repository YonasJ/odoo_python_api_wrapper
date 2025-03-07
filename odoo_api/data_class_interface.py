from __future__ import annotations  # This is crucial for forward references
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypeVar


from typing import Any

if TYPE_CHECKING:
    from .api_wrapper import OdooTransaction

class OdooWrapperInterface(ABC):
    @property
    @abstractmethod
    def id(self)->int: # type: ignore
        pass
    @id.setter
    @abstractmethod
    def id(self,id)->None: # type: ignore
        pass

    @abstractmethod
    def get_value(self, prop, value_if_none=None)->Any|None: # type: ignore
        pass
    
    
    @property
    @abstractmethod
    def transaction (self)->OdooTransaction: # type: ignore
        pass
 
    @property
    @abstractmethod
    def changes (self)->dict[str,Any]: # type: ignore
        pass

    @property
    @abstractmethod
    def wrapped_oject (self)->dict[str,Any]: # type: ignore
        pass
    
    @property
    def MODEL (self)->str: 
        raise NotImplementedError('MODEL property not implemented')

    @classmethod
    @abstractmethod
    def _get_model(cls) -> str:
        raise NotImplementedError('_get_model property not implemented')


from __future__ import annotations  # This is crucial for forward references

from .object_wrapper_interface import OdooWrapperInterface

from typing import Any
import json
from .api_wrapper import OdooTransaction

class ObjectWrapper(OdooWrapperInterface):
    '''
    Object wrapper class.
    This a wrapper for objects. It is initialiesed with the object to wrap
    and then proxies the unhandled getattribute methods to it.
    Other classes are to inherit from it.
    '''
    def __init__(self, be:OdooTransaction, model:str, obj:Any):
        self._wrapped_obj = obj
        self._model = model
        self._be = be  
        
    @property
    def transaction (self)->OdooTransaction: 
        return self._be
    @property
    def wrapped_oject (self)->dict[str,Any]: # type: ignore
        return self._wrapped_obj
    @property 
    def changes  (self)->dict[str,Any]: # type: ignore
        return self.changes

    def get_value(self, prop, value_if_none=None)->Any|None: # type: ignore
        return getattr(self._wrapped_obj, prop, value_if_none)
    
    
    def __getattr__(self, attr):
        # see if this object has attr
        # NOTE do not use hasattr, it goes into
        # infinite recurrsion
        if attr in self.__dict__:
            # this object has it
            return getattr(self, attr)
        # proxy to the wrapped object
        return getattr(self._wrapped_obj, attr)
    
    def __getitem__(self, index):
        return self._wrapped_obj.__getitem__(index)
    def __str__(self) -> str:
        return json.dumps(self._wrapped_obj, indent=2)

    def get(self, attr) -> Any:
        if attr in self.__dict__:
            # this object has it
            return getattr(self, attr)
        # proxy to the wrapped object
        return self._wrapped_obj.get(attr) # getattr(self._wrapped_obj, attr)
        # emulator for account.move of relationship.
    @property
    def id(self) -> int:
        return self._wrapped_obj["id"]
 
    def get_id(self, value_if_none=None) -> int|None:
        if "id" in self._wrapped_obj:
            return self._wrapped_obj["id"]
        return value_if_none
    
    @id.setter
    def id(self,id)->None: # type: ignore
        self._wrapped_obj["id"] = id

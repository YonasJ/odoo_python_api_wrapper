import copy
from datetime import datetime
from typing import Any
from .api_wrapper import OdooTransaction
from .data_class_interface import OdooWrapperInterface

class OdooDataClass(OdooWrapperInterface):
    
    def __init__(self, odoo:OdooTransaction, model:str, wo:dict[str,Any]|None):
        assert isinstance(odoo, OdooTransaction)
        self.odoo: OdooTransaction = odoo
        self._MODEL:str = model
        if wo:
            self.wo = wo
        else:
            self.wo:dict[str,Any] = {}
        
        self._changes:dict[str,Any] = {}
        
        self.related_records: dict[str,list[OdooDataClass]] = {}

    # also note you must have a class property called _MODEL
    def __deepcopy__(self, memo):
        key = f"{self.model}:{self.id}"
        if f"{self.model}:{self.id}" in memo:
            return memo[key]
        
        new_node:OdooDataClass = type(self)(memo['trans']) # type: ignore
        memo[key] = new_node

        new_node.wo = copy.deepcopy(self.wo, memo)
        new_node._changes = self._changes
        new_node.related_records = copy.deepcopy(self.related_records, memo)
        memo['trans'].append(new_node)
        return new_node

    @property
    def id(self) -> int:
        ret = self.get_value_int("id")    
        if not ret:
            raise ValueError("Null id")
        return ret
    
    def get_id(self, value_if_none)->int|None: # type: ignore
        ret = self.get_value_int("id")    
        if not ret:
            return value_if_none
        return ret

    @id.setter
    def id(self,id)->None: # type: ignore
        self.set_value_int("id",id)
    
    @property
    def transaction (self)->OdooTransaction: # type: ignore
        return self.odoo

    @property
    def changes (self)->dict[str,Any]: 
        return self._changes
    @property
    def wrapped_oject (self)->dict[str,Any]: # type: ignore
        return self.wo
 
    def get_value(self, prop, value_if_none=None):# -> Any:
        if prop in self.changes:
            return self.changes[prop]
        if prop in self.wo:
            return self.wo[prop]
        return value_if_none

    def get_value_float(self, prop) -> float|None:
        ret= self.get_value(prop)
        if ret is None:
            return None
        return float(ret)
    def get_value_int(self, prop) -> int|None:
        ret= self.get_value(prop)
        if ret is None:
            return None 
        return int(ret)
    def get_value_bool(self, prop) -> bool|None:
        ret= self.get_value(prop)
        if ret is None:
            return None 
        return bool(ret)    
    def get_value_str(self, prop) -> str|None:
        ret= self.get_value(prop)
        if ret is None or ret is False:
            return None 
        return str(ret)
    def get_value_date(self, prop) -> datetime|None:
        ret= self.get_value(prop)
        if ret is None or ret is False:
            return None
        return datetime.strptime(ret, "%Y-%m-%d")

    def get_many2one(self, prop: str, model_class:type, when_none=None):
        obj_field_name =prop
        existing_in_change = self.changes.get(obj_field_name)
        if existing_in_change: 
            return existing_in_change
        value = self.get_value(obj_field_name, when_none) 

        if value and not isinstance(value, OdooWrapperInterface):
            if isinstance(value, int):
                match = self.odoo.get(model_class, "id", value) # First element is the id, second the name.
            else:
                match = self.odoo.get(model_class, "id", value[0]) # First element is the id, second the name.
            if match:
                self.wo[obj_field_name] = match
                return match
        
        return value
    
    def set_many2one(self, prop:str, value:'OdooDataClass|None') -> None:  
        self.set_data(prop, value)
    
    def get_one2many(self, field_name: str, other_model_class, field_in_other_model:str ):
        ret = self.related_records.get(field_name)
        if ret is None:
            self.related_records[field_name] = ret = []
            if self.get_value('id'):
                related = self.odoo.search(other_model_class,[(field_in_other_model, '=', self.id)])

                for r in related:
                    ret.append(r)
        return ret
    
    def set_one2many(self):
        raise Exception("asdf")
        # return None
         
    def set_data(self, prop, value) -> None: 
        self.transaction.append(self)
        
        db_val = self.wo.get(prop)
        if db_val == value and prop in self.changes:
            del self.changes[prop]
        elif db_val != value:  
            self.changes[prop] = value
        
    def set_value_money(self, prop, value:float) -> None: 
        self.set_data(prop, round(float(value),2))
    def set_value_str(self, prop, value:str|None) -> None: 
        if value is None:
            self.set_data(prop, None)
        else:
            self.set_data(prop, str(value))
    def set_value_float(self, prop, value:float|None) -> None: 
        if value is None:
            self.set_data(prop, 0.0) # None handling with floats is not yet done, so we just save 0
        else:
            self.set_data(prop, float(value))

    def set_value_int(self, prop, value:int|None) -> None:  
        self.set_data(prop, int(value) if value is not None else None)
    def set_value_bool(self, prop, value:bool|None) -> None:  
        self.set_data(prop, bool(value) if value is not None else None)
    def set_value_date(self, prop, value:datetime|None) -> None:  
        self.set_data(prop, value.strftime('%Y-%m-%d') if value is not None else None)

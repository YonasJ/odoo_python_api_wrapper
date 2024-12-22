import copy
from datetime import datetime
from typing import Any
from .api_wrapper import OdooTransaction
from .object_wrapper_interface import OdooWrapperInterface

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
        ret = self.get_data_int("id")    
        if not ret:
            raise ValueError("Null id")
        return ret
    
    def get_id(self, value_if_none)->int|None: # type: ignore
        ret = self.get_data_int("id")    
        if not ret:
            return value_if_none
        return ret

    @id.setter
    def id(self,id)->None: # type: ignore
        self.set_data_int("id",id)
    
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

    def get_data_float(self, prop) -> float|None:
        ret= self.get_value(prop)
        if ret is None:
            return None
        return float(ret)
    def get_data_int(self, prop) -> int|None:
        ret= self.get_value(prop)
        if ret is None:
            return None 
        return int(ret)
    def get_data_str(self, prop) -> str|None:
        ret= self.get_value(prop)
        if ret is None:
            return None 
        return str(ret)
    def get_data_date(self, prop) -> datetime|None:
        ret= self.get_value(prop)
        if ret is None or ret is False:
            return None
        return datetime.strptime(ret, "%Y-%m-%d")

    def get_many2one(self, prop: str, model_class:type):
        obj_field_name =prop[:-3]
        existing_in_change = self.changes.get(obj_field_name)
        if existing_in_change: 
            return existing_in_change
        value = self.get_value(obj_field_name) # not sure about this.
        if value:
            return value

        value = self.get_value(prop) # not sure about this.
        if value and not isinstance(value, OdooWrapperInterface):
            match = self.odoo.get(model_class, "id", value[0])
            if match:
                self.wo[obj_field_name] = match
                return match
        raise Exception("The above should handle these?")            
        model_name = model_class.Z_MODEL  # Extract the model name from the class
        related_record_id = value[1]  # Get the res_id from the tuple
        matches = self.odoo.search(model_name, [('id', '=', related_record_id)])
        if matches:
            return model_class(self.odoo, matches[0])
    
    def set_many2one(self, prop:str, value:'OdooDataClass') -> None:  
        obj_field_name =prop[:-3]
        self.set_data(obj_field_name, value)
    
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
        
    def set_data_money(self, prop, value:float) -> None: 
        self.set_data(prop, round(float(value),2))
    def set_data_str(self, prop, value:str|None) -> None: 
        if value is None:
            self.set_data(prop, None)
        else:
            self.set_data(prop, str(value))
    def set_data_float(self, prop, value:float|None) -> None: 
        if value is None:
            self.set_data(prop, None)
        else:
            self.set_data(prop, float(value))

    def set_data_int(self, prop, value:int|None) -> None:  
        self.set_data(prop, int(value) if value is not None else None)
    def set_data_date(self, prop, value:datetime|None) -> None:  
        self.set_data(prop, value.strftime('%Y-%m-%d') if value is not None else None)

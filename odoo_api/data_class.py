import copy
from datetime import datetime
import time
from typing import Any, TypeVar
from .api_wrapper import OdooTransaction
from .data_class_interface import OdooWrapperInterface
from mixt import SingleList
class OdooManyToManyHelper:
    def __init__(self):
        self.adds:list[OdooWrapperInterface] = []
        self.removes:list[OdooWrapperInterface] = []
        pass

T = TypeVar('T')

class OdooDataClass(OdooWrapperInterface):
    
    def __init__(self, trans:OdooTransaction, model:str, id:int|None, wo:dict[str,Any]|None):
        assert isinstance(trans, OdooTransaction)
        self.trans: OdooTransaction = trans
        self._MODEL:str = model
        if wo:
            self.a__wo = wo
        else:
            self.a__wo:dict[str,Any] = {}
        self._changes:dict[str,Any] = {}
        
        self.related_records: dict[str,list[OdooWrapperInterface]] = {}
        if id:
            self._id = id
        else:
            self._id = trans._gen_working_id()

        self.trans.append(self)

    # also note you must have a class property called _MODEL
    def __deepcopy__(self, memo):
        key = f"{self.model}:{self.id}"
        if key in memo:
            return memo[key]
        trans = memo['trans'] # type: OdooTransaction

        if key in trans.objects:
            return trans.objects[key]

        new_node:OdooDataClass = type(self)(trans, self._id, None) # type: ignore
        # Note: The object appends itself to the transaction.
        memo[key] = new_node
        new_node.a__wo = copy.deepcopy(self.a__wo, memo)
        new_node._changes = copy.deepcopy(self._changes, memo)
        new_node.related_records = copy.deepcopy(self.related_records, memo)
        return new_node

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self,id:int)->None: # type: ignore
        assert isinstance(id, int)
        
        self._id = id
    
    def __eq__(self, other):
        if not isinstance(other, OdooDataClass):
            return NotImplemented
        if self._id is None or other._id is None:
            raise ValueError("Cannot compare objects without id")
            # return super().__eq__(other)
        return self._id == other._id and self.model == other.model


    def delete(self):
        self.trans.delete(self)
        

    @property
    def transaction (self)->OdooTransaction: # type: ignore
        return self.trans

    @property
    def changes (self)->dict[str,Any]: 
        return self._changes
    @property
    def wrapped_oject (self)->dict[str,Any]: # type: ignore
        if self.model == 'res.partner':
            return self.a__wo
        return self.a__wo
 
    def get_value(self, prop, value_if_none=None):# -> Any:
        if prop in self.changes:
            return self.changes[prop]
        if prop in self.a__wo:
            return self.a__wo[prop]
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
        try:
            return datetime.strptime(ret, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.strptime(ret, "%Y-%m-%d")

    def get_many2one(self, prop: str, model_class:type[T], when_none:T|None=None) -> T | None:# -> Any | Any | int | None | OdooWrapperInterface:# -> Any | Any | int | None | OdooWrapperInterface:
        assert issubclass(model_class, OdooWrapperInterface)
        obj_field_name =prop
        existing_in_change = self.changes.get(obj_field_name)
        if existing_in_change: 
            return existing_in_change
        value = self.get_value(obj_field_name, when_none) 

        if value and not isinstance(value, OdooWrapperInterface):
            if isinstance(value, int):
                match = self.trans.get(model_class, "id", value) # First element is the id, second the name.
            else:
                match = self.trans.get(model_class, "id", value[0]) # First element is the id, second the name.
            if match:
                self.a__wo[obj_field_name] = match
                return match
        if value:
            return value # type: ignore
        return when_none
    
    def set_many2one(self, prop:str, value:'OdooDataClass|None') -> None:  
        self.set_data(prop, value)
    
    def get_one2many(self, field_name: str, other_model_class:type[T], field_in_other_model:str) -> list[T]:
        assert issubclass(other_model_class, OdooWrapperInterface)
        # ids = self.wrapped_oject.get(field_name)
        ret:list[TT]|None = self.related_records.get(field_name) # type: ignore
        if ret is None:
            self.related_records[field_name] = ret = SingleList()
            if self.get_value(field_name):
                db_search = []
                for x in self.get_value(field_name): # type: ignore
                    key = f"{other_model_class.model}:{x}"
                    o = self.transaction.objects.get(key)
                    if o:
                        ret.append(o)
                    else:
                        db_search.append(x)
                if db_search:                  
                    ret.extend(self.transaction.extend(
                        self.trans.search(other_model_class,[('id', 'in', db_search)])))
            elif self.get_value('id'):
                related = self.trans.search(other_model_class,[(field_in_other_model, '=', self.id)])
                ret.extend(self.transaction.extend(related))

            # check the transaction of related objects.
            for _,r in enumerate(self.transaction.objects.values()):
                if isinstance(r, other_model_class) and r.get_value(field_in_other_model) == self.id:
                    ret.append(r)
        return ret
       
    def get_many2many(self, field_name: str, other_model_class:type[T]) -> tuple[T]:
        assert issubclass(other_model_class, OdooWrapperInterface)
        ids = self.a__wo.get(field_name)
        ret:list[TT]|None = self.related_records.get(field_name) # type: ignore
        if ret is None:
            self.related_records[field_name] = ret = []
            if self.get_value(field_name):
                related = self.trans.search(other_model_class,[('id', 'in', self.get_value(field_name))])
                ret.extend(self.transaction.extend(related))

        return tuple(ret)

    def append_many2many(self, field_name: str, other_model_class:type[T], new_value:T|list[T]):
        if isinstance(new_value, list):
            for x in new_value:
                self.append_many2many(field_name, other_model_class, x)
            return
        assert issubclass(other_model_class, OdooWrapperInterface)
        assert isinstance(new_value, OdooDataClass)

        if new_value.transaction != self.transaction:
            raise ValueError("Cannot append a value that is not in the same transaction.")

        # ids = self.wrapped_oject.get(field_name)
        related_records:list[TT]|None = self.related_records.get(field_name) # type: ignore
        if related_records is None:
            self.related_records[field_name] = related_records = []
            if self.get_value(field_name):
                related = self.trans.search(other_model_class,[('id', 'in', self.get_value(field_name))])
                related_records.extend(self.transaction.extend(related))
        if new_value in related_records:
            return
        # if not new_value.get_id(): raise ValueError("Cannot append a record that has not been saved yet.")
        # for x in ret:
        #     if x.id == new_value.id:
        #         return

        # Save to changes
        if self.changes.get(field_name) is None:
            self.changes[field_name] = OdooManyToManyHelper()

        h = self.changes[field_name]
        h.adds.append(new_value)

        related_records.append(new_value)
        self.transaction.commit()

    def set_one2many(self):
        raise Exception("asdf")
        # return None
         
    def set_data(self, prop, value) -> None: 
        if isinstance(value, OdooWrapperInterface) and value.transaction != self.transaction:
            raise ValueError("Cannot set a value that is not in the same transaction.")
        if prop != 'id':
            self.trans.append(self)

        db_val = self.a__wo.get(prop)
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

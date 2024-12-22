from __future__ import annotations  # This is crucial for forward references
from abc import ABC, abstractmethod
import copy
import inspect
from typing import TYPE_CHECKING, TypeVar
if TYPE_CHECKING:
    from .object_wrapper_interface import OdooWrapperInterface

if TYPE_CHECKING:
    from .data_class import OdooDataClass


from typing import Any
import xmlrpc.client
import json
import random
import urllib
import urllib.request
from .keepass_passwords import KeePass

T = TypeVar('T', bound='OdooWrapperInterface')

class OdooTransaction:    
    def __init__(self, backend:OdooBackend):
        self.backend = backend
        self.objects:set[OdooWrapperInterface] = set()
        self.verbose_logs = False
  
    def append(self, x:OdooWrapperInterface):
        self.objects.add(x)
    
    @property 
    def uid(self): return self.backend.uid
    
    @property 
    def url(self): return self.backend.url

    @property 
    def db(self): return self.backend.db

    @property 
    def api_key(self): return self.backend.api_key
    
       
  #   record = env['event.registration'].search([('id', '=', 14)])
    def get(self, wrapper:type[T], field:str, value:Any) -> T|None:
        model: str = wrapper._MODEL # type: ignore
        for o in self.objects:
            if o.model == model and o.get_value(None) == value:
                if self.verbose_logs: print(f"Get: {model}  -- {field} = {value} (cache hit)")
                return o # type: ignore
        
        if self.verbose_logs: print(f"Get: {model}  -- {field} = {value} (cache miss)")
        ret = self.search(wrapper, [(field, "=", value)],getting=True)
        if ret:
            return ret[0]

  #   record = env['event.registration'].search([('id', '=', 14)])
    def search(self, wrapper:type[T], search, fields=[], getting=False) -> list[T]:
        model: str = wrapper._MODEL # type: ignore
        if self.verbose_logs:
            if (search[0][0] == "id" and search[0][1] == "=") and not getting:
                print(f"Search: {model}  -- {search} (opportunity)")
            else: 
                print(f"Search: {model}  -- {search}")
                pass
        
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        ret = []
        for x in rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'search_read', [search], {'fields': fields, 'limit': 5000}):# type: ignore
            nr:T = wrapper(self, x) # type: ignore
            ret.append(nr) 
        return ret
        
    def search_raw(self, model, search, fields=[]) -> list[OdooWrapperInterface]:
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        ret = []
        for x in rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'search_read', [search], {'fields': fields, 'limit': 5000}):# type: ignore
            from .object_wrapper import ObjectWrapper
            ret.append(ObjectWrapper(self, model,x)) # type: ignore
        return ret
    
    def read(self, model, id, fields) -> OdooWrapperInterface:
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        from .object_wrapper import ObjectWrapper
        return ObjectWrapper(self, model, rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'read', [[id]], {'fields': fields})[0])# type: ignore
    
    def create(self, model:str, rec:list[dict[str,Any]]) -> list[int]:
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        return rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'create', rec) # type: ignore

    def write(self, model, id_pk, rec):
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url), allow_none=True)
        if rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'write', [[id_pk], rec]):
            return True
        return False

    def update_many_to(self, model, special_command):
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        return rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'write', special_command)
    def delete(self, model, ids:list[int]):
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        if rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'unlink', ids):
            return True
        return False

    def execute_action(self, model, action,search):
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url),allow_none=True)
        if rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, action, search):
            return True
        return False
    def execute_action2(self, model, action,p1,p2):
        rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url),allow_none=True,verbose=True)
        if rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, action, [p1,p2]):
            return True
        return False
            
      
    def _execute_actionj(self, rpc_service, rpc_method, params):
        url = f"{self.url}/jsonrpc"
        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": rpc_service, "method": rpc_method, "args": 
                       [self.db, 
                        self.uid if rpc_service != "common" else self.backend.username, 
                        self.api_key]+
                        params},
            "id": random.randint(0, 1000000000),
        }
        req = urllib.request.Request(url=url, data=json.dumps(data).encode(), headers={
            "Content-Type":"application/json",
        })
        reply = json.loads(urllib.request.urlopen(req).read().decode('UTF-8'))
        if reply.get("error"):
            raise Exception(reply["error"])
        
        return reply["id"]

    def execute_actionj(self, model, method, params):
        return self._execute_actionj("object", "execute", [model,method]+params)

    def execute_model_action(self, model, action, params):
        return self._execute_actionj("object", "execute", [model,action]+params)

    def execute_loginj(self):
        return self._execute_actionj("common", "login",[])

    
    def _get_changes(self, model:str, new_only:bool):
        to_create = []
        to_createm:list[OdooWrapperInterface] = []
        for o in self.objects:
            if new_only and o.get_id(None) != None:
                continue
            if o.changes and o.model == model:
                cm: dict[str,Any] = {}
                for k, v in o.changes.items():
                    if isinstance(v, OdooWrapperInterface):
                        if v.id:
                            cm[f"{k}_id"] = v.id
                    else:
                        cm[k] = v
                to_create.append(cm)  
                to_createm.append(o)  
                    
        return to_create, to_createm
    
    def commit(self):
        updated_models = set([m._MODEL for m in self.objects])# type: ignore
        models = [m for m in [ # preferred order of saving
               "x_cd.supplier_payment",
                "x_cd.supplier_payment_part",
                "x_cd.cto", 
                "x_cd.cto_booking",
                "x_cd.cto_booking_entry",
                "x_cd.cto_payment",
                "x_cd.commission_forecast"
        ] if m in updated_models]
        
        for model in models: 
            to_create,to_createm = self._get_changes(model, True)

            if to_create:
                # print(f"createing {model} = {len(to_create)}")
                # print(f"createing {model}")
                ids = self.create(model, [to_create]) # type: ignore
                
                for i, new_id in enumerate(ids):
                    to_createm[i].wrapped_oject['id'] = new_id

                    for k,v in to_create[i].items(): # delete any keys that were saved
                        k:str
                        to_createm[i].wrapped_oject[k] = v
                        if k.endswith("_id") and to_createm[i].changes[k[:-3]]:
                            del to_createm[i].changes[k[:-3]]    
                        else:
                            del to_createm[i].changes[k]
                # print(f"created {to_create}")
                for c in to_createm:
                    for ffk in c.related_records.values(): # type: ignore
                        for ff in ffk:
                            for _, p in inspect.getmembers(type(ff)):  # Iterate directly
                                if isinstance(p, property): 
                                    try:
                                        other =p.fget(ff) # type: ignore
                                        if other == c:
                                            p.fset(ff,c) # type: ignore
                                    except ValueError as e:                        
                                        pass

            to_update,to_updatem = self._get_changes(model, False)

            for i, em in enumerate(to_update):
                if em:
                    emdo = to_updatem[i]  
                    self.write(model, emdo.id, em)

                    for k,v in to_update[i].items(): # delete any keys that were saved
                        to_updatem[i].wrapped_oject[k] = v
                        if k.endswith("_id") and to_updatem[i].changes[k[:-3]]:
                            del to_updatem[i].changes[k[:-3]]    
                        else:
                            del to_updatem[i].changes[k]     

class OdooBackend:
    def __init__(self, db):
        self.db = db
        self.url = f"https://{db}.odoo.com"
        p = KeePass().get_login(f"api://{db}.odoo.com")
        self.username = p.login
        self.api_key = p.password
        self.modelCache:dict[str,list[str]] = {}
        self._lazy_uid:str|None = None

    
    @property
    def uid(self) -> str|None:
        if not self._lazy_uid:
            rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
            self.version:str = rpcmodel.version() # type: ignore
            self._lazy_uid = rpcmodel.authenticate(self.db, self.username, self.api_key, {}) # type: ignore
        return self._lazy_uid

    def begin(self) -> OdooTransaction:
        return OdooTransaction(self)

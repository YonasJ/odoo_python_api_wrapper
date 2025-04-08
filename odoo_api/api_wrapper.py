from __future__ import annotations  # This is crucial for forward references
from abc import ABC, abstractmethod
import copy
from datetime import date, datetime
import inspect
import re
import threading
from .data_class_interface import OdooWrapperInterface
from typing import TYPE_CHECKING, TypeVar
if TYPE_CHECKING:
    from .data_class import OdooDataClass
    from .data_class import OdooManyToManyHelper

from collections import defaultdict
from typing import Any
from .utils import Timer
import xmlrpc.client
import json
import random
import urllib
import urllib.request
from .keepass_passwords import KeePass

T = TypeVar('T', bound='OdooWrapperInterface')

class OdooTransaction:    
    lock = threading.RLock()

    def __init__(self, backend:OdooBackend):
        self.backend = backend
        self.objects:dict[str, OdooWrapperInterface] = {}
        self.cache:dict[str, OdooWrapperInterface] = {}
        self.deletes:list[OdooWrapperInterface] = []
        self.verbose_logs = True
        self.aborted = False
        self.rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url), allow_none=True)

    def _key(self, x:OdooWrapperInterface) -> str:
        if not x.id: raise ValueError(f"Object must have an ID to be saved {x}")
        return f"{x.MODEL}:{x.id}"
    def _gen_working_id(self) -> int:
        with self.lock:
            self.backend.working_id -= 1
            return self.backend.working_id

    # Append the object to the transacition, if it already exists, return the existing object
    def append(self, x:T) -> T:
        with self.lock:
            key = self._key(x)
            ret = self.objects.get(key)
            if ret:
                return ret # type: ignore
            elif x.transaction != self:
                deep_copy = copy.deepcopy(x, memo={'trans':self}) # type: ignore
                # No need to add to the transaction as it will have added itself in the constructor.
                return deep_copy
            else:
                self.objects[key] = x
                self.cache[key] = x
                self.backend.cache[key] = x
                return x

    def extend(self, e:list[T]) -> list[T]:
        with self.lock:
            ret = []
            for x in e:
                ret.append(self.append(x))
            return ret
    
    def check_in(self, x:OdooWrapperInterface) -> bool:
        with self.lock:
            key = self._key(x)
            if key in self.objects:
                if id(self.objects[key]) != id(x):
                    raise ValueError(f"Different version in transaction {x.MODEL}:{x.id}")
                return True
            return False

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
        with self.lock:
            model: str = wrapper._get_model()
            
            if field == "id":
                assert value
                key = f"{model}:{value}"
                if key in self.cache:
                    return self.cache[key]# type: ignore
                if key in self.backend.cache:
                    return self.append(self.backend.cache[key])# type: ignore
                        
            for _,o in enumerate(self.cache.values()):
                if o.MODEL == model and getattr(o,field) == value:
                    if self.verbose_logs: print(f"Get: {model}  -- {field} = {value} (cache hit)")
                    return o # type: ignore
            for _,o in enumerate(self.backend.cache.values()):
                if o.MODEL == model and getattr(o,field) == value:
                    if self.verbose_logs: print(f"Get: {model}  -- {field} = {value} (backend cache hit)")
                    return self.append(o) # type: ignore
            
            if self.verbose_logs: print(f"Get: {model}  -- {field} = {value} (cache miss)")
            ret = self.search(wrapper, [(field, "=", value)],getting=True)
            if ret:
                return ret[0]
            
    def _matches_search(self, c:OdooWrapperInterface, search:list[tuple[str,str,Any]]):
        for s in search:
            sqv = getattr(c, s[0])
            if s[1] == "=":
                if isinstance(sqv,OdooWrapperInterface):
                    if sqv.id != s[2]:
                        return False
                elif sqv != s[2]:
                    return False
            elif s[1] == "in":
                if sqv not in s[2]:
                    return False
            else:
                raise ValueError(f"Unknown search operator {s[1]}")
        return True
  #   record = env['event.registration'].search([('id', '=', 14)])
    def get2(self, wrapper:type[T], search:list[tuple[str,str,Any]]) -> T|None:
        with self.lock:
            model: str = wrapper._get_model() # type: ignore
            only_local_search = True

            if len(search) == 1 and search[0][0] == "id" and search[0][1] == "=":
                key = f"{model}:{search[0][2]}"
                if key in self.cache:
                    return self.cache[key]# type: ignore
                if key in self.backend.cache:
                    return self.append(self.backend.cache[key])# type: ignore
            else:
                for cache in [self.cache, self.backend.cache]:
                    for x in cache.values():
                        if x.MODEL != model:
                            continue
                        if self._matches_search(x, search):
                            return self.append(x) # type: ignore

            # Confirmed cache miss, record is not saved.

            if len(search) == 1 and search[0][0] == "id" and search[0][1] == "=" and search[0][2] < 0:
                return None

            if self.verbose_logs: print(f"Get2: {model}  -- {search} (cache miss)")
            ret = self.search(wrapper, search,getting=True)
            if ret:
                return ret[0]
    
    @staticmethod
    def convert_value(value):
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        elif isinstance(value, OdooWrapperInterface):
            return value.id
        return value

    def search_limit_order(self, wrapper:type[T], search, order:str, limit:int=1,fields=[],) -> T|None:
        search_2 = []
        for s in search:
            if len(s) == 1:
                search_2.append(s)  
            else:                
                search_2.append((s[0], s[1], OdooTransaction.convert_value(s[2])))
                        
        model: str = wrapper._get_model() # type: ignore
        for x in self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'search_read', [search_2], {'fields': fields, 'limit': limit, 'order':order}):# type: ignore
            existing = self.cache.get(f"{model}:{x['id']}")
            if existing:
                assert isinstance(existing, wrapper)
                return existing  
            else:
                id = x["id"]
                del x["id"]
                nr:T = wrapper(self, id, x) # type: ignore
                return nr
        return None


  #   record = env['event.registration'].search([('id', '=', 14)])
    def search(self, wrapper:type[T], search, fields=[], getting:bool=False) -> list[T]:
        p = '  ' if getting else ''

        with self.lock:
            model: str = wrapper._get_model() # type: ignore
            # Manually search for items in transaction if searching for an unsaved record.
            if len(search) == 1 and search[0][1] == "=" and isinstance(search[0][2], int) and search[0][2] < 0:
                ret = []
                for x in self.cache.values():
                    if x.MODEL != model:
                        continue
                    if self._matches_search(x, search):
                        ret.append(x)

                if self.verbose_logs: print(f"{p}Search: {model}  -- {search} (searched local for -ve id)")
                return ret
            if len(search) == 1 and search[0][1] == "in" and isinstance(search[0][2], list):
                ret = []
                for x in search[0][2]:
                    xo = self.get(wrapper, search[0][0], x)
                    if xo:
                        ret.append(xo)
                    else:
                        ret = None
                        break
                if ret:
                    if self.verbose_logs: print(f"{p}Search: {model}  -- {search} (searched local for in)")
                    return ret
        search_2 = []
        for s in search:
            if len(s) == 1:
                search_2.append(s)  
            else:                
                search_2.append((s[0], s[1], OdooTransaction.convert_value(s[2])))

        with Timer() as t:
            ret = []
            with self.lock:
                for x in self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'search_read', [search_2], {'fields': fields, 'limit': 5000}):# type: ignore
                    # First check if this object is already in the transactions.
                    existing = self.cache.get(f"{model}:{x['id']}")
                    if existing:
                        ret.append(existing)
                    else:
                        id = x["id"]
                        del x["id"]
                        nr:T = wrapper(self, id, x) # type: ignore
                        ret.append(nr) 

            if self.verbose_logs and search in [ # these are search, not get. And they could be lazy. It is fetching them just in case.
                    [('name', '=', 'Kelsey Janssen'), ('function', 'in', ['Owner', 'Manager', 'Consultant'])],
                    [('name', '=', 'Sharon Smith'), ('function', 'in', ['Owner', 'Manager', 'Consultant'])]
                ]:
                print("debug")
            if self.verbose_logs and search not in[
                    [('related_cto_numbers', '=', False)],
                    ['&', ('sync_date', '=', False), ('name', '!=', False)],
                    ['&', ('matched_status', '=', 'new'), ('related_cto_numbers', '!=', 'No match')],

                ]:

                if (search[0][0] == "id" and search[0][1] == "=") and not getting:
                    print(f"{p}Search {t.elapsed:2.1f}: {model}  -- {search} (opportunity)")
                else: 
                    print(f"{p}Search {t.elapsed:2.1f}: {model}  -- {search}")
                    pass
                if len(search) == 1 and search[0][1] == "=" and isinstance(search[0][2], int) and search[0][2] < 0:
                    print(f"{p}Search {t.elapsed:2.1f}: {model}  -- {search} (negative id)")
                pass

        return ret

    def search_singleton(self, wrapper:type[T], search, fields=[]) -> T|None: 
        with self.lock:
            ret = self.search(wrapper, search, fields)
            if len(ret) == 0:
                return None
            if len(ret) > 1:
                raise ValueError(f"Expected 1 record, got {len(ret)}")
            return ret[0]  

    def search_first(self, wrapper:type[T], search, fields=[]) -> T|None: 
        with self.lock:
            ret = self.search(wrapper, search, fields)
            if len(ret) == 0:
                return None
            return ret[0]  


    def search_raw(self, model:str, search, fields=[]) -> list[OdooWrapperInterface]:
        with self.lock:
            ret = []
            for x in self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'search_read', [search], {'fields': fields, 'limit': 5000}):# type: ignore
                from .object_wrapper import ObjectWrapper
                ret.append(ObjectWrapper(self, model,x)) # type: ignore
            return ret
    
    def read(self, model:str, id, fields) -> OdooWrapperInterface:
        with self.lock:
            from .object_wrapper import ObjectWrapper
            return ObjectWrapper(self, model, self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'read', [[id]], {'fields': fields})[0])# type: ignore
    
    def create(self, model:str, rec:list[dict[str,Any]]) -> list[int]:
        with self.lock:
            return self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'create', rec) # type: ignore

    def write(self, model:str, id_pk, rec):
        with self.lock:

            # loop through all keys in rec and replace all values of None with False.
            for k,v in rec.items():
                if v == None:
                    rec[k] = False

            if self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'write', [[id_pk], rec]):
                return True
            return False

    def update_many_to(self, model:str, special_command):
        with self.lock:
            return self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'write', special_command)

    def delete(self, to_delete:OdooWrapperInterface) -> None:
        if to_delete.id > 0:
            self.deletes.append(to_delete)
        self.cache.pop(self._key(to_delete))
        self.objects.pop(self._key(to_delete))
        self.backend.cache.pop(self._key(to_delete))

    def execute_delete(self, wrapper:type[T]|str, ids:list[int]) -> None:
        with self.lock:
            if isinstance(wrapper, str):
                model = wrapper
            else:
                model: str = wrapper._get_model() # type: ignore
            # if rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'unlink', [ids]):
            #     return True
            # return False
            for id in ids:
                if id:
                    self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, 'unlink', [id])

    def execute_action(self, model:str, action:str,search):
        with self.lock:
            if self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, action, search):
                return True
            return False
    def execute_action2(self, model:str, action:str,p1,p2):
        with self.lock:
            if self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, model, action, [p1,p2]):
                return True
            return False
            
      
    def _execute_actionj(self, rpc_service, rpc_method, params):
        with self.lock:
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

    def install_module(self, module:str):
        raise Exception("This has not been tested.")
        with self.lock:
            return self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, 'ir.module.module', 'button_install', [[module]])

    def uninstall_module(self, module:str):
        raise Exception("This has not been tested.")
        with self.lock:
            return self.rpcmodel.execute_kw(self.db, self.uid, self.api_key, 'ir.module.module', 'button_immediate_uninstall', [[module]])

    def _get_changes_early_save(self, v:OdooWrapperInterface):
        from .data_class import OdooManyToManyHelper
        new_obj = {}
        old_key: str = self._key(v)
        v_changes = dict(v.changes)
        for ck,cv in list(v.changes.items()): #object's is changed when new keys are generated for saved objects.
            if isinstance(cv, OdooWrapperInterface):
                if cv.id and cv.id >= 0:
                    v.wrapped_oject[ck] = new_obj[ck] = cv.id
                    del v.changes[ck]
            elif isinstance(v, OdooManyToManyHelper):
                pass
            elif ck == "id":
                raise ValueError("ID should not be in changes")
                del v.changes[ck] # don't pass this to create.
            else:
                v.wrapped_oject[ck] = new_obj[ck] = cv
                del v.changes[ck]

        ids: int = self.create(v.MODEL, [new_obj]) # type: ignore
        assert isinstance(ids, int)

        # Move it to the new key.
        del self.objects[old_key]
        del self.cache[old_key]
        v.wrapped_oject['id'] = ids
        assert 'id' not in v.changes # was cleaned by the copy.
        self.objects[self._key(v)] = v
        self.cache[self._key(v)] = v
        return v.id
    
    def  _get_changes(self, model:str, new_only:bool):
        with self.lock:
            from .data_class import OdooManyToManyHelper

            to_create = []
            to_createm:list[OdooWrapperInterface] = []
            for _,o in list(enumerate(self.objects.values())): #object's is changed when new keys are generated for saved objects.
                assert o.transaction == self, f"Object must be in the transaction it is being saved {o}"
                assert o.id, "Object must have an ID. Negative before save."
                if new_only and o.id >= 0: # Negative ID is working id.
                    continue
                if o.changes and o.MODEL == model:
                    cm: dict[str,Any] = {}
                    o_changes = dict(o.changes)

                    for k, v in o.changes.items():
                        if k == "id":
                            continue # don't update/create id's
                        if isinstance(v, OdooWrapperInterface):
                            assert v.id
                            if v.id >= 0:
                                cm[k] = v.id
                            else:
                                cm[k] = self._get_changes_early_save(v)

                        elif isinstance(v, OdooManyToManyHelper):
                            c = []
                            for x in v.adds:
                                assert x.id
                                if x.id < 0:
                                    self._get_changes_early_save(x)
                                assert x.id>0
                                c.append((4,x.id)) # 4 is the magic number for adding a many2many: https://www.odoo.com/forum/help-1/setting-tags-on-res-partner-via-automated-actions-198441
                            # v is going to be a parameter to the write call.
                            cm[k] = c
                        else:
                            cm[k] = v
                    to_create.append(cm)  
                    to_createm.append(o)  
                        
            return to_create, to_createm
    
    def __find_duplicates(self):
        return
        duplicates = []
        keys = list(self.objects.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                if id(self.objects[keys[i]]) == id(self.objects[keys[j]]):
                    duplicates.append((keys[i], keys[j]))
        if duplicates:
            print(f"Found {len(duplicates)} duplicates")
        return duplicates
    
    def abort(self) -> None:
        self.aborted = True

    def commit(self) -> None:
        if self.aborted:
            raise ValueError("Transaction was aborted")

        with self.lock:
            updated_models = set([m.MODEL for _,m in enumerate(self.objects.values())])# type: ignore
            models = [m for m in self.backend.save_order if m in updated_models]
            for m in updated_models:
                if m not in models:
                    models.append(m)
            
            for model in models: 
                to_create,to_createm = self._get_changes(model, True)

                if to_create:
                    # print(f"createing {model} = {len(to_create)}")
                    # print(f"createing {model}")

                    #
                    # PART 1: CREATE NEW RECORDS
                    #
                    ids = self.create(model, [to_create]) # type: ignore
                    for i, new_id in enumerate(ids):
                        old_key = self._key(to_createm[i])
                        del self.objects[old_key]
                        del self.cache[old_key]

                        to_createm[i].id = new_id

                        new_key = self._key(to_createm[i])
                        self.objects[new_key] = to_createm[i]
                        self.cache[new_key] = to_createm[i]

                        for k,v in to_create[i].items(): # delete any keys that were saved
                            k:str
                            to_createm[i].wrapped_oject[k] = v
                            # if k.endswith("_id") and to_createm[i].changes[k[:-3]]:
                            #     del to_createm[i].changes[k[:-3]]    
                            # else:
                            #     del to_createm[i].changes[k]
                            assert k != "id"
                            del to_createm[i].changes[k]
                            self.__find_duplicates()
                    # print(f"created {to_create}")

                for x in to_createm:
                    self.backend.cache[self._key(x)] = copy.deepcopy(x, memo={'trans':self})# type: ignore

            for model in models: 
                to_update,to_updatem = self._get_changes(model, False)

                for i, em in enumerate(to_update):
                    if em:
                        emdo = to_updatem[i]  
                        self.write(model, emdo.id, em)

                        for k,v in to_update[i].items(): # delete any keys that were saved
                            to_updatem[i].wrapped_oject[k] = v

                            try:
                                del to_updatem[i].changes[k]    
                            except KeyError as e:
                                if not k == "category_id" and not k == "consultant": # Many to many puts 2 changes in the list...
                                    raise e  # an error here may indicate a transaction shared between threads...
                for x in to_updatem:
                    self.backend.cache[self._key(x)] = copy.deepcopy(x, memo={'trans':self})# type: ignore

            delete_groups = defaultdict(list)
            for d in self.deletes:
                delete_groups[d.__class__].append(d.id)

            # Delete all the IDs in each class
            for cls, ids in delete_groups.items():
                self.execute_delete(cls, ids)

            self.backend.cache.update(self.cache)

            self.deletes.clear()
            self.cache.clear()
            self.objects.clear()
            


# TODO: Create a TRANS_ID in the object that doesn't change once mappeed into a trans.
# USE THAT FOR EQUALS as well.

class OdooBackend:
    def __init__(self, db, save_order = []):
        if db.startswith('http'):
            self.url = db
        else:   
            self.url = f"https://{db}.odoo.com"
        match = re.search(r"https?://([^.]+)", self.url)
        self.db: str | Any = match.group(1) if match else None

        p = KeePass().get_login(re.sub(r"https?", "api", self.url))
        self.username = p.login
        self.api_key = p.password
        self.modelCache:dict[str,list[str]] = {}
        self._lazy_uid:str|None = None
        
        self.save_order = save_order

        self.cache:dict[str, OdooWrapperInterface] = {}
        self.working_id = -100


    @property
    def uid(self) -> str|None:
        if not self._lazy_uid:
            rpcmodel = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
            self.version:str = rpcmodel.version() # type: ignore
            self._lazy_uid = rpcmodel.authenticate(self.db, self.username, self.api_key, {}) # type: ignore
        return self._lazy_uid

    def begin(self) -> OdooTransaction:
        return OdooTransaction(self)

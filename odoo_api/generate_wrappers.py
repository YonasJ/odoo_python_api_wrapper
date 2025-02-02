import os
from .api_wrapper import OdooTransaction


class Klass:
    model_classes = {}
    def __init__(self, odoo:OdooTransaction, model, name):
        self.name = name
        self.model = model
        self.model_classes[model] = self.name
        self.imports = {}
        self.add_import("odoo_api.data_class", "OdooDataClass")
        self.add_import("odoo_api.api_wrapper", "OdooTransaction")
        self.add_import("typing", "TypeVar")
        self.type_only_forward_imports = {}
        self.odoo: OdooTransaction = odoo

    def add_import(self,ifrom:str,iitem:str) -> str:
        if ifrom in self.imports:
            if not iitem in self.imports[ifrom]:
                self.imports[ifrom] = ",".join([self.imports[ifrom], iitem])
        else:
            self.imports[ifrom] = iitem
        return iitem

    def field(self, field,read_only) -> None:
        prop_name = field_name = field['name']

        if prop_name in ['create_uid', 'write_uid', 'id']:
            return

        db_type = field['ttype']

        if field_name.startswith("x_"):
            prop_name = field_name.replace("x_", "", 1)

        self.fields += f"    _{prop_name.upper()} = '{field_name}'\n"


        if db_type == 'many2one':
            rel_prop_name = prop_name

            other_class_name = self.model_classes.get(field['relation'], "OdooDataClass")
            self.type_only_forward_imports[f"db.{other_class_name}"] = other_class_name
            
            always_set_for_type_checking = (field['required'] or 
                                            "CASCADE" in str(field['on_delete']).upper() or
                                            "RESTRICT" in str(field['on_delete']).upper()
                                            ) 
            self.field_desc += f"    # {prop_name} is a many2one field of type {other_class_name}\n"
            self.fields += f"    @property # many2one\n"
            self.fields += f"    def {rel_prop_name}(self) -> {other_class_name}{"|None" if not always_set_for_type_checking else ""} : # required: {field['required']}, on delete: {field['on_delete']}\n"
            if other_class_name != "OdooDataClass":
                self.fields += f"        from db.{other_class_name} import {other_class_name}\n"
            self.fields += f"        ret = self.get_many2one(self._{prop_name.upper()}, {other_class_name}) \n"
            if always_set_for_type_checking:
                self.fields += f"        if not ret: raise ValueError(f'Key {prop_name} is not set.') \n"
            self.fields += f"        return ret\n"
            self.fields += f"    def get_{rel_prop_name}(self, when_none:T|None=None) -> {other_class_name}|T:\n"
            if other_class_name != "OdooDataClass":
                self.fields += f"        from db.{other_class_name} import {other_class_name}\n"
            self.fields += f"        ret = self.get_many2one(self._{prop_name.upper()}, {other_class_name},when_none)\n"
            self.fields += f"        return ret if ret else when_none # type: ignore\n"
            
            if not read_only:
                self.fields += f"    @{rel_prop_name}.setter\n"
                self.fields += f"    def {rel_prop_name}(self, value:{other_class_name}|None) -> None:\n"
                self.fields += f"        self.set_{rel_prop_name}(value)\n"
                self.fields += f"    def set_{rel_prop_name}(self, value:{other_class_name}|None) -> None:\n"
                self.fields += f"        self.set_many2one(self._{prop_name.upper()}, value)\n"

        elif db_type == 'one2many':
            # self.imports['typing'] = 'list'
            other_class_name = self.model_classes.get(field['relation'], "OdooDataClass")
            self.field_desc += f"    # {prop_name} is a one2many field of type {other_class_name} \n"
            self.type_only_forward_imports[f"{other_class_name}"] = other_class_name
            self.fields += f"    @property # one2many\n"
            self.fields += f"    def {prop_name}(self) -> list[{other_class_name}]:\n"
            self.fields += f"        return self.get_{prop_name}()\n"
            self.fields += f"    def get_{prop_name}(self) -> list[{other_class_name}]:\n"
            if other_class_name != "OdooDataClass":
                self.fields += f"        from db.{other_class_name} import {other_class_name}\n"
            self.fields += f"        ret = self.get_one2many(self._{prop_name.upper()}, {other_class_name}, '{field['relation_field']}')\n"
            self.fields += f"        return ret\n\n"
        elif db_type == 'many2many':
            # self.imports['typing'] = 'list'
            other_class_name = self.model_classes.get(field['relation'], "OdooDataClass")
            self.field_desc += f"    # {prop_name} is a many2many field of type {other_class_name} \n"
            self.type_only_forward_imports[f"db.{other_class_name}"] = other_class_name
            self.fields += f"    @property # many2many\n"
            self.fields += f"    def {prop_name}(self) -> tuple[{other_class_name}]:\n"
            if other_class_name != "OdooDataClass":
                self.fields += f"        from db.{other_class_name} import {other_class_name}\n"
            self.fields += f"        ret = self.get_many2many(self._{prop_name.upper()}, {other_class_name}) \n"
            self.fields += f"        return ret\n"
            self.fields += f"    def {prop_name}_append(self, new_value:{other_class_name}|list[{other_class_name}]):\n"
            if other_class_name != "OdooDataClass":
                self.fields += f"        from db.{other_class_name} import {other_class_name}\n"
            self.fields += f"        self.append_many2many(self._{prop_name.upper()}, {other_class_name}, new_value) \n\n"
        else:                    
            
            match db_type:
                case 'float': py_type = py_conversion = 'float'
                case 'date': 
                    py_type = self.add_import("datetime", "datetime")
                    py_conversion = 'date'
                    
                case 'datetime':  
                    py_type = self.add_import("datetime", "datetime")
                    py_conversion = 'date'
                case 'many2one':
                    py_conversion = 'int'
                    py_type = 'int'
                case 'integer':  py_type = py_conversion = 'int'
                case 'boolean':  py_type = py_conversion = 'bool'
                case 'char':  py_type = py_conversion = 'str'
                case _:  # Default case
                    py_type = py_conversion = 'str'

            self.field_desc += f"    # {prop_name} is a {py_type} field  \n"
                
            if py_conversion == 'date':
                self.fields += f"    def get_{prop_name}_str(self, format:str = '%Y-%m-%d', when_none:str|T=None) -> str|T:\n"
                self.fields += f"        ret = self.get_value_{py_conversion}(self._{prop_name.upper()})\n"
                self.fields += f"        if ret is None: \n"
                self.fields += f"            return when_none\n"
                self.fields += f"        return ret.strftime(format)\n"
                
            self.fields += f"    def get_{prop_name}(self, when_none:T=None) -> {py_type}|T:\n"
            self.fields += f"        ret = self.get_value_{py_conversion}(self._{prop_name.upper()})\n"
            self.fields += f"        if ret is None: \n"
            self.fields += f"            return when_none\n"
            self.fields += f"        return ret\n"

            if (db_type == 'float' or db_type == 'integer' or db_type == 'char'):
                self.fields += f"    @property # use get version to check for none, this will return 0 or empty string in the property.\n"
                self.fields += f"    def {prop_name}(self) -> {py_type}:\n"
                self.fields += f"        ret = self.get_{prop_name}()\n"
                if db_type == 'float':
                    self.fields += f"        if ret is None: return 0.00\n"
                elif db_type == 'integer':
                    self.fields += f"        if ret is None: return 0\n"
                elif db_type == 'char':
                    self.fields += f"        if ret is None: return ''\n"
                else: 
                    raise ValueError(f"Unknown type {db_type}")
                    
                self.fields += f"        return ret\n"
            else:
                self.fields += f"    @property\n"
                self.fields += f"    def {prop_name}(self) -> {py_type}|None:\n"
                self.fields += f"        ret = self.get_{prop_name}()\n"
                # self.fields += f"        if ret is None: raise ValueError(f'Key {prop_name} is not set.')\n"
                self.fields += f"        return ret\n"
                
            if not read_only:            
                self.fields += f"    @{prop_name}.setter\n"
                self.fields += f"    def {prop_name}(self, value:{py_type}|None) -> None:\n"
                self.fields += f"        self.set_value_{py_conversion}(self._{prop_name.upper()}, value)\n"
                            
            self.fields += "\n\n"

    def save(self, base_dir="."):
        
        self.file_name_base = f'{base_dir}/db/{self.name}B.py'
        self.file_name_ext = f'{base_dir}/db/{self.name}.py'
        self.init_py_path = f"{base_dir}/db/__init__.py"

        self.field_desc = ""
        self.fields = ""
        
        for emodel in self.odoo.search_raw('ir.model',[("model","=", self.model)]):
            print(f"Loading model {emodel.get_value('name')}")

            fields = self.odoo.search_raw('ir.model.fields', [("model", "=", self.model)])
            fields_sorted = sorted(fields, key=lambda field: (field.get_value("name") or "").lstrip("x_"))

            for field in fields_sorted:
                if field.get_value("name") in ['id', 'create_uid', 'write_uid']:
                    continue
                
                read_only = False
                if field.get_value('readonly'):
                    read_only = True

                self.field(field, read_only)

        header = ""
        header += f"\n"
        header += f"T = TypeVar('T')\n"
        header += f"\n"
        header += f"class {self.name}B(OdooDataClass):\n"
        header += f"    MODEL = '{self.model}'\n\n"


        header += f"    def __init__(self, trans:OdooTransaction, id:int|None, wo:dict[str,{self.add_import('typing','Any')}]|None):\n"
        header += f"        super().__init__(trans, self.MODEL, id, wo)\n"
        header += f"\n"        
        
        imports = ""
        if self.type_only_forward_imports:
            for k,v in self.type_only_forward_imports.items():            
                if v != "OdooDataClass":
                    if not "from typing import TYPE_CHECKING" in imports:
                        imports += f"from __future__ import annotations  # This is crucial for forward references\n"
                        imports += f"from typing import TYPE_CHECKING\n"
                        imports += f"if TYPE_CHECKING:\n"
                    imports += f"    from {k} import {v} # Import only when type checking\n"

        for k,v in self.imports.items():       
            imports += f"from {k} import {v}\n"

        
        complete_class = imports+header+self.field_desc+self.fields

        try:
            with open(self.file_name_base, 'w') as f:
                f.write(complete_class)
            print(f"Code written to {self.file_name_base}")

            if not os.path.exists(self.file_name_ext):
                with open(self.file_name_ext, 'w') as f:
                    f.write(f"from db.{self.name}B import {self.name}B\nfrom typing import Any\nfrom odoo_api.api_wrapper import OdooTransaction\n\nclass {self.name}({self.name}B):\n    def __init__(self, odoo:OdooTransaction, id:int|None=None,wo:dict[str,Any]|None = None):\n        super().__init__(odoo, id, wo)")

            import_statement = f"from .{self.name} import {self.name}\n"

            if os.path.exists(self.init_py_path):
                with open(self.init_py_path, 'r') as f:
                    content = f.read()
            else:
                content = ""

            if import_statement not in content:
                content += import_statement
                with open(self.init_py_path, 'w') as f:
                    f.write(content)

        except Exception as e:
            print(f"Error writing to file: {e}")       

         

# odoo = OdooBackend("mixt").begin()
# models = [
#      Klass(odoo, "x_cd.supplier_payment", "SupplierPayment"),
#      Klass(odoo, "x_cd.supplier_payment_part", "SupplierPaymentPart"),
#      Klass(odoo, "x_cd.cto", "CTO"),
#      Klass(odoo, "x_cd.cto_booking", "CTOBooking"),
#      Klass(odoo, "x_cd.cto_booking_entry", "CTOBookingEntry"),
#      Klass(odoo, "x_cd.cto_payment", "CTOPayment"),
#      Klass(odoo, "x_cd.commission_forecast", "CDCommissionForecast"),
#      ]

# for model in models:
#     model.save()

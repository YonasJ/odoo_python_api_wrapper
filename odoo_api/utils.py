from datetime import datetime
import time
from typing import Any

import xlrd
# from typing import TYPE_CHECKING, TypeVar
# if TYPE_CHECKING:
from typing import TypeVar

def my_strptime(row, field, format) -> datetime|None:
    if not row[field]:  # Check if the string is empty
        return None

    try:
        return datetime.strptime(row[field], format)
    except ValueError:  # Handle invalid date format
        return None

T = TypeVar('T')  # Define a TypeVar
def parse_money(value:str|None, when_none:T=False) -> float | T:
  """Converts a string to a float, handling commas, dollar signs, and spaces.

  Args:
    value: The string value to convert.

  Returns:
    The float value.
  """
  try:
    if not value or len(value) == 0:
        return when_none
    
    # Remove commas, dollar signs, and spaces
    cleaned_value = value.replace(',', '').replace('$', '').replace(' ', '')  
    return float(cleaned_value)
  except ValueError:
    # Handle cases where the value is not a valid number
    return when_none 

def normalize_money(value:float) -> float:
    if value == -0.0:
        return 0.00
    return round(value,2)


T = TypeVar('T')
from dataclasses import fields, is_dataclass
from xlrd import xldate_as_datetime

def parse_row_to_dataclass(data_class: type[T], row_number: int, headers:list[str], row: list[Any], workbook:xlrd.book.Book|None = None) -> T:
    if not is_dataclass(data_class):
        raise TypeError(f"{data_class} is not a dataclass")
    kwargs: dict[str,Any] = {"row_number": row_number}
    for f in fields(data_class):
        if f.name != "row_number":
            if f.metadata.get("col"):
                col = f.metadata["col"]
                value = row[col]
            elif f.metadata.get("name"):
                col = f.metadata["name"]
                if headers.index(col) < len(row):
                    value = row[headers.index(col)]
                else:
                    value = None
            else:
                raise Exception(f"Field {f.name} is missing metadata")

            if isinstance(value, xlrd.sheet.Cell) and value.ctype == 0:
                kwargs[f.name] = None
                continue

            if f.type == datetime:
                if not value:
                    value = None
                elif isinstance(value, xlrd.sheet.Cell) and value.ctype == 3:  # Check if the value is an Excel date
                    if not workbook: raise Exception("Workbook must be provided for Excel dates")
                    value = xldate_as_datetime(value.value, workbook.datemode)
                elif isinstance(value, str):
                    if not f.metadata.get("format"): raise Exception(f"Date format not provided for {f.name}. should be format=...")  
                    value = datetime.strptime(value, str(f.metadata.get("format")))
                else: raise Exception(f"Invalid date format {value}")

            elif f.type == float:
                if isinstance(value, xlrd.sheet.Cell):  # Check if the value is an Excel date
                    value = value.value
                if isinstance(value, float):
                    value = value
                else:
                    value = parse_money(value)
            elif isinstance(value, xlrd.sheet.Cell): 
                value = value.value

            kwargs[f.name] = value
    return data_class(**kwargs)

class Timer:
    def __init__(self, threshold=None):
        self.print_slow_warning_threshold = threshold

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        elapsed_time = self.end_time - self.start_time
        if self.print_slow_warning_threshold:
            if elapsed_time > self.print_slow_warning_threshold:
                print(f"Execution time: {elapsed_time:.2f} seconds")

            if elapsed_time > 9:
                print(f"Execution time: {elapsed_time:.2f} seconds")      
        return False
    
    @property
    def elapsed(self):
        self.end_time = time.time()
        self.elapsed_time = self.end_time - self.start_time        
        return self.elapsed_time
    
class DuplicateKeyError(Exception): pass

class SingleList(list):
    def append(self, value):
        if value in self:
            raise DuplicateKeyError('Value {!r} already present'.format(value))
        super().append(value)


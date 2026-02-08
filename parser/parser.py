from typing import Mapping, MutableMapping, Tuple, TypedDict
from typing import *
import re
# from common.common import EveItem, InvalidItemError, ItemCount
import logging

from sqlalchemy.orm import Session, aliased

import model.model


logger = logging.getLogger()

EveItem = model.EsiItemInfo

class ItemCount(TypedDict):
    type : EveItem
    count : int

ItemList = List[ItemCount]

def verifyItem(session: Session, typeName: str) -> Optional[model.EsiItemInfo]:
    item = session.query(model.EsiItemInfo).filter(model.EsiItemInfo.typeName.ilike(typeName)).one_or_none()
    return item


def parse_multibuy_items(session: Session, buylist: str) ->ItemList:
    entries = buylist.split("\n")
    items : ItemList = list()
    invalids : List[str] = list()
    for entry in entries:
        #skip empty lines
        if not entry:
            continue
        cols = entry.split("\t")
        if cols[0] == "Total:":
            break
        count:int
        count = int(cols[1].replace('.','')) if len(cols) > 1 else 1
        item = cols[0]
        item_model = verifyItem(session, item)
        if item_model:
            items.append(({'type':item_model,'count':count}))
        else:
            invalids.append(item)
    return items

def _add_count(item_list : MutableMapping[EveItem,int], entry: ItemCount):
    item = entry['type']
    count = entry['count']
    if item in item_list:
        item_list[item] = item_list[item] + count
    else:
        item_list[item] = count

def parse_mod(session: Session, item_line: str) -> Optional[ItemCount]:
    # Looks for a "Item x10" string which will come out as ("Item", 10)
    item_line.rstrip()
    wds = item_line.split(" ")
    res = re.search("x([1-9]+[0-9]*)", wds[-1])

    model = verifyItem(session, item_line)
    if model:
        return (ItemCount(type = model, count = 1))
    elif res and res[1]:
        count = int(res[1])
        item_line = " ".join(wds[0:len(wds)-1])
        model = verifyItem(session, item_line)
        if model:
            return (ItemCount(type = model, count = count))
    return None

FittingItems = Mapping[EveItem,int]

# Parses EFT-Style fitting into items
def parse_fit(session: Session, fitting : str) -> FittingItems:
    lines = fitting.split("\n")

    items = lines
    item_list : MutableMapping[EveItem,int]= {}
    # item_list[ship] = 1
    for item_line in items:
        try:
            if(item_line == ""):
                continue

            item_counts:List[Tuple[EveItem,int]]
            # Line of a ship
            if(item_line[0] == '['):
                wds = item_line.split(",")
                ship = wds[0][1:]
                ship_model = verifyItem(session, ship)
                if(ship_model):
                    _add_count(item_list, ItemCount(type=ship_model, count=1))
            else:
                if "," in item_line:
                    items = item_line.split(",")
                else:
                    items = [item_line]

                for item_name in items:
                        (item_count) = parse_mod(session, item_name)
                        if item_count:
                            _add_count(item_list, item_count)
        # except InvalidItemError as err:
        #     logger.critical("Skipping invalid Item {}".format(err.itemName))
        finally:
            pass

    return item_list

def fit2buy(fit : FittingItems) -> List[EveItem]:
    return [(key) for key in fit.keys()]

def fit2dna(fit : FittingItems) -> str:
    dna_string = ""
    for (type, count) in fit.items():
        dna_string = dna_string + f"{type.typeID};{count}:"

    return dna_string


if __name__ == "__main__":
    pass

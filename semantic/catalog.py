"""Database Catalog and Schema definitions for SQL Semantic Analysis."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ColumnSchema:
    name: str
    data_type: str  # 'INT', 'FLOAT', 'VARCHAR', 'DATE'
    is_primary_key: bool = False
    foreign_key_to: Optional[str] = None  # e.g., 'customers.id'


@dataclass
class TableSchema:
    name: str
    columns: Dict[str, ColumnSchema] = field(default_factory=dict)

    def add_column(
        self,
        name: str,
        data_type: str,
        is_primary_key: bool = False,
        foreign_key_to: Optional[str] = None,
    ) -> None:
        self.columns[name.lower()] = ColumnSchema(
            name=name,
            data_type=data_type.upper(),
            is_primary_key=is_primary_key,
            foreign_key_to=foreign_key_to,
        )

    def get_column(self, name: str) -> Optional[ColumnSchema]:
        return self.columns.get(name.lower())

    def column_names(self) -> List[str]:
        return [col.name for col in self.columns.values()]


class DatabaseCatalog:
    """Relational Database Catalog holding table schemas, primary keys, and foreign keys."""

    def __init__(self):
        self.tables: Dict[str, TableSchema] = {}

    def add_table(self, table: TableSchema) -> None:
        self.tables[table.name.lower()] = table

    def get_table(self, name: str) -> Optional[TableSchema]:
        return self.tables.get(name.lower())

    def has_table(self, name: str) -> bool:
        return name.lower() in self.tables

    def table_names(self) -> List[str]:
        return [tbl.name for tbl in self.tables.values()]

    def all_column_names(self) -> List[str]:
        cols = []
        for tbl in self.tables.values():
            cols.extend(tbl.column_names())
        return list(dict.fromkeys(cols))

    def get_foreign_keys_between(self, table1: str, table2: str) -> List[tuple[str, str]]:
        """
        Return pairs of (col1, col2) that form a valid FK relationship
        between table1 and table2 in either direction.
        """
        t1 = self.get_table(table1)
        t2 = self.get_table(table2)
        if not t1 or not t2:
            return []

        relationships: List[tuple[str, str]] = []

        # Check t1 FKs pointing to t2
        for col_name, col_meta in t1.columns.items():
            if col_meta.foreign_key_to:
                target_tbl, target_col = col_meta.foreign_key_to.split(".")
                if target_tbl.lower() == t2.name.lower():
                    relationships.append((col_meta.name, target_col))

        # Check t2 FKs pointing to t1
        for col_name, col_meta in t2.columns.items():
            if col_meta.foreign_key_to:
                target_tbl, target_col = col_meta.foreign_key_to.split(".")
                if target_tbl.lower() == t1.name.lower():
                    relationships.append((target_col, col_meta.name))

        return relationships


def create_default_catalog() -> DatabaseCatalog:
    """Creates the standard university lab database catalog specified in the project report."""
    catalog = DatabaseCatalog()

    # 1. customers table
    customers = TableSchema("customers")
    customers.add_column("id", "INT", is_primary_key=True)
    customers.add_column("name", "VARCHAR")
    customers.add_column("city", "VARCHAR")
    customers.add_column("signup_date", "DATE")
    catalog.add_table(customers)

    # 2. orders table
    orders = TableSchema("orders")
    orders.add_column("id", "INT", is_primary_key=True)
    orders.add_column("customer_id", "INT", foreign_key_to="customers.id")
    orders.add_column("order_date", "DATE")
    orders.add_column("status", "VARCHAR")
    catalog.add_table(orders)

    # 3. order_items table
    order_items = TableSchema("order_items")
    order_items.add_column("order_id", "INT", foreign_key_to="orders.id")
    order_items.add_column("product_id", "INT", foreign_key_to="products.id")
    order_items.add_column("quantity", "INT")
    order_items.add_column("price", "FLOAT")
    catalog.add_table(order_items)

    # 4. products table
    products = TableSchema("products")
    products.add_column("id", "INT", is_primary_key=True)
    products.add_column("name", "VARCHAR")
    products.add_column("category", "VARCHAR")
    products.add_column("price", "FLOAT")
    catalog.add_table(products)

    return catalog

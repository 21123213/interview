"""数据库连接和操作模块 - 使用 TDSQL-C (MySQL) 直连"""
import os
from typing import Any, Dict, List, Optional

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()


def escape_sql_string(value: Any) -> str:
    """
    转义SQL字符串，防止SQL注入
    :param value: 要转义的值
    :return: 转义后的字符串（带单引号）
    """
    if value is None:
        return 'NULL'

    if isinstance(value, bool):
        return '1' if value else '0'

    if isinstance(value, (int, float)):
        return str(value)

    s = str(value)
    s = s.replace('\\', '\\\\')
    s = s.replace("'", "\\'")

    return f"'{s}'"


def build_insert_sql(table: str, data: Dict[str, Any]) -> str:
    """构建INSERT SQL语句（防SQL注入）"""
    fields = ', '.join(data.keys())
    values = ', '.join([escape_sql_string(v) for v in data.values()])
    return f'INSERT INTO {table} ({fields}) VALUES ({values})'


def build_update_sql(table: str, data: Dict[str, Any], where: Dict[str, Any]) -> str:
    """构建UPDATE SQL语句（防SQL注入）"""
    set_clause = ', '.join([f'{k} = {escape_sql_string(v)}' for k, v in data.items()])
    where_clause = ' AND '.join([f'{k} = {escape_sql_string(v)}' for k, v in where.items()])
    return f'UPDATE {table} SET {set_clause} WHERE {where_clause}'


class DatabaseClient:
    """数据库客户端 - 直连 TDSQL-C (MySQL)"""

    def __init__(self):
        self.host = os.getenv('TDSQL_HOST', 'localhost')
        self.port = int(os.getenv('TDSQL_PORT', '3306'))
        self.user = os.getenv('TDSQL_USER', 'root')
        self.password = os.getenv('TDSQL_PASSWORD', '')
        self.database = os.getenv('TDSQL_DB', 'paper_rag')
        self.charset = os.getenv('TDSQL_CHARSET', 'utf8mb4')
        self.connect_timeout = int(os.getenv('TDSQL_CONNECT_TIMEOUT', '10'))

    def _connect(self, dict_cursor: bool = False):
        config = {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'password': self.password,
            'database': self.database,
            'charset': self.charset,
            'autocommit': True,
            'connect_timeout': self.connect_timeout,
        }
        if dict_cursor:
            config['cursorclass'] = DictCursor

        ssl_ca = os.getenv('TDSQL_SSL_CA')
        if ssl_ca:
            config['ssl'] = {'ca': ssl_ca}

        return pymysql.connect(**config)

    def ping(self) -> bool:
        """测试数据库连接"""
        conn = self._connect()
        try:
            conn.ping(reconnect=True)
            return True
        finally:
            conn.close()

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """执行查询SQL，返回字典列表"""
        conn = self._connect(dict_cursor=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                return list(rows) if rows else []
        except pymysql.MySQLError as e:
            print(f"Database query error: {e}")
            raise Exception(f"Database query failed: {str(e)}") from e
        finally:
            conn.close()

    def execute(self, sql: str) -> Dict[str, Any]:
        """执行写操作SQL（INSERT, UPDATE, DELETE）"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                affected_rows = cursor.execute(sql)
                return {
                    'affected_rows': affected_rows,
                    'last_insert_id': cursor.lastrowid or 0,
                }
        except pymysql.MySQLError as e:
            raise Exception(f"Database execute failed: {str(e)}") from e
        finally:
            conn.close()

    def execute_with_params(self, sql: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """执行带参数的写操作SQL"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                return {
                    'affected_rows': affected_rows,
                    'last_insert_id': cursor.lastrowid or 0,
                }
        except pymysql.MySQLError as e:
            raise Exception(f"Database execute failed: {str(e)}") from e
        finally:
            conn.close()

    def fetch_rows(self, sql: str, params: Optional[tuple] = None) -> List[tuple]:
        """执行带参数的查询，返回元组列表"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return list(rows) if rows else []
        except pymysql.MySQLError as e:
            raise Exception(f"Database query failed: {str(e)}") from e
        finally:
            conn.close()

    def execute_many(self, sql_list: List[str]) -> Dict[str, Any]:
        """批量执行SQL"""
        total_affected = 0
        for sql in sql_list:
            result = self.execute(sql)
            total_affected += result.get('affected_rows', 0)

        return {'affected_rows': total_affected}


# 全局数据库客户端实例
db_client = DatabaseClient()


def query(sql: str) -> List[Dict[str, Any]]:
    """执行查询"""
    return db_client.query(sql)


def execute(sql: str) -> Dict[str, Any]:
    """执行写操作"""
    return db_client.execute(sql)


def execute_many(sql_list: List[str]) -> Dict[str, Any]:
    """批量执行"""
    return db_client.execute_many(sql_list)


def execute_query(sql: str, params: Optional[tuple] = None) -> int:
    """执行写操作，返回插入ID或影响行数"""
    res = db_client.execute_with_params(sql, params)
    last_id = res.get('last_insert_id', 0)
    if last_id:
        return last_id
    return res.get('affected_rows', 0)


def fetch_all(sql: str, params: Optional[tuple] = None) -> List[tuple]:
    """返回所有行，统一为 tuple 列表"""
    return db_client.fetch_rows(sql, params)


def fetch_one(sql: str, params: Optional[tuple] = None) -> Optional[tuple]:
    """返回第一行或 None"""
    rows = fetch_all(sql, params)
    return rows[0] if rows else None

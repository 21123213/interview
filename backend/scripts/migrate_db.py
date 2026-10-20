"""
数据库迁移脚本
执行 migrations/001_add_new_tables.sql
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import execute_query, fetch_all
from dotenv import load_dotenv

load_dotenv()


def read_migration_file(filename: str) -> str:
    """读取迁移SQL文件"""
    migration_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'migrations',
        filename
    )
    
    with open(migration_path, 'r', encoding='utf-8') as f:
        return f.read()


def execute_migration_sql(sql_content: str):
    """执行迁移SQL（分割多个语句）"""
    # 分割SQL语句（以分号和换行符分隔）
    statements = []
    current_statement = []
    
    for line in sql_content.split('\n'):
        # 跳过注释行
        line = line.strip()
        if not line or line.startswith('--'):
            continue
        
        current_statement.append(line)
        
        # 如果行以分号结束，这是一个完整的语句
        if line.endswith(';'):
            statement = ' '.join(current_statement).strip()
            if statement and not statement.startswith('--'):
                statements.append(statement)
            current_statement = []
    
    # 执行每个语句
    success_count = 0
    error_count = 0
    
    for idx, statement in enumerate(statements, 1):
        # 跳过SHOW和DESC命令（它们不是修改命令）
        if statement.upper().startswith(('SHOW', 'DESC')):
            continue
        
        try:
            print(f"\n[{idx}/{len(statements)}] 执行SQL...")
            # 只显示前100个字符
            preview = statement[:100] + '...' if len(statement) > 100 else statement
            print(f"   {preview}")
            
            execute_query(statement)
            print("   ✅ 成功")
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            error_count += 1
            
            # 如果是表已存在的错误，继续
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                print("   ⚠️  表/字段已存在，跳过")
                continue
            
            # 其他错误，询问是否继续
            if input("   继续执行剩余迁移? (y/n): ").lower() != 'y':
                raise
    
    return success_count, error_count


def verify_migration():
    """验证迁移结果"""
    print("\n" + "=" * 60)
    print("验证迁移结果")
    print("=" * 60)
    
    tables_to_check = [
        'file_metadata',
        'document_elements',
        'document_chunks',
        'chat_sessions',
        'chat_messages',
        'processing_tasks'
    ]
    
    for table in tables_to_check:
        try:
            # 检查表是否存在
            sql = f"SHOW TABLES LIKE '{table}'"
            result = fetch_all(sql)
            
            if result:
                print(f"✅ {table:25} - 存在")
                
                # 获取记录数
                count_sql = f"SELECT COUNT(*) as count FROM {table}"
                count_result = fetch_all(count_sql)
                if count_result:
                    count = count_result[0][0] if isinstance(count_result[0], tuple) else count_result[0].get('count', 0)
                    print(f"   记录数: {count}")
            else:
                print(f"❌ {table:25} - 不存在")
        
        except Exception as e:
            print(f"⚠️  {table:25} - 检查失败: {e}")
    
    # 检查 file_metadata 的新字段
    print("\n检查 file_metadata 新字段...")
    try:
        sql = "SHOW COLUMNS FROM file_metadata"
        columns = fetch_all(sql)
        
        new_fields = [
            'total_elements',
            'total_chunks',
            'embedded_chunks',
            'elements_stats'
        ]
        
        existing_columns = [col[0] if isinstance(col, tuple) else col.get('Field') for col in columns]
        
        for field in new_fields:
            if field in existing_columns:
                print(f"   ✅ {field}")
            else:
                print(f"   ❌ {field} - 缺失")
    
    except Exception as e:
        print(f"   ⚠️  检查失败: {e}")


def main():
    """主函数"""
    print("\n" + "🔧" * 30)
    print("RAG系统数据库迁移")
    print("🔧" * 30)
    
    print("\n⚠️  注意:")
    print("   1. 此操作将修改数据库结构")
    print("   2. 建议先备份数据库")
    print("   3. 确保数据库连接配置正确")
    
    confirm = input("\n确认执行迁移? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ 迁移已取消")
        return
    
    try:
        # 读取迁移文件
        print("\n📖 读取迁移文件...")
        migration_sql = read_migration_file('001_add_new_tables.sql')
        print(f"   文件大小: {len(migration_sql)} 字符")
        
        # 执行迁移
        print("\n🔨 执行迁移...")
        success_count, error_count = execute_migration_sql(migration_sql)
        
        print("\n" + "=" * 60)
        print(f"迁移完成: {success_count} 成功, {error_count} 失败")
        print("=" * 60)
        
        # 验证迁移
        verify_migration()
        
        print("\n✅ 数据库迁移成功!")
        print("\n📚 下一步:")
        print("   1. 运行验证脚本: python scripts/verify_migration.py")
        print("   2. 启动FastAPI: uvicorn app.main:app --reload")
        print("   3. 测试文件上传功能")
        
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

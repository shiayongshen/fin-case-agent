import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

# 定義資料表結構 - 完整版本
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    identifier TEXT UNIQUE NOT NULL,
    "createdAt" TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    name TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    tags TEXT,
    "createdAt" TEXT,
    metadata TEXT,
    FOREIGN KEY ("userId") REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    "threadId" TEXT NOT NULL,
    "parentId" TEXT,
    streaming BOOLEAN,
    "waitForAnswer" BOOLEAN,
    "isError" BOOLEAN,
    metadata TEXT,
    tags TEXT,
    input TEXT,
    output TEXT,
    "createdAt" TEXT,
    start TEXT,
    end TEXT,
    generation TEXT,
    "showInput" TEXT,
    language TEXT,
    indent INTEGER,
    "defaultOpen" BOOLEAN,
    FOREIGN KEY ("threadId") REFERENCES threads(id)
);

CREATE TABLE IF NOT EXISTS elements (
    id TEXT PRIMARY KEY,
    "threadId" TEXT,
    type TEXT,
    url TEXT,
    "chainlitKey" TEXT,
    name TEXT,
    display TEXT,
    "objectKey" TEXT,
    size TEXT,
    page INTEGER,
    language TEXT,
    "forId" TEXT,
    mime TEXT,
    props TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads(id)
);

CREATE TABLE IF NOT EXISTS feedbacks (
    id TEXT PRIMARY KEY,
    "forId" TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    value INTEGER NOT NULL,
    comment TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads(id)
);
"""

async def init_database():
    engine = create_async_engine("sqlite+aiosqlite:///./chainlit.db")
    
    async with engine.begin() as conn:
        # 分割並執行每個 CREATE TABLE 語句
        for statement in SCHEMA.split(';'):
            if statement.strip():
                await conn.execute(text(statement))
    
    await engine.dispose()
    print("✅ 資料庫初始化完成!")

if __name__ == "__main__":
    asyncio.run(init_database())
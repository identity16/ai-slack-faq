"""
SQLite Semantic Data Store

시맨틱 데이터를 SQLite 데이터베이스에 저장하고 관리하는 모듈입니다.
"""

import os
import json
import sqlite3
from typing import Dict, Any, List
from datetime import datetime

from .. import SemanticStore, SemanticType

class SQLiteStore(SemanticStore):
    """SQLite 기반 시맨틱 데이터 저장소"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        초기화
        
        Args:
            config: 데이터베이스 설정 정보
        """
        db_path = config.get("db_path") if config else os.environ.get("SEMANTIC_DB_PATH", "data/semantic.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """데이터베이스 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 시맨틱 데이터 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS semantic_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                keywords TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 키워드 인덱스 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_index (
                keyword TEXT NOT NULL,
                semantic_id INTEGER,
                FOREIGN KEY(semantic_id) REFERENCES semantic_data(id),
                PRIMARY KEY(keyword, semantic_id)
            )
            """)
            
            conn.commit()
    
    async def store(self, semantic_data: List[Dict[str, Any]]) -> None:
        """
        시맨틱 데이터 저장
        
        Args:
            semantic_data: 저장할 시맨틱 데이터 목록
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for data in semantic_data:
                # 메타데이터 준비
                metadata = {}
                
                # 데이터 타입에 따른 처리
                data_type = data.get("type", "")
                
                # 타입 정규화
                if isinstance(data_type, str):
                    type_value = data_type
                else:
                    # SemanticType 클래스의 속성인 경우
                    type_value = data_type
                
                # 타입에 따른 처리
                if type_value == SemanticType.QA:
                    metadata["question"] = data.get("question", "")
                    content = data.get("answer", "")
                else:
                    content = data.get("content", "")
                    if "reference_type" in data:
                        metadata["reference_type"] = data.get("reference_type", "")
                
                # 데이터 저장
                cursor.execute(
                    """
                    INSERT INTO semantic_data (type, content, metadata, keywords, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        type_value,
                        content,
                        json.dumps(metadata),
                        json.dumps(data.get("keywords", [])),
                        json.dumps(data.get("source", {})),
                        datetime.now().isoformat()
                    )
                )
                
                semantic_id = cursor.lastrowid
                
                # 키워드 인덱스 생성
                for keyword in data.get("keywords", []):
                    cursor.execute(
                        "INSERT INTO keyword_index (keyword, semantic_id) VALUES (?, ?)",
                        (keyword.lower(), semantic_id)
                    )
            
            conn.commit()
    
    async def retrieve(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        시맨틱 데이터 검색
        
        Args:
            query: 검색 조건
                - type: 데이터 유형 (qa, insight 등)
                - keywords: 검색할 키워드 목록
                - source_type: 소스 유형 (slack_thread, notion_section 등)
                - date_from: 시작 날짜
                - date_to: 종료 날짜
            
        Returns:
            검색된 시맨틱 데이터 목록
        """
        conditions = []
        params = []
        
        # 검색 조건 구성
        if "type" in query:
            type_value = query["type"]
            # SemanticType 클래스의 속성이면 문자열로 변환
            if not isinstance(type_value, str):
                type_value = type_value
            conditions.append("type = ?")
            params.append(type_value)
        
        if "keywords" in query:
            keywords = query["keywords"]
            if keywords:
                placeholders = ",".join("?" * len(keywords))
                conditions.append(f"id IN (SELECT semantic_id FROM keyword_index WHERE keyword IN ({placeholders}))")
                params.extend([k.lower() for k in keywords])
        
        if "source_type" in query:
            conditions.append("json_extract(source, '$.type') = ?")
            params.append(query["source_type"])
        
        if "date_from" in query:
            conditions.append("created_at >= ?")
            params.append(query["date_from"])
        
        if "date_to" in query:
            conditions.append("created_at <= ?")
            params.append(query["date_to"])
        
        # SQL 쿼리 구성
        sql = "SELECT * FROM semantic_data"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY created_at DESC"
        
        # 쿼리 실행
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            results = cursor.execute(sql, params).fetchall()
            
            # 결과 변환
            semantic_data = []
            for row in results:
                data = {
                    "id": row["id"],
                    "type": row["type"],
                    "content": row["content"],
                    "created_at": row["created_at"]
                }
                
                # 메타데이터 복원
                metadata = json.loads(row["metadata"])
                
                # 타입에 따른 처리
                if row["type"] == SemanticType.QA:
                    data["question"] = metadata.get("question", "")
                    data["answer"] = data.pop("content", "")
                elif "reference_type" in metadata:
                    data["reference_type"] = metadata.get("reference_type", "")
                
                # 키워드 및 소스 정보 복원
                try:
                    data["keywords"] = json.loads(row["keywords"])
                except (json.JSONDecodeError, TypeError):
                    data["keywords"] = []
                    
                try:
                    data["source"] = json.loads(row["source"])
                except (json.JSONDecodeError, TypeError):
                    data["source"] = {}
                
                semantic_data.append(data)
            
            return semantic_data 